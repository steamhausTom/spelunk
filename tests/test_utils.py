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


# ---------------------------------------------------------------------------
# TASK-017: root vs resolved_root mismatch
# ---------------------------------------------------------------------------

def test_gitignore_applied_via_relative_path(tmp_path: Path) -> None:
    """AC1 — walk_repo called with a relative path still applies .gitignore rules.

    When walk_repo receives Path(".") (resolved inside tmp_path), gitignore
    rules must filter node_modules/ even though the input path may differ from
    its resolved absolute form.
    """
    from spelunk.utils import walk_repo

    _write(tmp_path / ".gitignore", "node_modules/\n")
    _write(tmp_path / "index.js", "console.log('hi')")
    _write(tmp_path / "node_modules" / "lodash" / "lodash.js", "// lodash")

    # Build a relative path by changing cwd to tmp_path and passing Path(".")
    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        file_paths, errors, warnings = walk_repo(Path("."))
    finally:
        os.chdir(original_cwd)

    names = [p.name for p in file_paths]
    assert "index.js" in names, "index.js should be included"
    assert "lodash.js" not in names, "lodash.js inside node_modules/ must be excluded"
    assert not any("node_modules" in str(p) for p in file_paths), (
        "No path under node_modules/ must appear in file_paths"
    )


def test_gitignore_applied_via_symlinked_path(tmp_path: Path) -> None:
    """AC2 — walk_repo with a symlinked path component still applies .gitignore rules.

    Creates a symlink to the repo directory (simulating /tmp -> /private/tmp on
    macOS) and passes the symlinked path to walk_repo. Gitignore must still fire.
    """
    from spelunk.utils import walk_repo

    repo = tmp_path / "real_repo"
    repo.mkdir()
    _write(repo / ".gitignore", "node_modules/\n")
    _write(repo / "app.py", "pass")
    _write(repo / "node_modules" / "pkg" / "index.js", "// pkg")

    # Create a symlink that points at the real repo
    link = tmp_path / "linked_repo"
    link.symlink_to(repo)

    # Pass the symlinked path — this mimics /tmp on macOS where /tmp -> /private/tmp
    file_paths, errors, warnings = walk_repo(link)

    names = [p.name for p in file_paths]
    assert "app.py" in names, "app.py should be included"
    assert "index.js" not in names, "index.js inside node_modules/ must be excluded"
    assert not any("node_modules" in str(p) for p in file_paths), (
        "No path under node_modules/ must appear in file_paths"
    )


def test_is_ignored_never_raises_value_error_relative_path(tmp_path: Path) -> None:
    """AC4 — is_ignored must not raise ValueError when walk_repo uses a relative path.

    Patches is_ignored to assert it never returns via the ValueError fallback
    (i.e., the root passed in is always the resolved form so relative_to succeeds).
    """
    from spelunk import utils

    _write(tmp_path / ".gitignore", "node_modules/\n")
    _write(tmp_path / "main.py", "pass")
    _write(tmp_path / "node_modules" / "lib.js", "// lib")

    value_error_triggered = []

    original_is_ignored = utils.is_ignored

    def patched_is_ignored(path: Path, root: Path, spec: object) -> bool:
        try:
            path.relative_to(root)
        except ValueError:
            value_error_triggered.append((path, root))
        return original_is_ignored(path, root, spec)

    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        with patch.object(utils, "is_ignored", patched_is_ignored):
            utils.walk_repo(Path("."))
    finally:
        os.chdir(original_cwd)

    assert value_error_triggered == [], (
        f"is_ignored raised ValueError for: {value_error_triggered}"
    )


# ---------------------------------------------------------------------------
# TASK-021: .gitignore size cap and cumulative line cap
# ---------------------------------------------------------------------------

