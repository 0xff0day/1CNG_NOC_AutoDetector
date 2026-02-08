"""
Gemini Architecture Adapter

Supports Gemini-style multimodal models.
Designed for efficient inference with multimodal capabilities.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Generator
import logging

from .. import BaseModelAdapter, ModelConfig, GenerationResult, ModelArchitecture

logger = logging.getLogger(__name__)


class GeminiAdapter(BaseModelAdapter):
    """
    Adapter for Gemini-style multimodal models.
    
    Optimized for efficient inference and multimodal understanding.
    Can handle text, images, and structured data.
    """
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._model = None
        self._tokenizer = None
        self.architecture = ModelArchitecture.GEMINI
    
    def load(self) -> bool:
        """Load the model."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, AutoProcessor
            import torch
            
            logger.info(f"Loading Gemini-style model: {self.config.name}")
            
            # Try to load as multimodal model
            try:
                self._processor = AutoProcessor.from_pretrained(
                    self.config.model_path,
                    trust_remote_code=True,
                )
                self._tokenizer = self._processor.tokenizer
            except:
                # Fall back to tokenizer-only
                self._tokenizer = AutoTokenizer.from_pretrained(
                    self.config.model_path,
                    trust_remote_code=True,
                )
                self._processor = None
            
            # Load model
            device = "cuda" if torch.cuda.is_available() and self.config.gpu_layers != 0 else "cpu"
            
            load_params = {
                "pretrained_model_name_or_path": self.config.model_path,
                "trust_remote_code": True,
                "torch_dtype": torch.float16 if device == "cuda" else torch.float32,
                "device_map": "auto" if device == "cuda" else None,
            }
            
            self._model = AutoModelForCausalLM.from_pretrained(**load_params)
            self._is_loaded = True
            
            logger.info(f"Gemini model loaded on {device}")
            return True
            
        except ImportError:
            logger.error("transformers not installed. Run: pip install transformers torch")
            return False
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False
    
    def unload(self) -> None:
        """Unload the model from memory."""
        import gc
        import torch
        
        if self._model is not None:
            del self._model
            self._model = None
        if self._tokenizer is not None:
            del self._tokenizer
            self._tokenizer = None
        if hasattr(self, '_processor') and self._processor is not None:
            del self._processor
            self._processor = None
        
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
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
        if not self._is_loaded or self._model is None or self._tokenizer is None:
            raise RuntimeError("Model not loaded")
        
        import torch
        
        max_tokens = max_tokens or self.config.max_tokens
        temperature = temperature if temperature is not None else self.config.temperature
        
        # Tokenize
        inputs = self._tokenizer(prompt, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}
        
        input_ids = inputs["input_ids"]
        prompt_tokens = input_ids.shape[1]
        
        # Generation parameters
        gen_kwargs = {
            "max_new_tokens": max_tokens,
            "temperature": temperature,
            "top_p": kwargs.get("top_p", self.config.top_p),
            "top_k": kwargs.get("top_k", self.config.top_k),
            "do_sample": temperature > 0,
            "pad_token_id": self._tokenizer.pad_token_id,
        }
        
        # Generate
        start_time = time.time()
        with torch.no_grad():
            outputs = self._model.generate(input_ids, **gen_kwargs)
        end_time = time.time()
        
        # Decode
        generated_ids = outputs[0][prompt_tokens:]
        text = self._tokenizer.decode(generated_ids, skip_special_tokens=True)
        
        tokens_generated = len(generated_ids)
        elapsed = end_time - start_time
        tokens_per_second = tokens_generated / elapsed if elapsed > 0 else 0
        
        return GenerationResult(
            text=text,
            tokens_generated=tokens_generated,
            tokens_per_second=tokens_per_second,
            prompt_tokens=prompt_tokens,
            finish_reason="stop",
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
        if not self._is_loaded or self._model is None or self._tokenizer is None:
            raise RuntimeError("Model not loaded")
        
        import torch
        from transformers import TextIteratorStreamer
        from threading import Thread
        
        max_tokens = max_tokens or self.config.max_tokens
        temperature = temperature if temperature is not None else self.config.temperature
        
        inputs = self._tokenizer(prompt, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}
        
        streamer = TextIteratorStreamer(
            self._tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
        )
        
        gen_kwargs = {
            **inputs,
            "max_new_tokens": max_tokens,
            "temperature": temperature,
            "streamer": streamer,
            "pad_token_id": self._tokenizer.pad_token_id,
        }
        
        thread = Thread(target=self._model.generate, kwargs=gen_kwargs)
        thread.start()
        
        for text in streamer:
            if text:
                yield text
        
        thread.join()
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information."""
        if not self._is_loaded or self._model is None:
            return {"loaded": False}
        
        config = self._model.config
        return {
            "loaded": True,
            "name": self.config.name,
            "architecture": self.config.architecture.value,
            "model_path": self.config.model_path,
            "context_length": self.config.context_length,
            "vocab_size": config.vocab_size,
            "hidden_size": getattr(config, "hidden_size", "unknown"),
            "num_layers": getattr(config, "num_hidden_layers", "unknown"),
            "num_heads": getattr(config, "num_attention_heads", "unknown"),
        }
    
    def tokenize(self, text: str) -> List[int]:
        """Tokenize text into token IDs."""
        if not self._is_loaded or self._tokenizer is None:
            raise RuntimeError("Model not loaded")
        return self._tokenizer.encode(text, add_special_tokens=True)
    
    def detokenize(self, tokens: List[int]) -> str:
        """Convert token IDs back to text."""
        if not self._is_loaded or self._tokenizer is None:
            raise RuntimeError("Model not loaded")
        return self._tokenizer.decode(tokens, skip_special_tokens=True)
    
    def format_prompt(
        self,
        instruction: str,
        input_text: str = "",
        system_prompt: Optional[str] = None,
        context: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Format prompt using Gemini's style."""
        # Gemini uses a structured format with roles
        parts = []
        
        if system_prompt:
            parts.append(f"system: {system_prompt}\n")
        
        if context:
            for msg in context:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                parts.append(f"{role}: {content}\n")
        
        parts.append(f"user: {instruction}")
        if input_text:
            parts.append(f"\n{input_text}")
        parts.append("\nmodel: ")
        
        return "".join(parts)
