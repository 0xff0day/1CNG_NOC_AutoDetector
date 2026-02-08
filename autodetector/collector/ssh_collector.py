from __future__ import annotations

import re
import socket
import time
from typing import Dict, List, Tuple

import paramiko


class SshCollector:
    def __init__(self, connect_timeout_sec: int = 10, command_timeout_sec: int = 15):
        self.connect_timeout_sec = int(connect_timeout_sec)
        self.command_timeout_sec = int(command_timeout_sec)

    def run_commands(self, host: str, username: str, password: str, commands: Dict[str, str]) -> Tuple[Dict[str, str], Dict[str, str]]:
        outputs: Dict[str, str] = {}
        errors: Dict[str, str] = {}

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            client.connect(
                hostname=host,
                username=username,
                password=password,
                timeout=self.connect_timeout_sec,
                banner_timeout=self.connect_timeout_sec,
                auth_timeout=self.connect_timeout_sec,
                look_for_keys=False,
                allow_agent=False,
            )

            for key, cmd in commands.items():
                try:
                    stdin, stdout, stderr = client.exec_command(cmd, timeout=self.command_timeout_sec)
                    _ = stdin
                    out = stdout.read().decode("utf-8", errors="replace")
                    err = stderr.read().decode("utf-8", errors="replace")
                    if err.strip():
                        errors[key] = err
                    outputs[key] = out
                except Exception as e:  # noqa: BLE001
                    errors[key] = str(e)
                    outputs[key] = ""
                time.sleep(0.05)

        except (paramiko.SSHException, socket.error, Exception) as e:  # noqa: BLE001
            for key in commands.keys():
                outputs[key] = ""
                errors[key] = f"SSH connect/exec failed: {e}"
        finally:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass

        return outputs, errors

    def run_commands_shell(
        self,
        host: str,
        username: str,
        password: str,
        commands: Dict[str, str],
        pre_commands: List[str],
        prompt_regex: str,
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        outputs: Dict[str, str] = {}
        errors: Dict[str, str] = {}

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            client.connect(
                hostname=host,
                username=username,
                password=password,
                timeout=self.connect_timeout_sec,
                banner_timeout=self.connect_timeout_sec,
                auth_timeout=self.connect_timeout_sec,
                look_for_keys=False,
                allow_agent=False,
            )

            chan = client.invoke_shell(width=200, height=80)
            chan.settimeout(self.command_timeout_sec)

            prompt = re.compile(prompt_regex.encode("utf-8"))

            def _recv_until_prompt(timeout_sec: float) -> bytes:
                buf = b""
                start = time.time()
                while True:
                    if time.time() - start > timeout_sec:
                        return buf
                    try:
                        if chan.recv_ready():
                            chunk = chan.recv(65535)
                            if not chunk:
                                return buf
                            buf += chunk
                            tail = buf[-4096:]
                            if prompt.search(tail):
                                return buf
                        else:
                            time.sleep(0.05)
                    except Exception:
                        time.sleep(0.05)

            _ = _recv_until_prompt(timeout_sec=3)

            for pc in pre_commands:
                try:
                    chan.send((pc + "\n").encode("utf-8"))
                    _recv_until_prompt(timeout_sec=self.command_timeout_sec)
                except Exception as e:  # noqa: BLE001
                    errors[f"pre:{pc}"] = str(e)

            for key, cmd in commands.items():
                try:
                    chan.send((cmd + "\n").encode("utf-8"))
                    raw = _recv_until_prompt(timeout_sec=self.command_timeout_sec)
                    outputs[key] = raw.decode("utf-8", errors="replace")
                except Exception as e:  # noqa: BLE001
                    outputs[key] = ""
                    errors[key] = str(e)
                time.sleep(0.05)

        except (paramiko.SSHException, socket.error, Exception) as e:  # noqa: BLE001
            for key in commands.keys():
                outputs[key] = ""
                errors[key] = f"SSH shell connect/exec failed: {e}"
        finally:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass

        return outputs, errors
