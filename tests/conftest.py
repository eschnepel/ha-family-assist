import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "family_assist" / "app"))

GIT_ID = ["-c", "user.name=Seed", "-c", "user.email=seed@example.com"]


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *GIT_ID, *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def make_dir_link(link: Path, target: Path) -> None:
    """Symlink to a folder; on Windows without privileges fall back to a junction."""
    try:
        os.symlink(target, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        if os.name != "nt":
            raise
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    """A plain folder shaped like an Agent Environment (no git history)."""
    root = tmp_path / "repo"
    write(root, "AGENTS.md", "---\nmodell: test-model\n---\n# Rules\n")
    write(root, "notes.md", "alpha\nbeta\ngamma\n")
    write(root, "Mathe/AGENTS.md", "Mathe rules")
    write(root, "Mathe/Lehrplan-Gymnasium/Klasse-8.md", "curriculum bruch\n")
    write(root, "Mathe/Klasse-8/Marten/a.md", "task bruch\n")
    write(root, "Scripts/run.ps1", "secret script\n")
    write(root, "Scripts/AGENTS.md", "script rules")
    write(root, ".family_assist.yaml", "hidden:\n  - /Scripts/\nreadonly:\n  - Lehrplan-*/\n")
    (root / ".git").mkdir()
    write(root, ".git/config", "[core]\n")
    return root


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    """A bare repository on branch main with one commit."""
    bare = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(seed)], check=True)
    write(seed, "AGENTS.md", "# Rules\n")
    write(seed, "notes.md", "one\n")
    git(seed, "add", ".")
    git(seed, "commit", "-q", "-m", "seed")
    git(seed, "push", "-q", str(bare), "main")
    return bare
