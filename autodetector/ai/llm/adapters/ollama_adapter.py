"""Ollama Adapter

Provides LLM inference via a local/remote Ollama server (HTTP API).

This adapter allows the AI NOC system to use Ollama-managed models without
requiring local GPU/transformers/llama.cpp runtime for inference.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Generator, List, Optional
import logging

import requests

from .. import BaseModelAdapter, GenerationResult, ModelArchitecture, ModelConfig

logger = logging.getLogger(__name__)


class OllamaAdapter(BaseModelAdapter):
    """Adapter for Ollama HTTP API."""

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self.architecture = ModelArchitecture.OLLAMA
        self._base_url = self._resolve_base_url(config)

    @staticmethod
    def _resolve_base_url(config: ModelConfig) -> str:
        # Prefer explicit custom param, then env var, then Ollama default.
        host = (config.custom_params or {}).get("ollama_host") or (config.custom_params or {}).get("host")
        if not host:
            import os

            host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

        host = str(host).rstrip("/")
        if not host.startswith("http://") and not host.startswith("https://"):
            host = f"http://{host}"
        return host

    def load(self) -> bool:
        """Check Ollama server availability."""
        try:
            r = requests.get(f"{self._base_url}/api/tags", timeout=5)
            self._is_loaded = r.status_code == 200
            if not self._is_loaded:
                logger.error("Ollama server not available: %s %s", r.status_code, r.text[:200])
            return self._is_loaded
        except Exception as e:
            logger.error("Failed to connect to Ollama at %s: %s", self._base_url, e)
            self._is_loaded = False
            return False

    def unload(self) -> None:
        self._is_loaded = False

    @property
    def _model_name(self) -> str:
        # For Ollama, model_path stores the ollama model name, e.g. "llama3:8b".
        return self.config.model_path

    def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop_sequences: Optional[List[str]] = None,
        **kwargs,
    ) -> GenerationResult:
        if not self._is_loaded:
            raise RuntimeError("Ollama adapter not loaded")

        max_tokens = max_tokens or self.config.max_tokens
        temperature = temperature if temperature is not None else self.config.temperature
        stop_sequences = stop_sequences or self.config.stop_sequences

        payload: Dict[str, Any] = {
            "model": self._model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": kwargs.get("top_p", self.config.top_p),
                "top_k": kwargs.get("top_k", self.config.top_k),
                "num_predict": max_tokens,
            },
        }
        if stop_sequences:
            payload["options"]["stop"] = stop_sequences

        start = time.time()
        r = requests.post(f"{self._base_url}/api/generate", json=payload, timeout=kwargs.get("timeout", 120))
        end = time.time()

        if r.status_code != 200:
            raise RuntimeError(f"Ollama generate failed: HTTP {r.status_code}: {r.text[:500]}")

        data = r.json()
        text = data.get("response", "")

        # Ollama does not return token counts consistently; use rough estimation.
        tokens_generated = len(self.tokenize(text))
        prompt_tokens = len(self.tokenize(prompt))
        elapsed = max(0.0001, end - start)

        return GenerationResult(
            text=text,
            tokens_generated=tokens_generated,
            tokens_per_second=tokens_generated / elapsed,
            prompt_tokens=prompt_tokens,
            finish_reason="stop" if data.get("done", True) else "length",
            model_name=self.config.name,
            metadata={
                "ollama_model": self._model_name,
                "base_url": self._base_url,
                "raw": {k: v for k, v in data.items() if k not in {"response"}},
            },
        )

    def generate_stream(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs,
    ) -> Generator[str, None, None]:
        if not self._is_loaded:
            raise RuntimeError("Ollama adapter not loaded")

        max_tokens = max_tokens or self.config.max_tokens
        temperature = temperature if temperature is not None else self.config.temperature

        payload: Dict[str, Any] = {
            "model": self._model_name,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "top_p": kwargs.get("top_p", self.config.top_p),
                "top_k": kwargs.get("top_k", self.config.top_k),
                "num_predict": max_tokens,
            },
        }

        with requests.post(
            f"{self._base_url}/api/generate",
            json=payload,
            stream=True,
            timeout=kwargs.get("timeout", 120),
        ) as r:
            if r.status_code != 200:
                raise RuntimeError(f"Ollama stream failed: HTTP {r.status_code}: {r.text[:500]}")

            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except Exception:
                    continue

                text = chunk.get("response")
                if text:
                    yield text

                if chunk.get("done"):
                    break

    def get_model_info(self) -> Dict[str, Any]:
        if not self._is_loaded:
            return {"loaded": False, "base_url": self._base_url, "ollama_model": self._model_name}

        info: Dict[str, Any] = {
            "loaded": True,
            "name": self.config.name,
            "architecture": self.architecture.value,
            "base_url": self._base_url,
            "ollama_model": self._model_name,
        }

        try:
            r = requests.post(f"{self._base_url}/api/show", json={"name": self._model_name}, timeout=10)
            if r.status_code == 200:
                data = r.json()
                info.update({"details": data.get("details"), "model": data.get("model"), "parameters": data.get("parameters")})
        except Exception:
            pass

        return info

    def tokenize(self, text: str) -> List[int]:
        # Ollama does not provide a generic tokenizer endpoint; use a stable approximation.
        # This is only used for rough stats, not for correctness.
        if not text:
            return []
        return [len(t) for t in text.split()]

    def detokenize(self, tokens: List[int]) -> str:
        # Not reversible with the approximation.
        return " ".join(["x" * int(n) for n in tokens])
