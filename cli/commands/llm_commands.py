"""
LLM CLI Commands for NOC System

Provides command-line interface for:
- Model management (load, unload, list)
- Training and fine-tuning
- Inference and testing
- Dataset generation
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from ..llm import (
    LLMRegistry, 
    ModelConfig, 
    ModelArchitecture,
    NOCModelTrainer,
    TrainingConfig,
    NOCTrainingDataBuilder,
)


def add_llm_subparser(subparsers):
    """Add LLM-related subcommands to the CLI."""
    llm_parser = subparsers.add_parser(
        "llm", 
        help="Local LLM management and training",
        description="Manage local LLM models for AI NOC operations"
    )
    llm_subparsers = llm_parser.add_subparsers(dest="llm_command", help="LLM commands")
    
    # Model list command
    list_parser = llm_subparsers.add_parser("list", help="List registered models")
    list_parser.add_argument("--loaded", action="store_true", help="Show only loaded models")
    
    # Model load command
    load_parser = llm_subparsers.add_parser("load", help="Load a model")
    load_parser.add_argument("name", help="Model name to load")
    
    # Model unload command
    unload_parser = llm_subparsers.add_parser("unload", help="Unload a model")
    unload_parser.add_argument("name", help="Model name to unload")
    
    # Model info command
    info_parser = llm_subparsers.add_parser("info", help="Show model information")
    info_parser.add_argument("name", help="Model name")
    
    # Register model command
    register_parser = llm_subparsers.add_parser("register", help="Register a new model")
    register_parser.add_argument("--name", required=True, help="Model name")
    register_parser.add_argument("--path", required=True, help="Path to model file")
    register_parser.add_argument("--architecture", required=True, 
                                choices=["gpt", "claude", "gemini"],
                                help="Model architecture")
    register_parser.add_argument("--context-length", type=int, default=8192)
    register_parser.add_argument("--quantization", default="Q4_K_M")
    
    # Generate command
    generate_parser = llm_subparsers.add_parser("generate", help="Generate text")
    generate_parser.add_argument("--model", required=True, help="Model name")
    generate_parser.add_argument("--prompt", "-p", required=True, help="Input prompt")
    generate_parser.add_argument("--max-tokens", type=int, default=512)
    generate_parser.add_argument("--temperature", type=float, default=0.7)
    generate_parser.add_argument("--stream", action="store_true", help="Stream output")
    
    # Training commands
    train_parser = llm_subparsers.add_parser("train", help="Train/fine-tune a model")
    train_parser.add_argument("--base-model", required=True, help="Base model path")
    train_parser.add_argument("--output-dir", required=True, help="Output directory")
    train_parser.add_argument("--architecture", default="gpt",
                             choices=["gpt", "claude", "gemini"])
    train_parser.add_argument("--method", default="lora",
                             choices=["lora", "qlora", "full"])
    train_parser.add_argument("--data-path", help="Training data path")
    train_parser.add_argument("--epochs", type=int, default=3)
    train_parser.add_argument("--batch-size", type=int, default=4)
    train_parser.add_argument("--learning-rate", type=float, default=2e-4)
    train_parser.add_argument("--lora-r", type=int, default=16)
    train_parser.add_argument("--lora-alpha", type=int, default=32)
    
    # Dataset generation
    dataset_parser = llm_subparsers.add_parser("dataset", help="Generate NOC training dataset")
    dataset_parser.add_argument("--output-dir", required=True, help="Output directory")
    dataset_parser.add_argument("--train-count", type=int, default=1000)
    dataset_parser.add_argument("--eval-count", type=int, default=200)
    dataset_parser.add_argument("--format", default="jsonl",
                               choices=["jsonl", "alpaca", "sharegpt", "all"])
    
    # Benchmark command
    benchmark_parser = llm_subparsers.add_parser("benchmark", help="Benchmark model performance")
    benchmark_parser.add_argument("--model", required=True, help="Model name")
    benchmark_parser.add_argument("--iterations", type=int, default=10)
    
    return llm_parser


def handle_llm_command(args) -> int:
    """Handle LLM subcommands."""
    command = args.llm_command
    
    if command == "list":
        return _cmd_list(args)
    elif command == "load":
        return _cmd_load(args)
    elif command == "unload":
        return _cmd_unload(args)
    elif command == "info":
        return _cmd_info(args)
    elif command == "register":
        return _cmd_register(args)
    elif command == "generate":
        return _cmd_generate(args)
    elif command == "train":
        return _cmd_train(args)
    elif command == "dataset":
        return _cmd_dataset(args)
    elif command == "benchmark":
        return _cmd_benchmark(args)
    else:
        print("Unknown LLM command. Use --help for available commands.")
        return 1


def _cmd_list(args) -> int:
    """List models command."""
    if args.loaded:
        models = LLMRegistry.list_loaded_models()
        print("Loaded Models:")
        for name in models:
            print(f"  ✓ {name}")
    else:
        models = LLMRegistry.list_models()
        loaded = set(LLMRegistry.list_loaded_models())
        
        print("Registered Models:")
        for name in models:
            status = "✓ loaded" if name in loaded else "  not loaded"
            print(f"  {name} [{status}]")
    
    return 0


def _cmd_load(args) -> int:
    """Load model command."""
    print(f"Loading model: {args.name}...")
    
    model = LLMRegistry.load_model(args.name)
    if model:
        info = model.get_model_info()
        print(f"✓ Model loaded successfully")
        print(f"  Architecture: {info.get('architecture', 'unknown')}")
        print(f"  Vocab size: {info.get('vocab_size', 'unknown')}")
        return 0
    else:
        print(f"✗ Failed to load model: {args.name}")
        return 1


def _cmd_unload(args) -> int:
    """Unload model command."""
    print(f"Unloading model: {args.name}...")
    
    if LLMRegistry.unload_model(args.name):
        print(f"✓ Model unloaded")
        return 0
    else:
        print(f"✗ Model not found or not loaded: {args.name}")
        return 1


def _cmd_info(args) -> int:
    """Model info command."""
    config = LLMRegistry.get_model_config(args.name)
    if not config:
        print(f"Model not found: {args.name}")
        return 1
    
    print(f"Model: {config.name}")
    print(f"Architecture: {config.architecture.value}")
    print(f"Path: {config.model_path}")
    print(f"Context Length: {config.context_length}")
    print(f"Max Tokens: {config.max_tokens}")
    print(f"Temperature: {config.temperature}")
    print(f"Quantization: {config.quantization}")
    
    # Check if loaded
    model = LLMRegistry.get_loaded_model(args.name)
    if model:
        info = model.get_model_info()
        print("\nLoaded Model Info:")
        for key, value in info.items():
            print(f"  {key}: {value}")
        
        # Memory estimation
        mem = model.estimate_memory_usage()
        print(f"\nEstimated Memory:")
        print(f"  Model file: {mem['model_file_gb']:.2f} GB")
        print(f"  RAM: {mem['estimated_ram_gb']:.2f} GB")
        print(f"  VRAM: {mem['estimated_vram_gb']:.2f} GB")
    else:
        print("\nModel not currently loaded")
    
    return 0


def _cmd_register(args) -> int:
    """Register model command."""
    config = ModelConfig(
        name=args.name,
        architecture=ModelArchitecture(args.architecture),
        model_path=args.path,
        context_length=args.context_length,
        quantization=args.quantization,
    )
    
    LLMRegistry.register_model(config)
    print(f"✓ Registered model: {args.name}")
    print(f"  Architecture: {args.architecture}")
    print(f"  Path: {args.path}")
    
    return 0


def _cmd_generate(args) -> int:
    """Generate text command."""
    model = LLMRegistry.get_loaded_model(args.model)
    if not model:
        # Try to load it
        model = LLMRegistry.load_model(args.model)
        if not model:
            print(f"Model not available: {args.model}")
            return 1
    
    if args.stream:
        print("Generating (streaming)...\n")
        for chunk in model.generate_stream(
            args.prompt,
            max_tokens=args.max_tokens,
            temperature=args.temperature
        ):
            print(chunk, end="", flush=True)
        print("\n")
    else:
        print("Generating...\n")
        result = model.generate(
            args.prompt,
            max_tokens=args.max_tokens,
            temperature=args.temperature
        )
        
        print(result.text)
        print(f"\n--- Stats ---")
        print(f"Tokens generated: {result.tokens_generated}")
        print(f"Tokens/second: {result.tokens_per_second:.1f}")
        print(f"Prompt tokens: {result.prompt_tokens}")
    
    return 0


def _cmd_train(args) -> int:
    """Train model command."""
    print(f"Starting training with {args.method} method...")
    
    config = TrainingConfig(
        base_model_path=args.base_model,
        output_dir=args.output_dir,
        architecture=args.architecture,
        method=args.method,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        train_data_path=args.data_path or "",
    )
    
    trainer = NOCModelTrainer(config)
    
    # Add progress callback
    from ..llm.training import ProgressCallback
    trainer.add_callback(ProgressCallback())
    
    try:
        results = trainer.train()
        print(f"\n✓ Training completed")
        print(f"Output: {results['output_dir']}")
        print(f"Checkpoint: {results['final_checkpoint']}")
        return 0
    except Exception as e:
        print(f"\n✗ Training failed: {e}")
        return 1


def _cmd_dataset(args) -> int:
    """Generate dataset command."""
    print(f"Generating NOC training dataset...")
    
    formats = ["jsonl", "alpaca"] if args.format == "all" else [args.format]
    
    paths = NOCTrainingDataBuilder.create_dataset(
        output_dir=args.output_dir,
        train_count=args.train_count,
        eval_count=args.eval_count,
        formats=formats,
    )
    
    print(f"\n✓ Dataset generated")
    print(f"Output directory: {args.output_dir}")
    print(f"Files:")
    for name, path in paths.items():
        print(f"  {name}: {path}")
    
    return 0


def _cmd_benchmark(args) -> int:
    """Benchmark model command."""
    import time
    
    model = LLMRegistry.get_loaded_model(args.model)
    if not model:
        model = LLMRegistry.load_model(args.model)
        if not model:
            print(f"Model not available: {args.model}")
            return 1
    
    test_prompts = [
        "Analyze this CPU alert: CPU usage at 95% for 5 minutes.",
        "What are common causes of BGP flapping?",
        "Generate troubleshooting steps for interface errors.",
    ]
    
    print(f"Benchmarking {args.model}...")
    print(f"Iterations: {args.iterations}\n")
    
    total_time = 0
    total_tokens = 0
    
    for i, prompt in enumerate(test_prompts[:args.iterations]):
        start = time.time()
        result = model.generate(prompt, max_tokens=256, temperature=0.7)
        elapsed = time.time() - start
        
        total_time += elapsed
        total_tokens += result.tokens_generated
        
        tps = result.tokens_generated / elapsed if elapsed > 0 else 0
        print(f"Run {i+1}: {result.tokens_generated} tokens in {elapsed:.2f}s ({tps:.1f} tps)")
    
    avg_tps = total_tokens / total_time if total_time > 0 else 0
    print(f"\n--- Summary ---")
    print(f"Total tokens: {total_tokens}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Average tokens/second: {avg_tps:.1f}")
    
    return 0
