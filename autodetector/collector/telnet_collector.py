from __future__ import annotations

import telnetlib
import time
from typing import Dict, Tuple


class TelnetCollector:
    def __init__(self, connect_timeout_sec: int = 10, command_timeout_sec: int = 20):
        self.connect_timeout_sec = int(connect_timeout_sec)
        self.command_timeout_sec = int(command_timeout_sec)

    def run_commands(self, host: str, username: str, password: str, commands: Dict[str, str]) -> Tuple[Dict[str, str], Dict[str, str]]:
        outputs: Dict[str, str] = {}
        errors: Dict[str, str] = {}

        try:
            tn = telnetlib.Telnet(host, timeout=self.connect_timeout_sec)
            try:
                tn.read_until(b"login:", timeout=3)
                tn.write(username.encode("utf-8") + b"\n")
                tn.read_until(b"Password:", timeout=3)
                tn.write(password.encode("utf-8") + b"\n")
            except Exception:
                pass

            for key, cmd in commands.items():
                try:
                    tn.write(cmd.encode("utf-8") + b"\n")
                    time.sleep(0.5)
                    out = tn.read_very_eager().decode("utf-8", errors="replace")
                    outputs[key] = out
                except Exception as e:  # noqa: BLE001
                    outputs[key] = ""
                    errors[key] = str(e)

            tn.close()

        except Exception as e:  # noqa: BLE001
            for key in commands.keys():
                outputs[key] = ""
                errors[key] = f"Telnet connect/exec failed: {e}"

        return outputs, errors
