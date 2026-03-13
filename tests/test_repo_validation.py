from __future__ import annotations

import pytest

from clawductor.state import validate_repo_path


def test_valid_git_repo(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    valid, error = validate_repo_path(str(tmp_path))
    assert valid is True
    assert error == ""


def test_nonexistent_path(tmp_path):
    missing = str(tmp_path / "does_not_exist")
    valid, error = validate_repo_path(missing)
    assert valid is False
    assert "does not exist" in error.lower() or "not exist" in error.lower()


def test_existing_directory_without_git(tmp_path):
    valid, error = validate_repo_path(str(tmp_path))
    assert valid is False
    assert "git" in error.lower()


def test_file_path_not_directory(tmp_path):
    f = tmp_path / "somefile.txt"
    f.write_text("hello")
    valid, error = validate_repo_path(str(f))
    assert valid is False
    assert "directory" in error.lower()


def test_empty_string_path():
    valid, error = validate_repo_path("")
    assert valid is False


def test_nested_git_repo(tmp_path):
    """A directory with a .git inside a parent dir — only the inner dir is valid."""
    inner = tmp_path / "project"
    inner.mkdir()
    (inner / ".git").mkdir()

    # inner dir is valid
    valid, _ = validate_repo_path(str(inner))
    assert valid is True

    # parent dir (no .git directly) is not valid
    valid2, _ = validate_repo_path(str(tmp_path))
    assert valid2 is False
