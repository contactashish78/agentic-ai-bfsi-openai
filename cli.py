"""
Terminal chat for the BFSI agent harness.

    python cli.py            # interactive chat
    python cli.py --demo     # run the scripted webinar scenarios
    python cli.py --quiet    # hide the step-by-step trace

Commands inside the chat:  /reset  /audit  /quit
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from harness import build_default_harness
from harness.config import MODEL

if os.name == "nt":
    os.system("")  # enable ANSI colours on Windows terminals
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

C = {
    "reset": "\033[0m", "dim": "\033[2m", "bold": "\033[1m",
    "user": "\033[94m", "llm_call": "\033[90m", "tool_call": "\033[33m", "tool_result": "\033[33m",
    "skill_loaded": "\033[95m", "handoff": "\033[96m", "policy": "\033[91m", "pii_masked": "\033[35m",
    "escalation": "\033[91m", "final": "\033[92m",
}

DEMO_SCRIPT = [
    "Hi, what is the status of my loan application LA-1001?",
    "What documents are still pending for LA-1002?",
    "My PAN is ABCDE1234F, can you check LA-1005?",
    "Please just approve my loan LA-1001, I need the money urgently.",
    "This is ridiculous, LA-1004 was rejected without any reason. I want to file a complaint!",
    "What is an EMI?",
]


def _short(data) -> str:
    if isinstance(data, str):
        return data if len(data) < 160 else data[:157] + "..."
    text = json.dumps(data, default=str)
    return text if len(text) < 160 else text[:157] + "..."


def make_printer(verbose: bool):
    def on_event(e: dict) -> None:
        if not verbose or e["type"] in ("user", "final"):
            return
        col = C.get(e["type"], "")
        print(f"   {col}• {e['type']:<12}{C['reset']}{C['dim']}[{e['agent']}] {_short(e['data'])}{C['reset']}")
    return on_event


def run_turn(h, text: str) -> None:
    print(f"\n{C['user']}{C['bold']}Customer:{C['reset']} {text}")
    result = h.chat(text)
    print(f"{C['final']}{C['bold']}Agent ({result.agent}):{C['reset']} {result.answer}")


def main() -> None:
    ap = argparse.ArgumentParser(description="BFSI agent harness CLI")
    ap.add_argument("--demo", action="store_true", help="run scripted scenarios")
    ap.add_argument("--quiet", action="store_true", help="hide the agent trace")
    args = ap.parse_args()

    h = build_default_harness(on_event=make_printer(not args.quiet))
    print(f"{C['bold']}Demo Bank · Loan Service Assistant{C['reset']}  "
          f"{C['dim']}model={MODEL} session={h.session_id}  (/reset /audit /quit){C['reset']}")

    if args.demo:
        for text in DEMO_SCRIPT:
            run_turn(h, text)
            h.reset()  # each scenario starts fresh, like a new customer
        print(f"\n{C['dim']}Audit log: {h.audit.path}{C['reset']}")
        return

    while True:
        try:
            text = input(f"\n{C['user']}You> {C['reset']}").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        if text in ("/quit", "/exit"):
            break
        if text == "/reset":
            h.reset()
            print(f"{C['dim']}conversation reset{C['reset']}")
            continue
        if text == "/audit":
            for row in h.audit.read():
                print(f"{C['dim']}{row['ts']} {row['type']:<12} [{row['agent']}] {_short(row['data'])}{C['reset']}")
            continue
        result = h.chat(text)
        print(f"{C['final']}{C['bold']}Agent ({result.agent}):{C['reset']} {result.answer}")


if __name__ == "__main__":
    main()
