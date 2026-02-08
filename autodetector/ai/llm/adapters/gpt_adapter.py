"""
GPT Architecture Adapter using llama.cpp

Supports GPT-style models (Llama, Mistral, Qwen, etc.)
Uses llama-cpp-python for efficient local inference.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Generator
import logging

from .. import BaseModelAdapter, ModelConfig, GenerationResult, ModelArchitecture

logger = logging.getLogger(__name__)


class GPTAdapter(BaseModelAdapter):
    """
    Adapter for GPT-style decoder-only transformer models.
    
    Supports models in GGUF format via llama-cpp-python.
    Examples: Llama 2/3, Mistral, Qwen, Phi, Gemma
    """
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._llm = None
        self.architecture = ModelArchitecture.GPT
    
    def load(self) -> bool:
        """Load the model using llama-cpp-python."""
        try:
            from llama_cpp import Llama
            
            logger.info(f"Loading GPT model: {self.config.name}")
            logger.info(f"Model path: {self.config.model_path}")
            
            # Build load parameters
            load_params = {
                "model_path": self.config.model_path,
                "n_ctx": self.config.context_length,
                "n_threads": self.config.threads,
                "n_batch": self.config.batch_size,
                "verbose": False,
            }
            
            # GPU configuration
            if self.config.gpu_layers != 0:
                load_params["n_gpu_layers"] = self.config.gpu_layers
            
            # Seed
            if self.config.seed >= 0:
                load_params["seed"] = self.config.seed
            
            # Load the model
            self._llm = Llama(**load_params)
            self._is_loaded = True
            
            logger.info(f"Model loaded successfully")
            logger.info(f"Context length: {self.config.context_length}")
            
            return True
            
        except ImportError:
            logger.error("llama-cpp-python not installed. Run: pip install llama-cpp-python")
            return False
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False
    
    def unload(self) -> None:
        """Unload the model from memory."""
        if self._llm is not None:
            # llama-cpp doesn't have explicit unload, just delete reference
            del self._llm
            self._llm = None
            self._is_loaded = False
            logger.info(f"Model {self.config.name} unloaded")
    
    def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop_sequences: Optional[List[str]] = None,
        **kwargs
    ) -> GenerationResult:
        """Generate text using the loaded model."""
        if not self._is_loaded or self._llm is None:
            raise RuntimeError("Model not loaded")
        
        # Use config defaults if not specified
        max_tokens = max_tokens or self.config.max_tokens
        temperature = temperature if temperature is not None else self.config.temperature
        stop_sequences = stop_sequences or self.config.stop_sequences
        
        # Generation parameters
        gen_params = {
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": kwargs.get("top_p", self.config.top_p),
            "top_k": kwargs.get("top_k", self.config.top_k),
            "repeat_penalty": kwargs.get("repeat_penalty", self.config.repetition_penalty),
            "stop": stop_sequences,
            "stream": False,
        }
        
        # Add custom params
        for key, value in self.config.custom_params.items():
            if key not in gen_params:
                gen_params[key] = value
        
        # Generate
        start_time = time.time()
        result = self._llm(prompt, **gen_params)
        end_time = time.time()
        
        # Extract result
        text = result["choices"][0]["text"]
        tokens_generated = result["usage"]["completion_tokens"]
        prompt_tokens = result["usage"]["prompt_tokens"]
        
        # Calculate tokens per second
        elapsed = end_time - start_time
        tokens_per_second = tokens_generated / elapsed if elapsed > 0 else 0
        
        # Determine finish reason
        finish_reason = result["choices"][0].get("finish_reason", "stop")
        if finish_reason is None:
            finish_reason = "stop"
        
        return GenerationResult(
            text=text,
            tokens_generated=tokens_generated,
            tokens_per_second=tokens_per_second,
            prompt_tokens=prompt_tokens,
            finish_reason=finish_reason,
            model_name=self.config.name,
        )
    
    def generate_stream(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> Generator[str, None, None]:
        """Generate text in streaming mode."""
        if not self._is_loaded or self._llm is None:
            raise RuntimeError("Model not loaded")
        
        max_tokens = max_tokens or self.config.max_tokens
        temperature = temperature if temperature is not None else self.config.temperature
        
        gen_params = {
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": kwargs.get("top_p", self.config.top_p),
            "top_k": kwargs.get("top_k", self.config.top_k),
            "repeat_penalty": kwargs.get("repeat_penalty", self.config.repetition_penalty),
            "stream": True,
        }
        
        # Stream generation
        for chunk in self._llm(prompt, **gen_params):
            if "choices" in chunk and len(chunk["choices"]) > 0:
                delta = chunk["choices"][0].get("text", "")
                if delta:
                    yield delta
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information."""
        if not self._is_loaded or self._llm is None:
            return {"loaded": False}
        
        return {
            "loaded": True,
            "name": self.config.name,
            "architecture": self.config.architecture.value,
            "model_path": self.config.model_path,
            "context_length": self.config.context_length,
            "vocab_size": self._llm.n_vocab(),
            "embedding_size": getattr(self._llm, "n_embd", lambda: "unknown")(),
            "num_layers": getattr(self._llm, "n_layer", lambda: "unknown")(),
            "num_heads": getattr(self._llm, "n_head", lambda: "unknown")(),
        }
    
    def tokenize(self, text: str) -> List[int]:
        """Tokenize text into token IDs."""
        if not self._is_loaded or self._llm is None:
            raise RuntimeError("Model not loaded")
        return self._llm.tokenize(text.encode("utf-8"))
    
    def detokenize(self, tokens: List[int]) -> str:
        """Convert token IDs back to text."""
        if not self._is_loaded or self._llm is None:
            raise RuntimeError("Model not loaded")
        return self._llm.detokenize(tokens).decode("utf-8", errors="ignore")
    
    def format_prompt(
        self,
        instruction: str,
        input_text: str = "",
        system_prompt: Optional[str] = None,
        context: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Format prompt for chat/instruction following."""
        # Use llama-cpp's chat format if available
        if self._is_loaded and self._llm is not None:
            messages = []
            
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            if context:
                for msg in context:
                    messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    })
            
            # Add current instruction
            content = instruction
            if input_text:
                content += f"\n\nInput: {input_text}"
            messages.append({"role": "user", "content": content})
            
            # Use the model's chat handler
            try:
                return self._llm.create_chat_completion(
                    messages=messages,
                    stream=False,
                )["choices"][0]["message"]["content"]
            except:
                # Fallback to simple format
                pass
        
        # Simple fallback format
        parts = []
        if system_prompt:
            parts.append(f"<|system|>\n{system_prompt}\n")
        if context:
            for msg in context:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                parts.append(f"<|{role}|>\n{content}\n")
        parts.append(f"<|user|>\n{instruction}")
        if input_text:
            parts.append(f"\n{input_text}")
        parts.append("\n<|assistant|>\n")
        return "".join(parts)
