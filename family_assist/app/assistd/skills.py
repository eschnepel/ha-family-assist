from __future__ import annotations

import re

import httpx

LOAD_SKILL = "load_skill"

SKILL_BASE_URL = "https://raw.githubusercontent.com/mattpocock/skills/main/skills/"
# Curated: only these skills of github.com/mattpocock/skills can be loaded, nothing else.
SKILLS = {
    "domain-modeling": "engineering/domain-modeling",
    "grill-me": "productivity/grill-me",
    "grilling": "productivity/grilling",
    "grill-with-docs": "engineering/grill-with-docs",
}
MAX_SKILL_BYTES = 64 * 1024
FETCH_TIMEOUT_SECONDS = 15.0
MAIN_FILE = "SKILL.md"
# Resource files must sit directly in the skill folder: a plain Markdown file name, no path.
RESOURCE_FILE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.md")

SCHEMA = (
    "Load the instructions of a curated skill and follow them for the current task. Available skills: "
    + ", ".join(SKILLS) + ". A skill may refer to resource files in its own folder (e.g. 'ADR-FORMAT.md'); "
    "load them with the 'file' parameter.",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string", "enum": list(SKILLS), "description": "Skill name"},
            "file": {"type": "string", "description": f"Resource file of the skill; default '{MAIN_FILE}'"},
        },
        "required": ["name"],
    },
)


class SkillError(Exception):
    pass


async def load_skill(args, *, transport: httpx.AsyncBaseTransport | None = None) -> str:
    name = args.get("name") if isinstance(args, dict) else None
    if not isinstance(name, str) or name not in SKILLS:
        raise SkillError(f"unknown skill; available: {', '.join(SKILLS)}")
    file = args.get("file") or MAIN_FILE
    if not isinstance(file, str) or not RESOURCE_FILE_RE.fullmatch(file) or ".." in file:
        raise SkillError("file must be a Markdown file name in the skill folder")
    url = f"{SKILL_BASE_URL}{SKILLS[name]}/{file}"
    try:
        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=False,
                                     transport=transport) as client:
            response = await client.get(url)
    except httpx.HTTPError:
        raise SkillError("skill could not be loaded") from None
    if response.status_code != 200:
        raise SkillError(f"skill could not be loaded (HTTP {response.status_code})")
    data = response.content
    if len(data) > MAX_SKILL_BYTES:
        raise SkillError("skill is too large")
    return data.decode("utf-8", errors="replace")
