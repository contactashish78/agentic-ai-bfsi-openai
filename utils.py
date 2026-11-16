"""
Notebook display helpers for the BFSI Agentic AI webinar.

Inspired by the `utils.print_html` helper used in DeepLearning.AI short courses:
render LLM output, JSON, tool calls and agent traces as clean HTML cards
instead of raw `print()` dumps.

Usage in a notebook:
    from utils import print_html, show_messages, show_trace
    print_html(response.choices[0].message.content, title="Assistant reply")
"""
from __future__ import annotations

import html
import json
from typing import Any, Iterable

try:
    from IPython.display import HTML, display
except ImportError:  # running outside Jupyter (CLI / tests)
    HTML = None

    def display(obj):  # type: ignore
        print(obj)


# --------------------------------------------------------------------------- #
# Styling: fixed colours that read well on both light and dark notebook themes
# --------------------------------------------------------------------------- #
_CSS = """
<style>
.bfsi-card{font-family:-apple-system,Segoe UI,Roboto,sans-serif;border-radius:10px;
  margin:10px 0;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.15);
  border:1px solid #d6dbe4;background:#ffffff;color:#1f2933;max-width:980px}
.bfsi-card .hd{padding:8px 14px;font-weight:600;font-size:13px;letter-spacing:.3px;
  color:#fff;background:#1d4ed8;display:flex;justify-content:space-between}
.bfsi-card .hd small{font-weight:400;opacity:.85}
.bfsi-card .bd{padding:12px 16px;font-size:14px;line-height:1.55;white-space:normal}
.bfsi-card pre{margin:0;white-space:pre-wrap;word-break:break-word;font-size:13px;
  font-family:Consolas,Menlo,monospace;color:#1f2933;background:transparent}
.bfsi-card table{border-collapse:collapse;font-size:13px;width:100%}
.bfsi-card th,.bfsi-card td{border:1px solid #e3e7ee;padding:5px 9px;text-align:left;
  vertical-align:top;color:#1f2933}
.bfsi-card th{background:#f1f4f9;font-weight:600}
.bfsi-chat{display:flex;flex-direction:column;gap:8px}
.bfsi-msg{padding:9px 13px;border-radius:10px;max-width:85%;font-size:14px;line-height:1.5;color:#1f2933}
.bfsi-msg .who{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;
  margin-bottom:3px;opacity:.75}
.bfsi-msg.system{background:#f3f4f6;border:1px dashed #9ca3af;align-self:center;max-width:95%}
.bfsi-msg.user{background:#dbeafe;align-self:flex-end}
.bfsi-msg.assistant{background:#dcfce7;align-self:flex-start}
.bfsi-msg.tool{background:#fef3c7;align-self:flex-start;font-family:Consolas,Menlo,monospace;font-size:12.5px}
.bfsi-step{display:flex;gap:10px;align-items:flex-start;padding:7px 0;border-bottom:1px solid #eef1f5}
.bfsi-step:last-child{border-bottom:none}
.bfsi-badge{flex:0 0 auto;font-size:11px;font-weight:700;padding:3px 8px;border-radius:999px;
  color:#fff;min-width:92px;text-align:center;text-transform:uppercase}
.bfsi-step .txt{flex:1;font-size:13.5px;color:#1f2933}
.bfsi-step pre{background:#f8fafc;border-radius:6px;padding:6px 8px;margin-top:4px}
</style>
"""

_THEMES = {
    "blue": "#1d4ed8",
    "green": "#15803d",
    "amber": "#b45309",
    "red": "#b91c1c",
    "purple": "#6d28d9",
    "gray": "#475569",
    "teal": "#0f766e",
}

_EVENT_COLOURS = {
    "user": "#1d4ed8",
    "llm_call": "#475569",
    "tool_call": "#b45309",
    "tool_result": "#a16207",
    "skill_loaded": "#6d28d9",
    "handoff": "#0f766e",
    "policy": "#b91c1c",
    "pii_masked": "#be185d",
    "escalation": "#dc2626",
    "final": "#15803d",
    "error": "#7f1d1d",
}


def _show(markup: str) -> None:
    if HTML is None:
        print(_strip_tags(markup))
    else:
        display(HTML(_CSS + markup))


def _strip_tags(markup: str) -> str:
    import re

    text = re.sub(r"<style.*?</style>", "", markup, flags=re.S)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(re.sub(r"[ \t]+", " ", text)).strip()


