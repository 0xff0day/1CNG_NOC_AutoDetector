from __future__ import annotations

from typing import Any, Dict, List


def parse(outputs: Dict[str, str], errors: Dict[str, str], device: Dict[str, Any]) -> Dict[str, Any]:
    _ = device
    _ = errors
    metrics: List[Dict[str, Any]] = []
    # TODO: parse CLI outputs into normalized variables
    return {"metrics": metrics, "raw": {"outputs": outputs, "errors": errors}}
