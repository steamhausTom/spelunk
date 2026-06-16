"""Tests for spelunk/utils.py — TASK-005."""

from __future__ import annotations

import os
import pathlib
import stat
from pathlib import Path
from unittest.mock import patch

import pytest


def _write(path: Path, content: str = "hello") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


# ---------------------------------------------------------------------------
# is_binary
# ---------------------------------------------------------------------------

def test_is_binary_null_byte(tmp_path: Path) -> None:
    """File with a null byte in first 8 KB is binary."""
    from spelunk.utils import is_binary

    f = tmp_path / "bin.dat"
    f.write_bytes(b"hello\x00world")
    assert is_binary(f) is True


def test_is_binary_plain_text(tmp_path: Path) -> None:
    """Plain text file with no null bytes is not binary."""
    from spelunk.utils import is_binary

    f = tmp_path / "plain.py"
    f.write_text("print('hello')")
    assert is_binary(f) is False


# ---------------------------------------------------------------------------
# gitignore filtering
# ---------------------------------------------------------------------------

def test_gitignore_excludes_node_modules(tmp_path: Path) -> None:
    """Files inside node_modules/ must not appear in file_paths."""
    from spelunk.utils import walk_repo

    _write(tmp_path / ".gitignore", "node_modules/\n")
    _write(tmp_path / "index.js", "console.log('hi')")
    _write(tmp_path / "node_modules" / "lodash" / "lodash.js", "// lodash")

    file_paths, errors, warnings = walk_repo(tmp_path)

    names = [p.name for p in file_paths]
    assert "index.js" in names
    assert "lodash.js" not in names
    # node_modules directory itself is not a file; .gitignore and index.js are
    gitignore_in_paths = any("node_modules" in str(p) for p in file_paths)
    assert not gitignore_in_paths


# ---------------------------------------------------------------------------
# symlink scope escape
# ---------------------------------------------------------------------------

def test_symlink_scope_escape_excluded(tmp_path: Path) -> None:
    """A symlink whose target is outside the scan root must not appear in file_paths."""
    from spelunk.utils import walk_repo

    # Create a file outside the repo root
    outside = tmp_path.parent / "outside_file.txt"
    outside.write_text("secret")

    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "legit.py", "pass")
    link = repo / "escaped_link.txt"
    link.symlink_to(outside)

    file_paths, errors, warnings = walk_repo(repo)
    names = [p.name for p in file_paths]
    assert "legit.py" in names
    assert "escaped_link.txt" not in names
    assert errors == []  # scope escapes are silently dropped


# ---------------------------------------------------------------------------
# symlink cycle detection
# ---------------------------------------------------------------------------

def test_symlink_cycle_terminates(tmp_path: Path) -> None:
    """A symlink cycle must not cause an infinite loop; cyclic link is not in file_paths."""
    from spelunk.utils import walk_repo

    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "real.py", "pass")

    # Create a directory and a symlink back to parent (cycle)
    subdir = repo / "subdir"
    subdir.mkdir()
    _write(subdir / "inner.py", "pass")
    cycle_link = subdir / "cycle"
    cycle_link.symlink_to(repo)  # points back to root -> cycle

    file_paths, errors, warnings = walk_repo(repo)
    # Walk must complete; the cyclic link is not followed infinitely
    names = [p.name for p in file_paths]
    assert "real.py" in names
    # The cycle link itself (as a symlink to a directory) won't be in file_paths
    # but we must not loop or error
    assert errors == []


# ---------------------------------------------------------------------------
# PermissionError handling
# ---------------------------------------------------------------------------

@pytest.mark.skipif(os.getuid() == 0, reason="root can read any file")
def test_permission_error_goes_to_errors(tmp_path: Path) -> None:
    """A file that raises PermissionError on stat must appear in errors."""
    from spelunk.utils import walk_repo

    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "readable.py", "pass")
    secret = repo / "secret.txt"
    secret.write_text("classified")
    # Remove all permissions
    secret.chmod(0)

    try:
        file_paths, errors, warnings = walk_repo(repo)
        assert any("secret.txt" in e for e in errors)
    finally:
        secret.chmod(stat.S_IRUSR | stat.S_IWUSR)


# ---------------------------------------------------------------------------
# Large file handling
# ---------------------------------------------------------------------------

def test_large_file_in_file_paths_with_warning(tmp_path: Path) -> None:
    """A file > 10 MB must be in file_paths and produce a warning."""
    from spelunk.utils import LARGE_FILE_THRESHOLD_BYTES, walk_repo

    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "small.py", "pass")
    big = repo / "big.bin"
    # Write just over 10 MB
    big.write_bytes(b"x" * (LARGE_FILE_THRESHOLD_BYTES + 1))

    file_paths, errors, warnings = walk_repo(repo)
    names = [p.name for p in file_paths]
    assert "big.bin" in names
    assert any("big.bin" in w for w in warnings)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_constants_defined() -> None:
    """LARGE_FILE_THRESHOLD_BYTES and BINARY_READ_BYTES must be defined."""
    from spelunk.utils import BINARY_READ_BYTES, LARGE_FILE_THRESHOLD_BYTES

    assert LARGE_FILE_THRESHOLD_BYTES == 10 * 1024 * 1024
    assert BINARY_READ_BYTES == 8192
