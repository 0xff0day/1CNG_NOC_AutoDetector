"""
Telnet Fallback Collector
Provides telnet connection support when SSH is unavailable.
"""

from __future__ import annotations

import telnetlib
import time
import re
from typing import Optional, List, Dict
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TelnetResult:
    """Result from telnet command execution."""
    device_id: str
    command: str
    output: str
    duration_ms: float
    success: bool
    error: str = ""


class TelnetFallbackCollector:
    """
    Telnet fallback collector for devices without SSH.
    
    Features:
    - Automatic login detection
    - Prompt detection and matching
    - Timeout handling
    - Session reuse
    """
    
    # Common prompt patterns
    PROMPT_PATTERNS = [
        rb'[>#\$]\s*$',  # Generic prompts
        rb'[\w-]+[>#\$]\s*$',  # Hostname-based prompts
        rb'Username:\s*$',
        rb'Password:\s*$',
        rb'Login:\s*$',
        rb'[\w-]+\(config[\w-]*\)[>#\$]\s*$',  # Config mode
        rb'--More--',  # Paging
        rb'Press any key to continue',
    ]
    
    def __init__(
        self,
        default_timeout: int = 30,
        connect_timeout: int = 10,
        command_timeout: int = 30,
    ):
        self.default_timeout = default_timeout
        self.connect_timeout = connect_timeout
        self.command_timeout = command_timeout
        
        # Session cache
        self._sessions: Dict[str, telnetlib.Telnet] = {}
        self._session_info: Dict[str, Dict] = {}
    
    def connect(
        self,
        device_id: str,
        host: str,
        port: int = 23,
        username: str = "",
        password: str = "",
        enable_password: str = "",
        prompt_pattern: Optional[bytes] = None,
    ) -> bool:
        """
        Establish telnet connection with automatic login.
        
        Args:
            device_id: Unique device identifier
            host: Hostname or IP
            port: Telnet port (default 23)
            username: Login username
            password: Login password
            enable_password: Enable mode password (for network devices)
            prompt_pattern: Custom prompt regex pattern
        
        Returns:
            True if connected and logged in successfully
        """
        try:
            logger.info(f"Connecting to {device_id} via telnet ({host}:{port})")
            
            # Create connection
            tn = telnetlib.Telnet(host, port, timeout=self.connect_timeout)
            
            # Perform login sequence
            logged_in = self._perform_login(tn, username, password, enable_password, prompt_pattern)
            
            if logged_in:
                self._sessions[device_id] = tn
                self._session_info[device_id] = {
                    "host": host,
                    "port": port,
                    "username": username,
                    "connected_at": time.time(),
                    "prompt_pattern": prompt_pattern,
                }
                logger.info(f"Telnet connection established for {device_id}")
                return True
            else:
                tn.close()
                logger.error(f"Login failed for {device_id}")
                return False
                
        except Exception as e:
            logger.error(f"Telnet connection failed for {device_id}: {e}")
            return False
    
    def _perform_login(
        self,
        tn: telnetlib.Telnet,
        username: str,
        password: str,
        enable_password: str,
        prompt_pattern: Optional[bytes],
    ) -> bool:
        """Perform automatic login sequence."""
        try:
            # Wait for initial prompt (username/login)
            match = tn.expect([b'Username:', b'Login:', b'User name:', b'login:'], timeout=5)
            
            if match[0] >= 0:  # Got username prompt
                tn.write(username.encode('ascii') + b'\n')
                
                # Wait for password prompt
                tn.read_until(b'Password:', timeout=5)
                tn.write(password.encode('ascii') + b'\n')
            else:
                # No username prompt, try password only
                tn.read_until(b'Password:', timeout=3)
                tn.write(password.encode('ascii') + b'\n')
            
            # Wait for command prompt
            prompt_match = tn.expect(self.PROMPT_PATTERNS, timeout=10)
            
            if prompt_match[0] < 0:
                logger.error("Failed to detect command prompt after login")
                return False
            
            # Check if we need to enter enable mode (Cisco-style)
            prompt = prompt_match[2]
            if b'>' in prompt and enable_password:
                tn.write(b'enable\n')
                tn.read_until(b'Password:', timeout=3)
                tn.write(enable_password.encode('ascii') + b'\n')
                
                # Wait for elevated prompt
                tn.expect(self.PROMPT_PATTERNS, timeout=5)
            
            # Disable paging on network devices
            self._disable_paging(tn, prompt_pattern)
            
            return True
            
        except Exception as e:
            logger.error(f"Login sequence error: {e}")
            return False
    
    def _disable_paging(self, tn: telnetlib.Telnet, custom_prompt: Optional[bytes] = None) -> None:
        """Disable paging/screen scrolling on network devices."""
        paging_commands = [
            b'terminal length 0\n',  # Cisco/IOS
            b'terminal pager 0\n',    # ASA/Firepower
            b'screen-length 0\n',   # Huawei/H3C
            b'no pagination\n',      # Some switches
            b'set cli screen-length 0\n',  # Juniper
        ]
        
        for cmd in paging_commands:
            try:
                tn.write(cmd)
                tn.expect(self.PROMPT_PATTERNS, timeout=2)
            except:
                pass
    
    def execute_command(
        self,
        device_id: str,
        command: str,
        timeout: Optional[int] = None,
    ) -> TelnetResult:
        """
        Execute command on connected device.
        
        Args:
            device_id: Device identifier
            command: Command to execute
            timeout: Command timeout override
        
        Returns:
            TelnetResult with output
        """
        start_time = time.time()
        
        if device_id not in self._sessions:
            return TelnetResult(
                device_id=device_id,
                command=command,
                output="",
                duration_ms=0,
                success=False,
                error="No active session",
            )
        
        tn = self._sessions[device_id]
        timeout = timeout or self.command_timeout
        
        try:
            # Send command
            tn.write(command.encode('utf-8') + b'\n')
            
            # Read output until prompt
            output = b''
            while True:
                try:
                    idx, match, data = tn.expect(self.PROMPT_PATTERNS, timeout=timeout)
                    output += data
                    
                    # Check if we got the prompt (indicating command complete)
                    if idx >= 0 and idx < 4:  # Prompt patterns
                        break
                    
                    # Handle --More-- paging
                    if idx == 5:  # --More--
                        tn.write(b' ')  # Send space to continue
                        continue
                    
                except Exception:
                    break
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Clean up output
            output_str = output.decode('utf-8', errors='replace')
            output_str = self._clean_output(output_str, command)
            
            return TelnetResult(
                device_id=device_id,
                command=command,
                output=output_str,
                duration_ms=duration_ms,
                success=True,
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return TelnetResult(
                device_id=device_id,
                command=command,
                output="",
                duration_ms=duration_ms,
                success=False,
                error=str(e),
            )
    
    def _clean_output(self, output: str, command: str) -> str:
        """Clean command output by removing echoed command and prompts."""
        lines = output.split('\n')
        
        # Remove first line (echoed command)
        if lines and command.strip() in lines[0]:
            lines = lines[1:]
        
        # Remove last line (prompt)
        if lines:
            last_line = lines[-1].strip()
            if last_line and last_line[-1] in '#>$':
                lines = lines[:-1]
        
        return '\n'.join(lines).strip()
    
    def execute_commands(
        self,
        device_id: str,
        commands: List[str],
        timeout: Optional[int] = None,
    ) -> List[TelnetResult]:
        """Execute multiple commands sequentially."""
        results = []
        for cmd in commands:
            result = self.execute_command(device_id, cmd, timeout)
            results.append(result)
            
            # Stop on failure if configured
            if not result.success:
                logger.warning(f"Command failed on {device_id}: {cmd}")
        
        return results
    
    def disconnect(self, device_id: str) -> bool:
        """Close telnet session."""
        if device_id in self._sessions:
            try:
                self._sessions[device_id].close()
                del self._sessions[device_id]
                del self._session_info[device_id]
                logger.info(f"Disconnected from {device_id}")
                return True
            except Exception as e:
                logger.error(f"Error disconnecting {device_id}: {e}")
        return False
    
    def disconnect_all(self) -> None:
        """Close all telnet sessions."""
        for device_id in list(self._sessions.keys()):
            self.disconnect(device_id)
    
    def is_connected(self, device_id: str) -> bool:
        """Check if device has active session."""
        return device_id in self._sessions
    
    def get_connected_devices(self) -> List[str]:
        """Get list of connected device IDs."""
        return list(self._sessions.keys())
    
    def reconnect(self, device_id: str) -> bool:
        """Reconnect to a device using stored credentials."""
        if device_id not in self._session_info:
            return False
        
        info = self._session_info[device_id]
        
        # Disconnect first
        self.disconnect(device_id)
        
        # Reconnect
        return self.connect(
            device_id=device_id,
            host=info["host"],
            port=info["port"],
            username=info["username"],
            password="",  # Would need to retrieve from credential vault
            prompt_pattern=info.get("prompt_pattern"),
        )


class ConnectionManager:
    """
    Unified connection manager that prefers SSH but falls back to Telnet.
    """
    
    def __init__(self, ssh_collector, telnet_collector):
        self.ssh = ssh_collector
        self.telnet = telnet_collector
        self._connection_methods: Dict[str, str] = {}  # device_id -> method
    
    def connect_with_fallback(
        self,
        device_id: str,
        host: str,
        ssh_port: int = 22,
        telnet_port: int = 23,
        username: str = "",
        password: str = "",
        **kwargs
    ) -> bool:
        """
        Try SSH first, then fall back to Telnet if needed.
        
        Returns:
            True if connected via either method
        """
        # Try SSH first
        if self.ssh.connect(device_id, host, ssh_port, username, password, **kwargs):
            self._connection_methods[device_id] = "ssh"
            logger.info(f"Connected to {device_id} via SSH")
            return True
        
        # Fall back to Telnet
        logger.warning(f"SSH failed for {device_id}, trying Telnet fallback")
        
        if self.telnet.connect(device_id, host, telnet_port, username, password):
            self._connection_methods[device_id] = "telnet"
            logger.info(f"Connected to {device_id} via Telnet (fallback)")
            return True
        
        logger.error(f"Failed to connect to {device_id} via SSH or Telnet")
        return False
    
    def execute(
        self,
        device_id: str,
        command: str,
        **kwargs
    ):
        """Execute command using appropriate method."""
        method = self._connection_methods.get(device_id, "ssh")
        
        if method == "ssh":
            return self.ssh.execute_command(device_id, command, **kwargs)
        else:
            return self.telnet.execute_command(device_id, command, **kwargs)
    
    def disconnect(self, device_id: str) -> None:
        """Disconnect from device using active method."""
        method = self._connection_methods.get(device_id)
        
        if method == "ssh":
            self.ssh.disconnect(device_id)
        elif method == "telnet":
            self.telnet.disconnect(device_id)
        
        if device_id in self._connection_methods:
            del self._connection_methods[device_id]
