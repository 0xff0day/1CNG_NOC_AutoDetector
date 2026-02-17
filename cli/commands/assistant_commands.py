from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from autodetector.assistant.detector import detect_issues_from_scan, summarize_scan_for_prompt
from autodetector.assistant.llm_assistant import AssistantConfig, generate_assistant_response
from autodetector.assistant.voice import speak_via_voice_call
from autodetector.pipeline.orchestrator import run_poll_once


def add_assistant_subparser(subparsers) -> argparse.ArgumentParser:
    assistant_parser = subparsers.add_parser(
        "assistant",
        help="AI assistant: chat, explain scan results, and voice-call summaries",
    )

    asp = assistant_parser.add_subparsers(dest="assistant_command", required=True)

    p_chat = asp.add_parser("chat", help="Interactive chat with a local LLM")
    p_chat.add_argument("--model", required=True, help="Registered model name")
    p_chat.add_argument("--system", default="You are a senior network operations assistant. Be concise and actionable.")

    p_explain = asp.add_parser("explain-scan", help="Auto-detect issues from scan output and generate a response")
    p_explain.add_argument("--model", required=True, help="Registered model name")
    p_explain.add_argument("--system", default="You are a senior network operations assistant. Be concise and actionable.")
    p_explain.add_argument("--scan-json", help="Path to scan JSON output (if omitted, a scan is executed)")
    p_explain.add_argument("--deep", action="store_true", help="Run deep-audit scan when executing scan")

    p_voice = asp.add_parser("voice-call", help="Generate a summary and place a Twilio voice call")
    p_voice.add_argument("--model", required=True, help="Registered model name")
    p_voice.add_argument("--system", default="You are a senior network operations assistant. Be concise and actionable.")
    p_voice.add_argument("--scan-json", help="Path to scan JSON output (if omitted, a scan is executed)")
    p_voice.add_argument("--deep", action="store_true", help="Run deep-audit scan when executing scan")

    return assistant_parser


def handle_assistant_command(args, cfg: Any, store: Any) -> int:
    cmd = args.assistant_command

    if cmd == "chat":
        return _cmd_chat(args)

    if cmd == "explain-scan":
        scan = _load_or_run_scan(args, cfg, store)
        return _cmd_explain_scan(args, scan)

    if cmd == "voice-call":
        scan = _load_or_run_scan(args, cfg, store)
        return _cmd_voice_call(args, cfg, scan)

    print("Unknown assistant command")
    return 1


def _load_or_run_scan(args, cfg: Any, store: Any) -> Dict[str, Any]:
    if getattr(args, "scan_json", None):
        with open(args.scan_json, "r", encoding="utf-8") as f:
            return json.load(f)

    now = datetime.now(timezone.utc)
    return run_poll_once(cfg, store, now=now, deep=bool(getattr(args, "deep", False)))


def _cmd_chat(args) -> int:
    cfg = AssistantConfig(model_name=args.model, system_prompt=args.system)
    context: List[Dict[str, str]] = []

    sys.stdout.write("Enter messages. Type 'exit' to quit.\n")
    while True:
        sys.stdout.write("you> ")
        sys.stdout.flush()
        line = sys.stdin.readline()
        if not line:
            break
        msg = line.strip()
        if msg.lower() in {"exit", "quit"}:
            break
        if not msg:
            continue

        context.append({"role": "user", "content": msg})
        resp = generate_assistant_response(cfg, instruction="Respond to the user.", input_data="", context=context)
        sys.stdout.write(f"ai> {resp.text.strip()}\n")
        context.append({"role": "assistant", "content": resp.text})

    return 0


def _cmd_explain_scan(args, scan: Dict[str, Any]) -> int:
    issues = detect_issues_from_scan(scan)
    prompt_data = {
        "scan": summarize_scan_for_prompt(scan),
        "detected_issues": [i.__dict__ for i in issues],
    }

    cfg = AssistantConfig(model_name=args.model, system_prompt=args.system)
    resp = generate_assistant_response(
        cfg,
        instruction=(
            "Analyze scan results. Provide: (1) probable root cause, (2) concrete troubleshooting steps, "
            "(3) minimal config changes to try, (4) what evidence in the scan supports your conclusion."
        ),
        input_data=prompt_data,
    )
    sys.stdout.write(resp.text.strip() + "\n")
    return 0


def _cmd_voice_call(args, app_cfg: Any, scan: Dict[str, Any]) -> int:
    issues = detect_issues_from_scan(scan)
    prompt_data = {
        "scan": summarize_scan_for_prompt(scan),
        "detected_issues": [i.__dict__ for i in issues],
    }

    cfg = AssistantConfig(model_name=args.model, system_prompt=args.system, max_tokens=256, temperature=0.2)
    resp = generate_assistant_response(
        cfg,
        instruction=(
            "Summarize the scan for an on-call phone call. Keep it under 60 seconds. "
            "Include device IDs affected and the single most likely cause."
        ),
        input_data=prompt_data,
    )

    summary = resp.text.strip()
    speak_via_voice_call(app_cfg, summary)
    return 0
