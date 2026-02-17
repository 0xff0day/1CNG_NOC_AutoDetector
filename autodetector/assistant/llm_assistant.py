from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from autodetector.ai.llm import LLMRegistry


@dataclass
class AssistantConfig:
    model_name: str
    system_prompt: str = "You are a senior network operations assistant. Be concise and actionable."
    max_tokens: int = 512
    temperature: float = 0.3


@dataclass
class AssistantResponse:
    text: str
    model: str
    metadata: Dict[str, Any]


def generate_assistant_response(
    cfg: AssistantConfig,
    instruction: str,
    input_data: Any = None,
    context: Optional[List[Dict[str, str]]] = None,
) -> AssistantResponse:
    model = LLMRegistry.get_loaded_model(cfg.model_name) or LLMRegistry.load_model(cfg.model_name)
    if not model:
        raise RuntimeError(f"Model not available: {cfg.model_name}")

    if input_data is None:
        input_text = ""
    elif isinstance(input_data, str):
        input_text = input_data
    else:
        input_text = json.dumps(input_data, indent=2, sort_keys=True, default=str)

    prompt = model.format_prompt(
        instruction=instruction,
        input_text=input_text,
        system_prompt=cfg.system_prompt,
        context=context,
    )

    result = model.generate(prompt=prompt, max_tokens=cfg.max_tokens, temperature=cfg.temperature)
    return AssistantResponse(text=result.text, model=result.model_name, metadata=result.metadata or {})
