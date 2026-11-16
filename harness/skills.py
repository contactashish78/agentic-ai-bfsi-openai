"""
Skills = reviewed Markdown playbooks that the agent loads on demand.

Only each skill's name + description goes into the system prompt (cheap).
The agent calls the `load_skill` tool to pull the full instructions when it
needs them ("progressive disclosure"). Compliance or business teams can edit
these files without touching Python code.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .config import SKILLS_DIR

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.S)


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path


def discover_skills(skills_dir: Path = SKILLS_DIR) -> dict[str, Skill]:
    skills: dict[str, Skill] = {}
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        m = _FRONTMATTER.match(text)
        if not m:
            continue
        meta = dict(
            line.split(":", 1) for line in m.group(1).splitlines() if ":" in line
        )
        name = meta.get("name", path.parent.name).strip()
        skills[name] = Skill(name, meta.get("description", "").strip(), m.group(2).strip(), path)
    return skills


def skills_catalog(skills: dict[str, Skill]) -> str:
    """The short list injected into the system prompt."""
    return "\n".join(f"- {s.name}: {s.description}" for s in skills.values())


def make_load_skill_tool(skills: dict[str, Skill]):
    """Build the `load_skill` tool bound to the discovered skills."""

    def load_skill(skill_name: str) -> dict:
        """Load the full instructions of a skill (playbook) by name.

        Call this before handling a request that matches a skill description.

        Args:
            skill_name: Exact skill name from the AVAILABLE SKILLS list.
        """
        skill = skills.get(skill_name.strip())
        if not skill:
            return {"error": f"Unknown skill '{skill_name}'.", "available": list(skills)}
        return {"skill": skill.name, "instructions": skill.body}

    return load_skill
