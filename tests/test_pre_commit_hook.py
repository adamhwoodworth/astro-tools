"""Tests for the .githooks/pre-commit hook.

Each test makes real commits in a throwaway git repository whose hooks path
points at this repo's .githooks directory.
"""

import subprocess
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).parent.parent / ".githooks"

UNFORMATTED = "x = {  'a':1 }\n"
FORMATTED = 'x = {"a": 1}\n'


def git(repo, *args):
    """Run git in repo and return the completed process."""
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=120)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "user.email", "test@example.test")
    git(tmp_path, "config", "core.hooksPath", str(HOOKS_DIR))
    return tmp_path


def test_unformatted_staged_file_is_committed_formatted(repo):
    (repo / "a.py").write_text(UNFORMATTED)
    git(repo, "add", "a.py")

    result = git(repo, "commit", "-q", "-m", "add a")

    assert result.returncode == 0, result.stderr
    assert git(repo, "show", "HEAD:a.py").stdout == FORMATTED
    assert git(repo, "status", "--porcelain").stdout == ""


def test_lint_error_blocks_the_commit(repo):
    (repo / "a.py").write_text("import os\n")
    git(repo, "add", "a.py")

    result = git(repo, "commit", "-q", "-m", "add a")

    assert result.returncode != 0
    assert "F401" in result.stdout + result.stderr
    assert git(repo, "log", "--oneline").stdout == ""


def test_partially_staged_file_needing_format_blocks_without_touching_it(repo):
    (repo / "a.py").write_text(FORMATTED)
    git(repo, "add", "a.py")
    git(repo, "commit", "-q", "-m", "add a")

    # Stage an unformatted change, then make a further edit that stays unstaged.
    (repo / "a.py").write_text(FORMATTED + UNFORMATTED)
    git(repo, "add", "a.py")
    (repo / "a.py").write_text(FORMATTED + UNFORMATTED + "y = 2\n")

    result = git(repo, "commit", "-q", "-m", "change a")

    assert result.returncode != 0
    assert "a.py" in result.stdout + result.stderr
    assert (repo / "a.py").read_text() == FORMATTED + UNFORMATTED + "y = 2\n"
    assert git(repo, "show", ":a.py").stdout == FORMATTED + UNFORMATTED


def test_commit_without_python_files_passes(repo):
    (repo / "notes.md").write_text("#  notes\n")
    git(repo, "add", "notes.md")

    result = git(repo, "commit", "-q", "-m", "add notes")

    assert result.returncode == 0, result.stderr


def test_unstaged_edits_to_a_formatted_file_stay_out_of_the_commit(repo):
    (repo / "a.py").write_text(FORMATTED)
    git(repo, "add", "a.py")
    (repo / "a.py").write_text(FORMATTED + "y = 2\n")

    result = git(repo, "commit", "-q", "-m", "add a")

    assert result.returncode == 0, result.stderr
    assert git(repo, "show", "HEAD:a.py").stdout == FORMATTED
    assert (repo / "a.py").read_text() == FORMATTED + "y = 2\n"