def test_gitignore_cap_constants_defined() -> None:
    """GITIGNORE_MAX_BYTES and GITIGNORE_MAX_TOTAL_LINES must be defined at module level."""
    from spelunk.utils import GITIGNORE_MAX_BYTES, GITIGNORE_MAX_TOTAL_LINES

    assert GITIGNORE_MAX_BYTES == 1 * 1024 * 1024
    assert GITIGNORE_MAX_TOTAL_LINES == 50_000


def test_collect_gitignore_spec_returns_tuple(tmp_path: Path) -> None:
    """collect_gitignore_spec must return a (PathSpec, list[str]) tuple."""
    from spelunk.utils import collect_gitignore_spec

    (tmp_path / ".gitignore").write_text("*.pyc\n")
    result = collect_gitignore_spec(tmp_path)
    assert isinstance(result, tuple), "collect_gitignore_spec must return a tuple"
    assert len(result) == 2, "tuple must have exactly two elements"
    spec, warnings = result
    assert isinstance(warnings, list)


def test_collect_gitignore_spec_normal_returns_empty_warnings(tmp_path: Path) -> None:
    """Normal .gitignore within caps returns an empty warnings list and applies patterns."""
    from spelunk.utils import collect_gitignore_spec

    (tmp_path / ".gitignore").write_text("node_modules/\n*.pyc\n")
    spec, warnings = collect_gitignore_spec(tmp_path)
    assert warnings == []
    assert spec.match_file("node_modules/lodash.js")


