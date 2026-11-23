"""
Environment check for the Agentic AI in BFSI session.

Run from the project folder with the virtual environment active:
    python check_setup.py            # all checks, including one tiny API call
    python check_setup.py --offline  # skip the API call
"""
from __future__ import annotations

import importlib
from importlib import metadata
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OK, FAIL, WARN = "[ OK ]", "[FAIL]", "[WARN]"
problems = 0


def report(status: str, msg: str, fix: str = "") -> None:
    global problems
    if status == FAIL:
        problems += 1
    print(f"{status} {msg}")
    if fix and status != OK:
        print(f"       fix: {fix}")


# 1. Python version
v = sys.version_info
if v >= (3, 11):
    report(OK, f"Python {v.major}.{v.minor}.{v.micro}")
else:
    report(FAIL, f"Python {v.major}.{v.minor} is too old (need 3.11 or newer)",
           "install Python 3.12 and recreate the .venv folder")

# 2. Running inside the project's virtual environment
in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
venv_here = Path(sys.prefix).resolve() == (ROOT / ".venv").resolve()
if in_venv and venv_here:
    report(OK, f"Virtual environment: {sys.prefix}")
elif in_venv:
    report(WARN, f"A virtual environment is active, but not this project's: {sys.prefix}",
           "activate .venv in this folder")
else:
    report(FAIL, "No virtual environment is active (packages would go to the global Python)",
           r"run .venv\Scripts\Activate.ps1 (Windows) or source .venv/bin/activate (macOS/Linux)")

# 3. Packages
for module, pip_name in [("aisuite", "aisuite"), ("openai", "openai"), ("mcp", "aisuite[mcp]"),
                         ("dotenv", "python-dotenv"), ("pydantic", "pydantic"),
                         ("streamlit", "streamlit"), ("jupyterlab", "jupyter"), ("ipykernel", "ipykernel")]:
    try:
        importlib.import_module(module)
        dist = pip_name.split("[")[0]
        dist = "jupyterlab" if dist == "jupyter" else ("mcp" if "[mcp]" in pip_name else dist)
        try:
            ver = metadata.version(dist)
        except metadata.PackageNotFoundError:
            ver = ""
        report(OK, f"{pip_name:<14} {ver}")
    except Exception as exc:  # noqa: BLE001
        report(FAIL, f"{pip_name} cannot be imported ({exc.__class__.__name__})",
               "pip install -r requirements.txt")

# 4. .env and API key
env_file = ROOT / ".env"
key = ""
if not env_file.exists():
    report(FAIL, ".env file not found", "copy .env.example to .env and paste your key")
else:
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file, override=True)
    except ImportError:
        pass
    key = os.getenv("OPENAI_API_KEY", "")
    if not key or "your-key" in key:
        report(FAIL, ".env exists but OPENAI_API_KEY is still the placeholder",
               "edit .env and paste your real key after OPENAI_API_KEY=")
    else:
        report(OK, f"OPENAI_API_KEY found (sk-...{key[-4:]})  model: {os.getenv('MODEL', 'openai:gpt-4o-mini')}")

# 5. Project files the notebooks rely on
for rel in ["utils.py", "harness/agent.py", "data/loans.json", "notebooks/01_sdk_basics.ipynb"]:
    if not (ROOT / rel).exists():
        report(FAIL, f"missing {rel}", "re-download or re-clone the repository")

# 6. One tiny live call
if "--offline" in sys.argv:
    report(WARN, "API call skipped (--offline)")
elif key and "your-key" not in key and problems == 0:
    try:
        import aisuite as ai
        model = os.getenv("MODEL", "openai:gpt-4o-mini")
        reply = ai.Client().chat.completions.create(
            model=model, max_tokens=5,
            messages=[{"role": "user", "content": "Reply with the single word: ready"}])
        report(OK, f"Live call to {model} answered: {reply.choices[0].message.content.strip()!r}")
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).splitlines()[0][:160]
        hint = "check the key, your network/proxy, and that the OpenAI account has credit"
        if "401" in msg or "invalid_api_key" in msg.lower():
            hint = "the key was rejected: copy it again from platform.openai.com/api-keys"
        elif "certificate" in msg.lower() or "ssl" in msg.lower():
            hint = "corporate network is intercepting TLS: see 'Corporate network' in setup_guide.html"
        report(FAIL, f"Live API call failed: {msg}", hint)

print()
print("All set for the session!" if problems == 0 else f"{problems} problem(s) to fix. See setup_guide.html > Troubleshooting.")
sys.exit(1 if problems else 0)
