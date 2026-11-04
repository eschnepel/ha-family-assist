import asyncio
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from assistd.skills import SKILLS, SkillError, load_skill

Handler = Callable[[httpx.Request], httpx.Response]


def run(args: Any, handler: Handler) -> str:
    result: str = asyncio.run(load_skill(args, transport=httpx.MockTransport(handler)))
    return result


def test_curated_skill_is_fetched_from_fixed_url() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, text="# Grill")

    assert run({"name": "grill-me"}, handler) == "# Grill"
    assert seen == [
        "https://raw.githubusercontent.com/mattpocock/skills/main/skills/productivity/grill-me/SKILL.md"
    ]
    assert set(SKILLS) == {"domain-modeling", "grill-me", "grilling", "grill-with-docs"}


@pytest.mark.parametrize("args", [{"name": "tdd"}, {"name": "../x"}, {"name": 1}, {}, "grill-me"])
def test_other_skills_are_rejected_without_request(args: Any) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    with pytest.raises(SkillError):
        run(args, handler)


def test_resource_file_in_skill_folder_is_fetched() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, text="adr")

    assert run({"name": "domain-modeling", "file": "ADR-FORMAT.md"}, handler) == "adr"
    assert seen == [
        "https://raw.githubusercontent.com/mattpocock/skills/main/skills/engineering/domain-modeling/ADR-FORMAT.md"
    ]


@pytest.mark.parametrize(
    "file", ["../grill-me/SKILL.md", "a/b.md", "..md", ".hidden.md", "x.py", "a\\b.md", 5]
)
def test_resource_files_outside_the_skill_folder_are_rejected(file: Any) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    with pytest.raises(SkillError):
        run({"name": "domain-modeling", "file": file}, handler)


def test_http_errors_and_oversize_are_reported() -> None:
    with pytest.raises(SkillError):
        run({"name": "grilling"}, lambda r: httpx.Response(404))
    with pytest.raises(SkillError):
        run({"name": "grilling"}, lambda r: httpx.Response(200, content=b"x" * (64 * 1024 + 1)))
