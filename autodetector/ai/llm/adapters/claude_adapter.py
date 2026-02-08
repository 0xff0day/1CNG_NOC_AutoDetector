"""
Claude Architecture Adapter

Supports Claude-style models with constitutional AI patterns.
Uses transformers library with custom attention mechanisms.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Generator
import logging

from .. import BaseModelAdapter, ModelConfig, GenerationResult, ModelArchitecture

logger = logging.getLogger(__name__)


class ClaudeAdapter(BaseModelAdapter):
    """
    Adapter for Claude-style models with constitutional AI.
    
    Designed for models emphasizing helpfulness, harmlessness, and honesty.
    Supports both transformers and custom inference backends.
    """
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._model = None
        self._tokenizer = None
        self.architecture = ModelArchitecture.CLAUDE
    
    def load(self) -> bool:
        """Load the model using transformers."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
            import torch
            
            logger.info(f"Loading Claude-style model: {self.config.name}")
            
            # Determine device
            device = "cuda" if torch.cuda.is_available() and self.config.gpu_layers != 0 else "cpu"
            
            # Load tokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.config.model_path,
                trust_remote_code=True,
            )
            
            # Set padding token if not set
            if self._tokenizer.pad_token is None:
                self._tokenizer.pad_token = self._tokenizer.eos_token
            
            # Build model load parameters
            load_params = {
                "pretrained_model_name_or_path": self.config.model_path,
                "trust_remote_code": True,
                "torch_dtype": torch.float16 if device == "cuda" else torch.float32,
            }
            
            # Quantization for memory efficiency
            if self.config.quantization.startswith("Q4") or self.config.quantization.startswith("Q8"):
                bnb_config = BitsAndBytesConfig(
                    load_in_4bit=self.config.quantization.startswith("Q4"),
                    load_in_8bit=self.config.quantization.startswith("Q8"),
                    bnb_4bit_compute_dtype=torch.float16,
                )
                load_params["quantization_config"] = bnb_config
                load_params["device_map"] = "auto"
            else:
                load_params["device_map"] = device
            
            # Load model
            self._model = AutoModelForCausalLM.from_pretrained(**load_params)
            self._is_loaded = True
            
            logger.info(f"Model loaded on {device}")
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
        
        # Force garbage collection
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
        
        # Use config defaults
        max_tokens = max_tokens or self.config.max_tokens
        temperature = temperature if temperature is not None else self.config.temperature
        
        # Tokenize input
        inputs = self._tokenizer(prompt, return_tensors="pt", padding=True)
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
            "repetition_penalty": kwargs.get("repetition_penalty", self.config.repetition_penalty),
            "do_sample": temperature > 0,
            "pad_token_id": self._tokenizer.pad_token_id,
            "eos_token_id": self._tokenizer.eos_token_id,
        }
        
        # Add stop sequences
        if stop_sequences:
            stop_token_ids = [self._tokenizer.encode(seq, add_special_tokens=False) for seq in stop_sequences]
            gen_kwargs["stopping_criteria"] = self._create_stopping_criteria(stop_token_ids)
        
        # Generate
        start_time = time.time()
        with torch.no_grad():
            outputs = self._model.generate(input_ids, **gen_kwargs)
        end_time = time.time()
        
        # Decode output
        generated_ids = outputs[0][prompt_tokens:]
        text = self._tokenizer.decode(generated_ids, skip_special_tokens=True)
        
        # Calculate metrics
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
        """Generate text in streaming mode using transformers generate."""
        if not self._is_loaded or self._model is None or self._tokenizer is None:
            raise RuntimeError("Model not loaded")
        
        import torch
        from transformers import TextIteratorStreamer
        from threading import Thread
        
        max_tokens = max_tokens or self.config.max_tokens
        temperature = temperature if temperature is not None else self.config.temperature
        
        # Tokenize
        inputs = self._tokenizer(prompt, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}
        
        # Create streamer
        streamer = TextIteratorStreamer(
            self._tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
        )
        
        # Generation kwargs
        gen_kwargs = {
            **inputs,
            "max_new_tokens": max_tokens,
            "temperature": temperature,
            "top_p": kwargs.get("top_p", self.config.top_p),
            "do_sample": temperature > 0,
            "streamer": streamer,
            "pad_token_id": self._tokenizer.pad_token_id,
        }
        
        # Run generation in separate thread
        thread = Thread(target=self._model.generate, kwargs=gen_kwargs)
        thread.start()
        
        # Yield tokens as they arrive
        for text in streamer:
            if text:
                yield text
        
        thread.join()
    
    def _create_stopping_criteria(self, stop_token_ids: List[List[int]]):
        """Create stopping criteria for generation."""
        from transformers import StoppingCriteria, StoppingCriteriaList
        
        class StopOnTokens(StoppingCriteria):
            def __init__(self, stop_ids):
                self.stop_ids = [torch.tensor(ids) for ids in stop_ids]
            
            def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:
                for stop_ids in self.stop_ids:
                    if input_ids[0][-len(stop_ids):].tolist() == stop_ids.tolist():
                        return True
                return False
        
        return StoppingCriteriaList([StopOnTokens(stop_token_ids)])
    
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
            "hidden_size": getattr(config, "hidden_size", config.d_model if hasattr(config, "d_model") else "unknown"),
            "num_layers": getattr(config, "num_hidden_layers", config.n_layer if hasattr(config, "n_layer") else "unknown"),
            "num_heads": getattr(config, "num_attention_heads", config.n_head if hasattr(config, "n_head") else "unknown"),
            "model_type": getattr(config, "model_type", "unknown"),
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
        """Format prompt using Claude's XML-style format."""
        # Claude uses XML-style tags for structure
        parts = []
        
        if system_prompt:
            parts.append(f"<system>\n{system_prompt}\n</system>\n\n")
        
        if context:
            for msg in context:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                parts.append(f"<{role}>\n{content}\n</{role}>\n\n")
        
        # Human/Assistant format
        parts.append(f"<human>\n{instruction}")
        if input_text:
            parts.append(f"\n\nInput: {input_text}")
        parts.append("\n</human>\n\n<assistant>\n")
        
        return "".join(parts)
