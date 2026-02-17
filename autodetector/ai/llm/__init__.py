"""
Local LLM Module for AI NOC System

This module provides local LLM capabilities for AI-driven network monitoring,
supporting multiple model architectures (GPT, Claude, Gemini) with training
capabilities for NOC-specific precision.
"""

from __future__ import annotations

import os
import json
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Generator, AsyncGenerator, Callable
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ModelArchitecture(Enum):
    """Supported LLM architectures."""
    GPT = "gpt"           # GPT-style (decoder-only transformer)
    CLAUDE = "claude"     # Claude-style (constitutional AI)
    GEMINI = "gemini"     # Gemini-style (multimodal transformer)
    OLLAMA = "ollama"     # Ollama-managed models via HTTP API


@dataclass
class ModelConfig:
    """Configuration for a local LLM model."""
    name: str
    architecture: ModelArchitecture
    model_path: str
    context_length: int = 8192
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    repetition_penalty: float = 1.1
    quantization: str = "Q4_K_M"  # llama.cpp quantization
    gpu_layers: int = -1  # -1 = all layers on GPU
    threads: int = 4
    batch_size: int = 512
    seed: int = -1
    stop_sequences: List[str] = field(default_factory=list)
    custom_params: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "architecture": self.architecture.value,
            "model_path": self.model_path,
            "context_length": self.context_length,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "repetition_penalty": self.repetition_penalty,
            "quantization": self.quantization,
            "gpu_layers": self.gpu_layers,
            "threads": self.threads,
            "batch_size": self.batch_size,
            "seed": self.seed,
            "stop_sequences": self.stop_sequences,
            "custom_params": self.custom_params,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelConfig":
        return cls(
            name=data["name"],
            architecture=ModelArchitecture(data["architecture"]),
            model_path=data["model_path"],
            context_length=data.get("context_length", 8192),
            max_tokens=data.get("max_tokens", 2048),
            temperature=data.get("temperature", 0.7),
            top_p=data.get("top_p", 0.9),
            top_k=data.get("top_k", 40),
            repetition_penalty=data.get("repetition_penalty", 1.1),
            quantization=data.get("quantization", "Q4_K_M"),
            gpu_layers=data.get("gpu_layers", -1),
            threads=data.get("threads", 4),
            batch_size=data.get("batch_size", 512),
            seed=data.get("seed", -1),
            stop_sequences=data.get("stop_sequences", []),
            custom_params=data.get("custom_params", {}),
        )


@dataclass
class GenerationResult:
    """Result from LLM generation."""
    text: str
    tokens_generated: int
    tokens_per_second: float
    prompt_tokens: int
    finish_reason: str
    model_name: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrainingExample:
    """Single training example for fine-tuning."""
    instruction: str
    input_text: str
    output_text: str
    system_prompt: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "instruction": self.instruction,
            "input": self.input_text,
            "output": self.output_text,
            "system": self.system_prompt,
            "metadata": self.metadata,
        }


class BaseModelAdapter(ABC):
    """Abstract base class for model adapters."""
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self._model = None
        self._tokenizer = None
        self._is_loaded = False
    
    @property
    def is_loaded(self) -> bool:
        return self._is_loaded
    
    @abstractmethod
    def load(self) -> bool:
        """Load the model into memory. Returns True if successful."""
        pass
    
    @abstractmethod
    def unload(self) -> None:
        """Unload the model from memory."""
        pass
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop_sequences: Optional[List[str]] = None,
        **kwargs
    ) -> GenerationResult:
        """Generate text from the model."""
        pass
    
    @abstractmethod
    def generate_stream(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> Generator[str, None, None]:
        """Generate text in streaming mode."""
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model."""
        pass
    
    @abstractmethod
    def tokenize(self, text: str) -> List[int]:
        """Tokenize text into token IDs."""
        pass
    
    @abstractmethod
    def detokenize(self, tokens: List[int]) -> str:
        """Convert token IDs back to text."""
        pass
    
    def format_prompt(
        self,
        instruction: str,
        input_text: str = "",
        system_prompt: Optional[str] = None,
        context: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Format a prompt according to the model's chat template."""
        # Default implementation - subclasses should override
        prompt_parts = []
        if system_prompt:
            prompt_parts.append(f"System: {system_prompt}\n")
        if context:
            for msg in context:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                prompt_parts.append(f"{role.capitalize()}: {content}\n")
        prompt_parts.append(f"Instruction: {instruction}\n")
        if input_text:
            prompt_parts.append(f"Input: {input_text}\n")
        prompt_parts.append("Output: ")
        return "".join(prompt_parts)
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenize(text))
    
    def estimate_memory_usage(self) -> Dict[str, float]:
        """Estimate memory usage for the model."""
        # Rough estimation based on model size and quantization
        file_size = os.path.getsize(self.config.model_path) if os.path.exists(self.config.model_path) else 0
        return {
            "model_file_gb": file_size / (1024 ** 3),
            "estimated_ram_gb": file_size / (1024 ** 3) * 1.2,  # 20% overhead
            "estimated_vram_gb": file_size / (1024 ** 3) * 1.1 if self.config.gpu_layers != 0 else 0,
        }