def _md(text: str) -> str:
    """Very small markdown -> HTML (bold, italics, code, bullets, line breaks)."""
    import re

    esc = html.escape(str(text))
    esc = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc)
    esc = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<i>\1</i>", esc)
    esc = re.sub(r"`([^`]+)`", r"<code>\1</code>", esc)
    lines, out, in_list = esc.split("\n"), [], False
    for line in lines:
        h = re.match(r"^\s*(#{1,6})\s+(.*)", line)
        if h:
            if in_list:
                out.append("</ul>")
                in_list = False
            size = {1: "16px", 2: "15px"}.get(len(h.group(1)), "14px")
            out.append(f"<div style='font-weight:700;font-size:{size};margin:8px 0 2px'>{h.group(2)}</div>")
            continue
        m = re.match(r"^\s*(?:[-*•]|\d+\.)\s+(.*)", line)
        if m:
            if not in_list:
                out.append("<ul style='margin:4px 0 4px 18px;padding:0'>")
                in_list = True
            out.append(f"<li>{m.group(1)}</li>")
        else:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(line + "<br>")
    if in_list:
        out.append("</ul>")
    return "".join(out).removesuffix("<br>")


def _to_plain(obj: Any) -> Any:
    """Convert pydantic models / OpenAI objects into plain python structures."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(exclude_none=True)
    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict()
        except Exception:
            pass
    return obj


def _render_body(content: Any) -> str:
    content = _to_plain(content)
    # pandas DataFrame
    if hasattr(content, "to_html") and hasattr(content, "columns"):
        return content.to_html(index=False, border=0)
    # list of flat dicts -> table
    if isinstance(content, list) and content and all(isinstance(r, dict) for r in content):
        cols = list(dict.fromkeys(k for r in content for k in r))
        head = "".join(f"<th>{html.escape(str(c))}</th>" for c in cols)
        rows = "".join(
            "<tr>" + "".join(f"<td>{_cell(r.get(c, ''))}</td>" for c in cols) + "</tr>"
            for r in content
        )
        return f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>"
    # dict -> key/value table
    if isinstance(content, dict):
        rows = "".join(
            f"<tr><th style='width:28%'>{html.escape(str(k))}</th><td>{_cell(v)}</td></tr>"
            for k, v in content.items()
        )
        return f"<table>{rows}</table>"
    # JSON string -> pretty
    if isinstance(content, str):
        stripped = content.strip()
        if stripped[:1] in "{[":
            try:
                return _render_body(json.loads(stripped))
            except Exception:
                pass
        return _md(content)
    return f"<pre>{html.escape(repr(content))}</pre>"


def _cell(v: Any) -> str:
    v = _to_plain(v)
    if isinstance(v, (dict, list)):
        return f"<pre>{html.escape(json.dumps(v, indent=2, default=str))}</pre>"
    return html.escape(str(v))


# --------------------------------------------------------------------------- #
# Public helpers
# --------------------------------------------------------------------------- #
def print_html(content: Any, title: str = "Output", color: str = "blue", subtitle: str = "") -> None:
    """Render any content (str / markdown / JSON / dict / list / pydantic / DataFrame) as a card."""
    bg = _THEMES.get(color, color)
    sub = f"<small>{html.escape(subtitle)}</small>" if subtitle else ""
    _show(
        f"<div class='bfsi-card'><div class='hd' style='background:{bg}'>"
        f"<span>{html.escape(title)}</span>{sub}</div>"
        f"<div class='bd'>{_render_body(content)}</div></div>"
    )


def print_json(obj: Any, title: str = "JSON", color: str = "gray") -> None:
    """Pretty-print an object as formatted JSON inside a card."""
    obj = _to_plain(obj)
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except Exception:
            pass
    body = html.escape(json.dumps(obj, indent=2, default=str))
    bg = _THEMES.get(color, color)
    _show(
        f"<div class='bfsi-card'><div class='hd' style='background:{bg}'>{html.escape(title)}</div>"
        f"<div class='bd'><pre>{body}</pre></div></div>"
    )


def _msg_get(m: Any, key: str, default=None):
    if isinstance(m, dict):
        return m.get(key, default)
    return getattr(m, key, default)


def show_messages(messages: Iterable[Any], title: str = "Conversation", show_system: bool = True) -> None:
    """Render a chat-completions message list as chat bubbles (incl. tool calls / results)."""
    parts = []
    for m in messages:
        role = _msg_get(m, "role", "assistant")
        if role == "system" and not show_system:
            continue
        content = _msg_get(m, "content") or ""
        tool_calls = _msg_get(m, "tool_calls") or []
        inner = _md(content) if content else ""
        for tc in tool_calls:
            fn = _msg_get(tc, "function")
            name, args = _msg_get(fn, "name"), _msg_get(fn, "arguments")
            inner += (
                f"<div style='margin-top:4px'>🔧 <b>calls</b> <code>{html.escape(str(name))}</code>"
                f"<pre>{html.escape(str(args))}</pre></div>"
            )
        label = role
        if role == "tool":
            label = f"tool result · {_msg_get(m, 'name') or _msg_get(m, 'tool_call_id', '')}"
            inner = f"<pre>{html.escape(str(content))}</pre>"
        parts.append(f"<div class='bfsi-msg {role}'><div class='who'>{html.escape(label)}</div>{inner}</div>")
    _show(
        f"<div class='bfsi-card'><div class='hd' style='background:{_THEMES['teal']}'>{html.escape(title)}</div>"
        f"<div class='bd'><div class='bfsi-chat'>{''.join(parts)}</div></div></div>"
    )


def show_tool_call(name: str, arguments: Any, result: Any = None) -> None:
    """Render a single tool invocation and (optionally) its result."""
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except Exception:
            pass
    body = f"<b>Function:</b> <code>{html.escape(name)}</code><br><b>Arguments:</b>{_render_body(arguments)}"
    if result is not None:
        body += f"<div style='margin-top:8px'><b>Result:</b>{_render_body(result)}</div>"
    _show(
        f"<div class='bfsi-card'><div class='hd' style='background:{_THEMES['amber']}'>🔧 Tool call</div>"
        f"<div class='bd'>{body}</div></div>"
    )


def show_trace(events: Iterable[dict], title: str = "Agent trace") -> None:
    """Render harness/agent events: [{'type':..., 'agent':..., 'data':...}, ...]."""
    rows = []
    for e in events:
        etype = e.get("type", "event")
        colour = _EVENT_COLOURS.get(etype, "#475569")
        agent = e.get("agent")
        data = e.get("data", "")
        if isinstance(data, (dict, list)):
            body = f"<pre>{html.escape(json.dumps(data, indent=2, default=str))}</pre>"
        else:
            body = _md(str(data))
        who = f"<span style='opacity:.65;font-size:12px'>[{html.escape(agent)}]</span> " if agent else ""
        rows.append(
            f"<div class='bfsi-step'><span class='bfsi-badge' style='background:{colour}'>"
            f"{html.escape(etype.replace('_', ' '))}</span><div class='txt'>{who}{body}</div></div>"
        )
    _show(
        f"<div class='bfsi-card'><div class='hd' style='background:{_THEMES['purple']}'>{html.escape(title)}</div>"
        f"<div class='bd'>{''.join(rows) or '<i>no events</i>'}</div></div>"
    )


def compare(left: Any, right: Any, left_title: str = "Before", right_title: str = "After",
            left_color: str = "red", right_color: str = "green") -> None:
    """Side-by-side cards — handy for 'without tool' vs 'with tool' comparisons."""
    lc, rc = _THEMES.get(left_color, left_color), _THEMES.get(right_color, right_color)
    _show(
        "<div style='display:flex;gap:12px;flex-wrap:wrap'>"
        f"<div class='bfsi-card' style='flex:1;min-width:300px'><div class='hd' style='background:{lc}'>"
        f"{html.escape(left_title)}</div><div class='bd'>{_render_body(left)}</div></div>"
        f"<div class='bfsi-card' style='flex:1;min-width:300px'><div class='hd' style='background:{rc}'>"
        f"{html.escape(right_title)}</div><div class='bd'>{_render_body(right)}</div></div></div>"
    )


def show_usage(response: Any, title: str = "Token usage") -> None:
    """Show token usage for a chat completion response."""
    usage = _to_plain(getattr(response, "usage", None)) or {}
    keep = {k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens") if k in usage}
    print_html(keep or "usage not reported", title=title, color="gray")
