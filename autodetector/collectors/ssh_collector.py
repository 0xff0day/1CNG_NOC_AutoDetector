"""
SSH Multi-Session Collector
Manages multiple concurrent SSH connections for device data collection.
"""

from __future__ import annotations

import paramiko
import threading
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from queue import Queue, Empty
import logging

logger = logging.getLogger(__name__)


@dataclass
class SSHSession:
    """Represents an active SSH session."""
    device_id: str
    hostname: str
    username: str
    client: Optional[paramiko.SSHClient] = None
    channel: Optional[paramiko.Channel] = None
    last_used: float = 0.0
    session_lock: threading.Lock = None
    is_connected: bool = False
    
    def __post_init__(self):
        if self.session_lock is None:
            self.session_lock = threading.Lock()


@dataclass
class CommandResult:
    """Result from SSH command execution."""
    device_id: str
    command: str
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float
    timestamp: float
    success: bool


class SSHMultiSessionCollector:
    """
    Manages multiple concurrent SSH sessions for efficient device polling.
    
    Features:
    - Connection pooling and reuse
    - Concurrent command execution
    - Automatic reconnection
    - Session health monitoring
    """
    
    def __init__(
        self,
        max_sessions: int = 50,
        session_timeout: int = 300,
        command_timeout: int = 30,
        keepalive_interval: int = 60,
    ):
        self.max_sessions = max_sessions
        self.session_timeout = session_timeout
        self.command_timeout = command_timeout
        self.keepalive_interval = keepalive_interval
        
        # Session management
        self._sessions: Dict[str, SSHSession] = {}
        self._session_lock = threading.RLock()
        
        # Command queue for async processing
        self._command_queue: Queue = Queue()
        self._result_queue: Queue = Queue()
        
        # Worker threads
        self._workers: List[threading.Thread] = []
        self._shutdown_event = threading.Event()
        
        # Keepalive thread
        self._keepalive_thread: Optional[threading.Thread] = None
        
        # Statistics
        self._stats = {
            "commands_executed": 0,
            "commands_failed": 0,
            "sessions_created": 0,
            "sessions_reused": 0,
            "reconnections": 0,
        }
        self._stats_lock = threading.Lock()
        
        logger.info(f"SSH Multi-Session Collector initialized (max_sessions={max_sessions})")
    
    def start(self, num_workers: int = 4) -> None:
        """Start the collector with worker threads."""
        self._shutdown_event.clear()
        
        # Start command workers
        for i in range(num_workers):
            worker = threading.Thread(
                target=self._command_worker,
                name=f"SSHWorker-{i}",
                daemon=True
            )
            worker.start()
            self._workers.append(worker)
        
        # Start keepalive thread
        self._keepalive_thread = threading.Thread(
            target=self._keepalive_loop,
            name="SSHKeepalive",
            daemon=True
        )
        self._keepalive_thread.start()
        
        logger.info(f"Started {num_workers} SSH worker threads")
    
    def stop(self) -> None:
        """Stop the collector and close all sessions."""
        logger.info("Stopping SSH collector...")
        self._shutdown_event.set()
        
        # Signal workers to finish
        for _ in self._workers:
            self._command_queue.put(None)
        
        # Wait for workers
        for worker in self._workers:
            worker.join(timeout=5)
        
        # Close all sessions
        with self._session_lock:
            for session in list(self._sessions.values()):
                self._close_session(session)
            self._sessions.clear()
        
        logger.info("SSH collector stopped")
    
    def connect(
        self,
        device_id: str,
        hostname: str,
        port: int = 22,
        username: str = "",
        password: str = "",
        key_filename: Optional[str] = None,
        timeout: int = 30,
    ) -> bool:
        """Establish SSH connection to a device."""
        try:
            # Check for existing session
            with self._session_lock:
                if device_id in self._sessions:
                    session = self._sessions[device_id]
                    if session.is_connected:
                        logger.debug(f"Reusing existing session for {device_id}")
                        with self._stats_lock:
                            self._stats["sessions_reused"] += 1
                        return True
                    else:
                        # Remove stale session
                        self._close_session(session)
                        del self._sessions[device_id]
            
            # Create new connection
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            connect_kwargs = {
                "hostname": hostname,
                "port": port,
                "username": username,
                "timeout": timeout,
                "look_for_keys": False,
            }
            
            if key_filename:
                connect_kwargs["key_filename"] = key_filename
            elif password:
                connect_kwargs["password"] = password
            
            client.connect(**connect_kwargs)
            
            # Create session
            session = SSHSession(
                device_id=device_id,
                hostname=hostname,
                username=username,
                client=client,
                is_connected=True,
                last_used=time.time(),
            )
            
            with self._session_lock:
                self._sessions[device_id] = session
            
            with self._stats_lock:
                self._stats["sessions_created"] += 1
            
            logger.info(f"Connected to {device_id} ({hostname})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to {device_id}: {e}")
            return False
    
    def execute_command(
        self,
        device_id: str,
        command: str,
        timeout: Optional[int] = None,
        wait: bool = True,
    ) -> Optional[CommandResult]:
        """
        Execute command on a device.
        
        Args:
            device_id: Target device
            command: Command to execute
            timeout: Command timeout override
            wait: If True, wait for result; if False, queue for async
        
        Returns:
            CommandResult if wait=True, None otherwise
        """
        if not wait:
            # Queue for async processing
            self._command_queue.put((device_id, command, timeout))
            return None
        
        # Execute synchronously
        return self._execute_single(device_id, command, timeout)
    
    def execute_commands(
        self,
        device_id: str,
        commands: List[str],
        timeout: Optional[int] = None,
    ) -> List[CommandResult]:
        """Execute multiple commands on a device sequentially."""
        results = []
        for cmd in commands:
            result = self._execute_single(device_id, cmd, timeout)
            if result:
                results.append(result)
        return results
    
    def execute_parallel(
        self,
        commands_map: Dict[str, List[str]],
        timeout: Optional[int] = None,
    ) -> Dict[str, List[CommandResult]]:
        """
        Execute commands on multiple devices in parallel.
        
        Args:
            commands_map: {device_id: [commands]}
            timeout: Command timeout
        
        Returns:
            {device_id: [CommandResults]}
        """
        results: Dict[str, List[CommandResult]] = {}
        threads: List[threading.Thread] = []
        results_lock = threading.Lock()
        
        def execute_for_device(device_id: str, commands: List[str]):
            device_results = []
            for cmd in commands:
                result = self._execute_single(device_id, cmd, timeout)
                if result:
                    device_results.append(result)
            with results_lock:
                results[device_id] = device_results
        
        # Spawn threads for each device
        for device_id, commands in commands_map.items():
            thread = threading.Thread(
                target=execute_for_device,
                args=(device_id, commands)
            )
            thread.start()
            threads.append(thread)
        
        # Wait for all
        for thread in threads:
            thread.join()
        
        return results
    
    def _execute_single(
        self,
        device_id: str,
        command: str,
        timeout: Optional[int] = None,
    ) -> Optional[CommandResult]:
        """Execute a single command on a device."""
        session = self._get_session(device_id)
        if not session:
            logger.error(f"No session for device {device_id}")
            return CommandResult(
                device_id=device_id,
                command=command,
                stdout="",
                stderr="No active session",
                exit_code=-1,
                duration_ms=0,
                timestamp=time.time(),
                success=False,
            )
        
        timeout = timeout or self.command_timeout
        start_time = time.time()
        
        try:
            with session.session_lock:
                if not session.is_connected or not session.client:
                    logger.warning(f"Session not connected for {device_id}, attempting reconnect")
                    if not self._reconnect(session):
                        return None
                
                # Execute command
                stdin, stdout, stderr = session.client.exec_command(command, timeout=timeout)
                
                # Read output
                stdout_data = stdout.read().decode('utf-8', errors='replace')
                stderr_data = stderr.read().decode('utf-8', errors='replace')
                exit_code = stdout.channel.recv_exit_status()
                
                # Update session
                session.last_used = time.time()
                
                duration_ms = (time.time() - start_time) * 1000
                
                with self._stats_lock:
                    self._stats["commands_executed"] += 1
                
                return CommandResult(
                    device_id=device_id,
                    command=command,
                    stdout=stdout_data,
                    stderr=stderr_data,
                    exit_code=exit_code,
                    duration_ms=duration_ms,
                    timestamp=time.time(),
                    success=exit_code == 0,
                )
                
        except Exception as e:
            logger.error(f"Command failed on {device_id}: {e}")
            duration_ms = (time.time() - start_time) * 1000
            
            with self._stats_lock:
                self._stats["commands_failed"] += 1
            
            # Mark session as disconnected
            if session:
                session.is_connected = False
            
            return CommandResult(
                device_id=device_id,
                command=command,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                duration_ms=duration_ms,
                timestamp=time.time(),
                success=False,
            )
    
    def _get_session(self, device_id: str) -> Optional[SSHSession]:
        """Get session for device."""
        with self._session_lock:
            return self._sessions.get(device_id)
    
    def _reconnect(self, session: SSHSession) -> bool:
        """Attempt to reconnect a session."""
        try:
            logger.info(f"Reconnecting to {session.device_id}")
            
            # Close old connection
            self._close_session(session)
            
            # Reconnect with stored credentials
            # Note: This requires storing credentials or using keys
            # Implementation depends on credential vault integration
            
            with self._stats_lock:
                self._stats["reconnections"] += 1
            
            return session.is_connected
            
        except Exception as e:
            logger.error(f"Reconnection failed for {session.device_id}: {e}")
            return False
    
    def _close_session(self, session: SSHSession) -> None:
        """Close SSH session."""
        try:
            if session.client:
                session.client.close()
        except Exception as e:
            logger.debug(f"Error closing session: {e}")
        
        session.is_connected = False
        session.client = None
    
    def _command_worker(self) -> None:
        """Worker thread for processing commands."""
        while not self._shutdown_event.is_set():
            try:
                item = self._command_queue.get(timeout=1)
                if item is None:  # Shutdown signal
                    break
                
                device_id, command, timeout = item
                result = self._execute_single(device_id, command, timeout)
                
                if result:
                    self._result_queue.put(result)
                    
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Command worker error: {e}")
    
    def _keepalive_loop(self) -> None:
        """Background thread to send keepalives and cleanup stale sessions."""
        while not self._shutdown_event.is_set():
            try:
                time.sleep(self.keepalive_interval)
                
                if self._shutdown_event.is_set():
                    break
                
                current_time = time.time()
                stale_sessions: List[str] = []
                
                with self._session_lock:
                    for device_id, session in list(self._sessions.items()):
                        # Check if session is stale
                        if current_time - session.last_used > self.session_timeout:
                            stale_sessions.append(device_id)
                            continue
                        
                        # Send keepalive if connected
                        if session.is_connected and session.client:
                            try:
                                transport = session.client.get_transport()
                                if transport:
                                    transport.send_keepalive()
                            except Exception as e:
                                logger.debug(f"Keepalive failed for {device_id}: {e}")
                                session.is_connected = False
                
                # Cleanup stale sessions
                for device_id in stale_sessions:
                    logger.info(f"Closing stale session for {device_id}")
                    with self._session_lock:
                        if device_id in self._sessions:
                            self._close_session(self._sessions[device_id])
                            del self._sessions[device_id]
                            
            except Exception as e:
                logger.error(f"Keepalive loop error: {e}")
    
    def get_stats(self) -> Dict[str, int]:
        """Get collector statistics."""
        with self._stats_lock:
            return dict(self._stats)
    
    def get_active_sessions(self) -> List[str]:
        """Get list of active session device IDs."""
        with self._session_lock:
            return [
                device_id for device_id, session in self._sessions.items()
                if session.is_connected
            ]
    
    def disconnect(self, device_id: str) -> bool:
        """Disconnect from a device."""
        with self._session_lock:
            if device_id in self._sessions:
                self._close_session(self._sessions[device_id])
                del self._sessions[device_id]
                logger.info(f"Disconnected from {device_id}")
                return True
        return False