class LLMRegistry:
    """Registry for managing available models and adapters."""
    
    _adapters: Dict[ModelArchitecture, type] = {}
    _models: Dict[str, ModelConfig] = {}
    _loaded_models: Dict[str, BaseModelAdapter] = {}
    
    @classmethod
    def register_adapter(cls, architecture: ModelArchitecture, adapter_class: type) -> None:
        """Register a model adapter for an architecture."""
        cls._adapters[architecture] = adapter_class
        logger.info(f"Registered adapter {adapter_class.__name__} for {architecture.value}")
    
    @classmethod
    def get_adapter_class(cls, architecture: ModelArchitecture) -> Optional[type]:
        """Get the adapter class for an architecture."""
        return cls._adapters.get(architecture)
    
    @classmethod
    def register_model(cls, config: ModelConfig) -> None:
        """Register a model configuration."""
        cls._models[config.name] = config
        logger.info(f"Registered model: {config.name}")
    
    @classmethod
    def get_model_config(cls, name: str) -> Optional[ModelConfig]:
        """Get a model configuration by name."""
        return cls._models.get(name)
    
    @classmethod
    def list_models(cls) -> List[str]:
        """List all registered model names."""
        return list(cls._models.keys())
    
    @classmethod
    def load_model(cls, name: str) -> Optional[BaseModelAdapter]:
        """Load a model by name."""
        if name in cls._loaded_models:
            return cls._loaded_models[name]
        
        config = cls.get_model_config(name)
        if not config:
            logger.error(f"Model {name} not found in registry")
            return None
        
        adapter_class = cls.get_adapter_class(config.architecture)
        if not adapter_class:
            logger.error(f"No adapter for architecture {config.architecture.value}")
            return None
        
        adapter = adapter_class(config)
        if adapter.load():
            cls._loaded_models[name] = adapter
            return adapter
        return None
    
    @classmethod
    def unload_model(cls, name: str) -> bool:
        """Unload a model by name."""
        if name in cls._loaded_models:
            cls._loaded_models[name].unload()
            del cls._loaded_models[name]
            return True
        return False
    
    @classmethod
    def get_loaded_model(cls, name: str) -> Optional[BaseModelAdapter]:
        """Get a loaded model by name."""
        return cls._loaded_models.get(name)
    
    @classmethod
    def list_loaded_models(cls) -> List[str]:
        """List names of currently loaded models."""
        return list(cls._loaded_models.keys())


# Import adapters after base class definition to avoid circular imports
from .adapters.gpt_adapter import GPTAdapter
from .adapters.claude_adapter import ClaudeAdapter
from .adapters.gemini_adapter import GeminiAdapter
from .adapters.ollama_adapter import OllamaAdapter

# Register default adapters
LLMRegistry.register_adapter(ModelArchitecture.GPT, GPTAdapter)
LLMRegistry.register_adapter(ModelArchitecture.CLAUDE, ClaudeAdapter)
LLMRegistry.register_adapter(ModelArchitecture.GEMINI, GeminiAdapter)
LLMRegistry.register_adapter(ModelArchitecture.OLLAMA, OllamaAdapter)