def test_collect_gitignore_spec_oversized_file_skipped(tmp_path: Path) -> None:
    """A .gitignore exceeding 1 MB is skipped; a warning naming the path is returned."""
    from spelunk.utils import GITIGNORE_MAX_BYTES, collect_gitignore_spec

    oversized = tmp_path / ".gitignore"
    # Write just over the cap — repeated pattern lines so it is valid text
    content = "*.skip\n" * ((GITIGNORE_MAX_BYTES // 7) + 1)
    oversized.write_bytes(content.encode("utf-8"))

    spec, warnings = collect_gitignore_spec(tmp_path)
    assert any(str(oversized) in w for w in warnings), (
        f"Expected warning for {oversized}, got: {warnings}"
    )
    assert not spec.match_file("anything.skip"), (
        "Patterns from oversized .gitignore must not be applied"
    )


def test_collect_gitignore_spec_cumulative_line_cap(tmp_path: Path) -> None:
    """Files that push cumulative line count past 50,000 are skipped with warnings."""
    from spelunk.utils import GITIGNORE_MAX_TOTAL_LINES, collect_gitignore_spec

    # First .gitignore fills the budget exactly to the limit
    first = tmp_path / ".gitignore"
    first.write_text("\n".join(f"pattern{i}" for i in range(GITIGNORE_MAX_TOTAL_LINES)) + "\n")

    # Second .gitignore in a subdirectory — must be skipped because the cap is hit
    sub = tmp_path / "sub"
    sub.mkdir()
    second = sub / ".gitignore"
    second.write_text("extra_pattern\n")

    spec, warnings = collect_gitignore_spec(tmp_path)
    assert any(str(second) in w for w in warnings), (
        f"Expected warning for skipped {second}, got: {warnings}"
    )
    # Must not raise MemoryError — reaching here satisfies that
    # Patterns from the first file must still be applied
    assert spec.match_file("pattern0")


def test_walk_repo_oversized_gitignore_warning_propagated(tmp_path: Path) -> None:
    """walk_repo includes warnings from an oversized .gitignore in its returned warnings list."""
    from spelunk.utils import GITIGNORE_MAX_BYTES, walk_repo

    oversized = tmp_path / ".gitignore"
    content = "*.skip\n" * ((GITIGNORE_MAX_BYTES // 7) + 1)
    oversized.write_bytes(content.encode("utf-8"))
    (tmp_path / "main.py").write_text("pass")

    _file_paths, _errors, warnings = walk_repo(tmp_path)
    assert any(str(oversized) in w for w in warnings), (
        f"Expected oversized .gitignore warning in walk_repo warnings, got: {warnings}"
    )


# ---------------------------------------------------------------------------
# TASK-022: os.access replaces _can_open on the hot path
# ---------------------------------------------------------------------------

def test_can_open_not_called_for_readable_files(tmp_path: Path) -> None:
    """AC1 — _can_open must not be called when os.access would suffice.

    Monkeypatches spelunk.utils._can_open to raise, then asserts walk_repo
    completes without triggering the exception for any readable file.
    """
    from spelunk import utils

    repo = tmp_path / "repo"
    repo.mkdir()
    for i in range(5):
        (repo / f"file{i}.py").write_text("pass")

    def raising_can_open(path: Path) -> bool:  # type: ignore[override]
        raise AssertionError(f"_can_open must not be called on the hot path: {path}")

    with patch.object(utils, "_can_open", raising_can_open):
        file_paths, errors, _ = utils.walk_repo(repo)

    assert len(file_paths) == 5
    assert errors == []


@pytest.mark.skipif(os.getuid() == 0, reason="root bypasses os.access checks")
def test_os_access_false_produces_error(tmp_path: Path) -> None:
    """AC2 — a file for which os.access returns False is recorded as an error.

    Sets a file to mode 0 so os.access returns False, confirms it appears in
    errors and is absent from file_paths.
    """
    from spelunk.utils import walk_repo

    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "readable.py", "pass")
    noperm = repo / "noperm.py"
    noperm.write_text("secret")
    noperm.chmod(0)

    try:
        file_paths, errors, _ = walk_repo(repo)
        names = [p.name for p in file_paths]
        assert "readable.py" in names
        assert "noperm.py" not in names
        assert any("noperm.py" in e for e in errors)
    finally:
        noperm.chmod(stat.S_IRUSR | stat.S_IWUSR)


def test_os_access_true_file_in_file_paths(tmp_path: Path) -> None:
    """AC3 — a file for which os.access returns True appears in file_paths without error."""
    from spelunk.utils import walk_repo

    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "main.py", "pass")

    file_paths, errors, _ = walk_repo(repo)
    names = [p.name for p in file_paths]
    assert "main.py" in names
    assert errors == []


def test_walk_repo_no_unreadable_files_empty_errors(tmp_path: Path) -> None:
    """AC4 — walk_repo with all readable files returns empty errors list."""
    from spelunk.utils import walk_repo

    repo = tmp_path / "repo"
    repo.mkdir()
    for name in ("a.py", "b.py", "c.txt"):
        _write(repo / name, "content")

    _file_paths, errors, _warnings = walk_repo(repo)
    assert errors == []


# ---------------------------------------------------------------------------
# TASK-023: error paths are relative to the scan root
# ---------------------------------------------------------------------------

@pytest.mark.skipif(os.getuid() == 0, reason="root can read any file")
def test_permission_error_path_is_relative(tmp_path: Path) -> None:
    """AC1 — PermissionError on a file inside root produces a relative error path."""
    from spelunk.utils import walk_repo

    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "ok.py", "pass")
    secret = repo / "sub" / "secret.txt"
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_text("classified")
    secret.chmod(0)

    try:
        _file_paths, errors, _warnings = walk_repo(repo)
        assert errors, "Expected at least one error"
        # The error must contain a relative path (no leading slash and no tmp_path)
        perm_errors = [e for e in errors if "secret.txt" in e]
        assert perm_errors, f"No error mentioning secret.txt in {errors}"
        for e in perm_errors:
            assert str(tmp_path) not in e, (
                f"Absolute path leaked into error string: {e}"
            )
            assert not e.split(": ", 1)[-1].startswith("/"), (
                f"Error path starts with '/' (absolute): {e}"
            )
    finally:
        secret.chmod(stat.S_IRUSR | stat.S_IWUSR)
