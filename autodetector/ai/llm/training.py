"""
LLM Training and Fine-tuning Pipeline for AI NOC

Provides capabilities for training custom models on NOC-specific data.
Supports LoRA, QLoRA, and full fine-tuning methods.
"""

from __future__ import annotations

import os
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Iterator
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Configuration for training/fine-tuning."""
    # Model settings
    base_model_path: str
    output_dir: str
    architecture: str = "gpt"  # gpt, claude, gemini
    
    # Training method
    method: str = "lora"  # lora, qlora, full
    
    # LoRA settings
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    lora_target_modules: List[str] = field(default_factory=lambda: ["q_proj", "v_proj", "k_proj", "o_proj"])
    
    # Training hyperparameters
    num_epochs: int = 3
    batch_size: int = 4
    gradient_accumulation_steps: int = 4
    learning_rate: float = 2e-4
    max_seq_length: int = 2048
    warmup_steps: int = 100
    save_steps: int = 500
    eval_steps: int = 500
    logging_steps: int = 10
    
    # Optimization
    optimizer: str = "adamw_torch"
    lr_scheduler: str = "cosine"
    weight_decay: float = 0.001
    max_grad_norm: float = 0.3
    
    # Data
    train_data_path: str = ""
    eval_data_path: str = ""
    validation_split: float = 0.1
    
    # Hardware
    fp16: bool = True
    bf16: bool = False
    gradient_checkpointing: bool = True
    max_memory_gb: int = 16
    
    # NOC-specific
    system_prompt: str = "You are an expert Network Operations Center (NOC) AI assistant. Analyze network issues and provide actionable recommendations."
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_model_path": self.base_model_path,
            "output_dir": self.output_dir,
            "architecture": self.architecture,
            "method": self.method,
            "lora_r": self.lora_r,
            "lora_alpha": self.lora_alpha,
            "lora_dropout": self.lora_dropout,
            "lora_target_modules": self.lora_target_modules,
            "num_epochs": self.num_epochs,
            "batch_size": self.batch_size,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "learning_rate": self.learning_rate,
            "max_seq_length": self.max_seq_length,
            "warmup_steps": self.warmup_steps,
            "save_steps": self.save_steps,
            "eval_steps": self.eval_steps,
            "logging_steps": self.logging_steps,
            "optimizer": self.optimizer,
            "lr_scheduler": self.lr_scheduler,
            "weight_decay": self.weight_decay,
            "max_grad_norm": self.max_grad_norm,
            "train_data_path": self.train_data_path,
            "eval_data_path": self.eval_data_path,
            "validation_split": self.validation_split,
            "fp16": self.fp16,
            "bf16": self.bf16,
            "gradient_checkpointing": self.gradient_checkpointing,
            "max_memory_gb": self.max_memory_gb,
            "system_prompt": self.system_prompt,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrainingConfig":
        return cls(**data)
    
    def save(self, path: str) -> None:
        """Save config to JSON file."""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: str) -> "TrainingConfig":
        """Load config from JSON file."""
        with open(path, 'r') as f:
            return cls.from_dict(json.load(f))


@dataclass
class TrainingMetrics:
    """Training metrics for monitoring progress."""
    step: int
    epoch: float
    loss: float
    learning_rate: float
    perplexity: Optional[float] = None
    eval_loss: Optional[float] = None
    tokens_per_second: float = 0.0
    gpu_memory_mb: float = 0.0
    timestamp: float = field(default_factory=time.time)


class TrainingCallback:
    """Callback for training events."""
    
    def on_training_start(self, config: TrainingConfig) -> None:
        """Called when training starts."""
        pass
    
    def on_training_end(self, metrics: Dict[str, Any]) -> None:
        """Called when training ends."""
        pass
    
    def on_step_end(self, metrics: TrainingMetrics) -> None:
        """Called at the end of each step."""
        pass
    
    def on_epoch_end(self, epoch: int, metrics: Dict[str, Any]) -> None:
        """Called at the end of each epoch."""
        pass
    
    def on_evaluate(self, eval_metrics: Dict[str, Any]) -> None:
        """Called during evaluation."""
        pass
    
    def on_save(self, checkpoint_path: str) -> None:
        """Called when a checkpoint is saved."""
        pass


class NOCModelTrainer:
    """
    Trainer for fine-tuning LLMs on NOC-specific data.
    
    Supports multiple training methods:
    - LoRA: Low-Rank Adaptation (memory efficient)
    - QLoRA: Quantized LoRA (even more memory efficient)
    - Full: Full fine-tuning (highest quality, most memory)
    """
    
    def __init__(self, config: TrainingConfig):
        self.config = config
        self.callbacks: List[TrainingCallback] = []
        self._is_training = False
        self._current_step = 0
        self._trainer = None
    
    def add_callback(self, callback: TrainingCallback) -> None:
        """Add a training callback."""
        self.callbacks.append(callback)
    
    def prepare_data(self, examples: List[Dict[str, str]]) -> str:
        """
        Prepare training data from examples.
        
        Examples should have keys:
        - instruction: The task description
        - input: Input context (optional)
        - output: Expected output
        """
        output_path = os.path.join(self.config.output_dir, "train_data.jsonl")
        os.makedirs(self.config.output_dir, exist_ok=True)
        
        with open(output_path, 'w') as f:
            for ex in examples:
                # Format according to architecture
                if self.config.architecture == "gpt":
                    formatted = self._format_gpt_example(ex)
                elif self.config.architecture == "claude":
                    formatted = self._format_claude_example(ex)
                elif self.config.architecture == "gemini":
                    formatted = self._format_gemini_example(ex)
                else:
                    formatted = self._format_default_example(ex)
                
                f.write(json.dumps(formatted) + '\n')
        
        self.config.train_data_path = output_path
        logger.info(f"Prepared {len(examples)} training examples at {output_path}")
        return output_path
    
    def _format_gpt_example(self, ex: Dict[str, str]) -> Dict[str, str]:
        """Format example for GPT-style training."""
        instruction = ex.get("instruction", "")
        input_text = ex.get("input", "")
        output = ex.get("output", "")
        
        if input_text:
            prompt = f"### Instruction:\n{instruction}\n\n### Input:\n{input_text}\n\n### Response:\n"
        else:
            prompt = f"### Instruction:\n{instruction}\n\n### Response:\n"
        
        return {
            "text": prompt + output + "</s>"
        }
    
    def _format_claude_example(self, ex: Dict[str, str]) -> Dict[str, str]:
        """Format example for Claude-style training."""
        instruction = ex.get("instruction", "")
        input_text = ex.get("input", "")
        output = ex.get("output", "")
        
        parts = [f"<human>\n{instruction}"]
        if input_text:
            parts.append(f"\n\n{input_text}")
        parts.append("\n</human>\n\n<assistant>\n")
        parts.append(output)
        parts.append("\n</assistant>")
        
        return {"text": "".join(parts)}
    
    def _format_gemini_example(self, ex: Dict[str, str]) -> Dict[str, str]:
        """Format example for Gemini-style training."""
        instruction = ex.get("instruction", "")
        input_text = ex.get("input", "")
        output = ex.get("output", "")
        
        parts = [f"user: {instruction}"]
        if input_text:
            parts.append(f"\n{input_text}")
        parts.append(f"\nmodel: {output}")
        
        return {"text": "".join(parts)}
    
    def _format_default_example(self, ex: Dict[str, str]) -> Dict[str, str]:
        """Default formatting."""
        return ex
    
    def train(self) -> Dict[str, Any]:
        """
        Execute training pipeline.
        
        Returns training metrics and checkpoint paths.
        """
        if not self.config.train_data_path:
            raise ValueError("No training data provided. Call prepare_data() first.")
        
        self._is_training = True
        
        # Notify callbacks
        for cb in self.callbacks:
            cb.on_training_start(self.config)
        
        try:
            if self.config.method == "lora":
                results = self._train_lora()
            elif self.config.method == "qlora":
                results = self._train_qlora()
            elif self.config.method == "full":
                results = self._train_full()
            else:
                raise ValueError(f"Unknown training method: {self.config.method}")
            
            # Notify callbacks
            for cb in self.callbacks:
                cb.on_training_end(results)
            
            return results
            
        finally:
            self._is_training = False
    
    def _train_lora(self) -> Dict[str, Any]:
        """Train using LoRA method."""
        try:
            from transformers import (
                AutoModelForCausalLM,
                AutoTokenizer,
                TrainingArguments,
                Trainer,
                DataCollatorForLanguageModeling,
            )
            from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
            from datasets import load_dataset
            import torch
            
            logger.info("Starting LoRA training...")
            
            # Load tokenizer
            tokenizer = AutoTokenizer.from_pretrained(self.config.base_model_path)
            tokenizer.pad_token = tokenizer.eos_token
            
            # Load model
            model = AutoModelForCausalLM.from_pretrained(
                self.config.base_model_path,
                torch_dtype=torch.float16,
                device_map="auto",
            )
            
            # Prepare model for training
            model = prepare_model_for_kbit_training(model)
            
            # Configure LoRA
            lora_config = LoraConfig(
                r=self.config.lora_r,
                lora_alpha=self.config.lora_alpha,
                target_modules=self.config.lora_target_modules,
                lora_dropout=self.config.lora_dropout,
                bias="none",
                task_type="CAUSAL_LM",
            )
            
            model = get_peft_model(model, lora_config)
            model.print_trainable_parameters()
            
            # Load dataset
            dataset = load_dataset('json', data_files=self.config.train_data_path, split='train')
            
            # Tokenize
            def tokenize_function(examples):
                return tokenizer(
                    examples["text"],
                    truncation=True,
                    max_length=self.config.max_seq_length,
                    padding="max_length",
                )
            
            tokenized_dataset = dataset.map(tokenize_function, batched=True)
            
            # Training arguments
            training_args = TrainingArguments(
                output_dir=self.config.output_dir,
                num_train_epochs=self.config.num_epochs,
                per_device_train_batch_size=self.config.batch_size,
                gradient_accumulation_steps=self.config.gradient_accumulation_steps,
                optim=self.config.optimizer,
                save_steps=self.config.save_steps,
                logging_steps=self.config.logging_steps,
                learning_rate=self.config.learning_rate,
                weight_decay=self.config.weight_decay,
                fp16=self.config.fp16,
                bf16=self.config.bf16,
                max_grad_norm=self.config.max_grad_norm,
                max_steps=-1,
                warmup_ratio=0.03,
                group_by_length=True,
                lr_scheduler_type=self.config.lr_scheduler,
                report_to="none",
                gradient_checkpointing=self.config.gradient_checkpointing,
            )
            
            # Data collator
            data_collator = DataCollatorForLanguageModeling(tokenizer, mlm=False)
            
            # Trainer
            trainer = Trainer(
                model=model,
                train_dataset=tokenized_dataset,
                args=training_args,
                data_collator=data_collator,
            )
            
            # Train
            trainer.train()
            
            # Save
            model.save_pretrained(os.path.join(self.config.output_dir, "final"))
            tokenizer.save_pretrained(os.path.join(self.config.output_dir, "final"))
            
            return {
                "status": "success",
                "method": "lora",
                "output_dir": self.config.output_dir,
                "final_checkpoint": os.path.join(self.config.output_dir, "final"),
            }
            
        except ImportError as e:
            logger.error(f"Missing dependency: {e}")
            raise
        except Exception as e:
            logger.error(f"Training failed: {e}")
            raise
    
    def _train_qlora(self) -> Dict[str, Any]:
        """Train using QLoRA (quantized LoRA) method."""
        try:
            from transformers import (
                AutoModelForCausalLM,
                AutoTokenizer,
                BitsAndBytesConfig,
                TrainingArguments,
                Trainer,
                DataCollatorForLanguageModeling,
            )
            from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
            from datasets import load_dataset
            import torch
            
            logger.info("Starting QLoRA training...")
            
            # Quantization config
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
            )
            
            # Load tokenizer
            tokenizer = AutoTokenizer.from_pretrained(self.config.base_model_path)
            tokenizer.pad_token = tokenizer.eos_token
            
            # Load quantized model
            model = AutoModelForCausalLM.from_pretrained(
                self.config.base_model_path,
                quantization_config=bnb_config,
                device_map="auto",
            )
            
            # Prepare model
            model = prepare_model_for_kbit_training(model)
            
            # Configure LoRA
            lora_config = LoraConfig(
                r=self.config.lora_r,
                lora_alpha=self.config.lora_alpha,
                target_modules=self.config.lora_target_modules,
                lora_dropout=self.config.lora_dropout,
                bias="none",
                task_type="CAUSAL_LM",
            )
            
            model = get_peft_model(model, lora_config)
            model.print_trainable_parameters()
            
            # Load dataset
            dataset = load_dataset('json', data_files=self.config.train_data_path, split='train')
            
            # Tokenize
            def tokenize_function(examples):
                return tokenizer(
                    examples["text"],
                    truncation=True,
                    max_length=self.config.max_seq_length,
                    padding="max_length",
                )
            
            tokenized_dataset = dataset.map(tokenize_function, batched=True)
            
            # Training arguments
            training_args = TrainingArguments(
                output_dir=self.config.output_dir,
                num_train_epochs=self.config.num_epochs,
                per_device_train_batch_size=self.config.batch_size,
                gradient_accumulation_steps=self.config.gradient_accumulation_steps,
                optim="paged_adamw_8bit",  # Optimized for QLoRA
                save_steps=self.config.save_steps,
                logging_steps=self.config.logging_steps,
                learning_rate=self.config.learning_rate,
                weight_decay=self.config.weight_decay,
                fp16=True,
                max_grad_norm=self.config.max_grad_norm,
                warmup_ratio=0.03,
                group_by_length=True,
                lr_scheduler_type=self.config.lr_scheduler,
                report_to="none",
            )
            
            # Data collator
            data_collator = DataCollatorForLanguageModeling(tokenizer, mlm=False)
            
            # Trainer
            trainer = Trainer(
                model=model,
                train_dataset=tokenized_dataset,
                args=training_args,
                data_collator=data_collator,
            )
            
            # Train
            trainer.train()
            
            # Save
            model.save_pretrained(os.path.join(self.config.output_dir, "final"))
            tokenizer.save_pretrained(os.path.join(self.config.output_dir, "final"))
            
            return {
                "status": "success",
                "method": "qlora",
                "output_dir": self.config.output_dir,
                "final_checkpoint": os.path.join(self.config.output_dir, "final"),
            }
            
        except ImportError as e:
            logger.error(f"Missing dependency: {e}")
            raise
        except Exception as e:
            logger.error(f"Training failed: {e}")
            raise
    
    def _train_full(self) -> Dict[str, Any]:
        """Train using full fine-tuning."""
        logger.warning("Full fine-tuning requires significant GPU memory. Ensure you have sufficient VRAM.")
        
        # For full fine-tuning, we use the same code as LoRA but without the PEFT wrapper
        # This is a simplified version
        try:
            from transformers import (
                AutoModelForCausalLM,
                AutoTokenizer,
                TrainingArguments,
                Trainer,
                DataCollatorForLanguageModeling,
            )
            from datasets import load_dataset
            import torch
            
            logger.info("Starting full fine-tuning...")
            
            # Load tokenizer
            tokenizer = AutoTokenizer.from_pretrained(self.config.base_model_path)
            tokenizer.pad_token = tokenizer.eos_token
            
            # Load model (no quantization for full fine-tuning)
            model = AutoModelForCausalLM.from_pretrained(
                self.config.base_model_path,
                torch_dtype=torch.float16,
                device_map="auto",
            )
            
            # Enable gradient checkpointing to save memory
            if self.config.gradient_checkpointing:
                model.gradient_checkpointing_enable()
            
            # Load dataset
            dataset = load_dataset('json', data_files=self.config.train_data_path, split='train')
            
            # Tokenize
            def tokenize_function(examples):
                return tokenizer(
                    examples["text"],
                    truncation=True,
                    max_length=self.config.max_seq_length,
                    padding="max_length",
                )
            
            tokenized_dataset = dataset.map(tokenize_function, batched=True)
            
            # Training arguments
            training_args = TrainingArguments(
                output_dir=self.config.output_dir,
                num_train_epochs=self.config.num_epochs,
                per_device_train_batch_size=self.config.batch_size,
                gradient_accumulation_steps=self.config.gradient_accumulation_steps,
                optim=self.config.optimizer,
                save_steps=self.config.save_steps,
                logging_steps=self.config.logging_steps,
                learning_rate=self.config.learning_rate,
                weight_decay=self.config.weight_decay,
                fp16=self.config.fp16,
                bf16=self.config.bf16,
                max_grad_norm=self.config.max_grad_norm,
                warmup_ratio=0.03,
                group_by_length=True,
                lr_scheduler_type=self.config.lr_scheduler,
                report_to="none",
            )
            
            # Data collator
            data_collator = DataCollatorForLanguageModeling(tokenizer, mlm=False)
            
            # Trainer
            trainer = Trainer(
                model=model,
                train_dataset=tokenized_dataset,
                args=training_args,
                data_collator=data_collator,
            )
            
            # Train
            trainer.train()
            
            # Save
            model.save_pretrained(os.path.join(self.config.output_dir, "final"))
            tokenizer.save_pretrained(os.path.join(self.config.output_dir, "final"))
            
            return {
                "status": "success",
                "method": "full",
                "output_dir": self.config.output_dir,
                "final_checkpoint": os.path.join(self.config.output_dir, "final"),
            }
            
        except Exception as e:
            logger.error(f"Training failed: {e}")
            raise
    
    def stop(self) -> None:
        """Stop training."""
        self._is_training = False
        logger.info("Training stop requested")
    
    @property
    def is_training(self) -> bool:
        """Check if training is in progress."""
        return self._is_training


class ProgressCallback(TrainingCallback):
    """Callback that logs training progress."""
    
    def __init__(self, log_interval: int = 10):
        self.log_interval = log_interval
        self.start_time = None
    
    def on_training_start(self, config: TrainingConfig) -> None:
        self.start_time = time.time()
        logger.info(f"Training started: {config.base_model_path}")
        logger.info(f"Method: {config.method}, Epochs: {config.num_epochs}")
    
    def on_step_end(self, metrics: TrainingMetrics) -> None:
        if metrics.step % self.log_interval == 0:
            logger.info(
                f"Step {metrics.step} | Epoch {metrics.epoch:.2f} | "
                f"Loss: {metrics.loss:.4f} | LR: {metrics.learning_rate:.2e} | "
                f"Tokens/s: {metrics.tokens_per_second:.1f}"
            )
    
    def on_training_end(self, metrics: Dict[str, Any]) -> None:
        elapsed = time.time() - self.start_time if self.start_time else 0
        logger.info(f"Training completed in {elapsed/60:.1f} minutes")
        logger.info(f"Output: {metrics.get('output_dir')}")
