"""Adversarial and edge-case tests for spelunk/utils.py — TASK-005.

These tests extend the engineer-written happy-path and primary-AC coverage in
test_utils.py with hostile inputs, boundary conditions, and failure modes not
covered there.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def _write(path: Path, content: str = "hello") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


# ---------------------------------------------------------------------------
# walk_repo: repo with no .gitignore at all
# ---------------------------------------------------------------------------

def test_walk_repo_no_gitignore(tmp_path: Path) -> None:
    """walk_repo must succeed on a repo that has no .gitignore file at all.

    Edge case: collect_gitignore_spec returns an empty spec; all files are
    included without error.
    """
    from spelunk.utils import walk_repo

    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "main.py", "print('hello')")
    _write(repo / "README.md", "# hi")

    file_paths, errors, warnings = walk_repo(repo)

    names = {p.name for p in file_paths}
    assert "main.py" in names
    assert "README.md" in names
    assert errors == []
    assert warnings == []


# ---------------------------------------------------------------------------
# walk_repo: empty directory
# ---------------------------------------------------------------------------

def test_walk_repo_empty_directory(tmp_path: Path) -> None:
    """walk_repo on an empty directory must return empty lists without error."""
    from spelunk.utils import walk_repo

    repo = tmp_path / "empty_repo"
    repo.mkdir()

    file_paths, errors, warnings = walk_repo(repo)

    assert file_paths == []
    assert errors == []
    assert warnings == []


# ---------------------------------------------------------------------------
# walk_repo: nested .gitignore excludes paths in subdirectory
# ---------------------------------------------------------------------------

def test_nested_gitignore_excludes_subdirectory_files(tmp_path: Path) -> None:
    """A .gitignore in a subdirectory must exclude files within that subtree.

    This exercises collect_gitignore_spec's multi-.gitignore merging logic.
    """
    from spelunk.utils import walk_repo

    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "keep.py", "pass")

    # Nested .gitignore inside 'vendor/' excludes *.log
    vendor = repo / "vendor"
    _write(vendor / ".gitignore", "*.log\n")
    _write(vendor / "lib.js", "// ok")
    _write(vendor / "debug.log", "log output")

    file_paths, errors, warnings = walk_repo(repo)
    names = [p.name for p in file_paths]
    assert "keep.py" in names
    assert "lib.js" in names
    assert "debug.log" not in names


# ---------------------------------------------------------------------------
# walk_repo: binary file is included in file_paths (extension counting)
# ---------------------------------------------------------------------------

def test_binary_file_included_in_file_paths(tmp_path: Path) -> None:
    """A binary file must appear in file_paths so its extension is counted.

    Binary detection is the analyser's responsibility; walk_repo includes it.
    """
    from spelunk.utils import walk_repo

    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "source.py", "pass")
    binary = repo / "image.png"
    binary.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00")  # PNG magic + null byte

    file_paths, errors, warnings = walk_repo(repo)
    names = [p.name for p in file_paths]
    assert "image.png" in names
    assert "source.py" in names


# ---------------------------------------------------------------------------
# is_binary: null byte appearing exactly at byte 8192 boundary
# ---------------------------------------------------------------------------

def test_is_binary_null_byte_at_boundary(tmp_path: Path) -> None:
    """Null byte at position 8191 (last byte of 8 KB window) must be detected."""
    from spelunk.utils import BINARY_READ_BYTES, is_binary

    f = tmp_path / "boundary.bin"
    # Write exactly BINARY_READ_BYTES bytes, last byte is null
    f.write_bytes(b"x" * (BINARY_READ_BYTES - 1) + b"\x00")
    assert is_binary(f) is True


def test_is_binary_null_byte_beyond_window(tmp_path: Path) -> None:
    """Null byte appearing AFTER the 8 KB window must NOT be detected as binary.

    The spec says only the first 8 KB is read; content beyond that is ignored.
    """
    from spelunk.utils import BINARY_READ_BYTES, is_binary

    f = tmp_path / "late_null.bin"
    # BINARY_READ_BYTES bytes of text, then a null byte — only first window read
    f.write_bytes(b"a" * BINARY_READ_BYTES + b"\x00")
    assert is_binary(f) is False


# ---------------------------------------------------------------------------
# is_binary: returns False on PermissionError (not OSError propagation)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(os.getuid() == 0, reason="root can read any file")
def test_is_binary_returns_false_on_permission_error(tmp_path: Path) -> None:
    """is_binary must return False (not raise) when the file cannot be opened.

    Spec: 'Return False on PermissionError or OSError'.
    """
    from spelunk.utils import is_binary

    f = tmp_path / "noperm.bin"
    f.write_bytes(b"\x00binary")
    f.chmod(0)
    try:
        result = is_binary(f)
        assert result is False
    finally:
        import stat
        f.chmod(stat.S_IRUSR | stat.S_IWUSR)


# ---------------------------------------------------------------------------
# is_ignored: path outside root returns False (does not raise ValueError)
# ---------------------------------------------------------------------------

def test_is_ignored_path_outside_root_returns_false(tmp_path: Path) -> None:
    """is_ignored must return False — not raise — when path is not under root."""
    from spelunk.utils import collect_gitignore_spec, is_ignored
    import pathspec

    root = tmp_path / "root"
    root.mkdir()
    spec = pathspec.PathSpec.from_lines("gitignore", [])
    outside = tmp_path / "outside.py"
    outside.write_text("pass")
    # Must not raise ValueError
    result = is_ignored(outside, root, spec)
    assert result is False


# ---------------------------------------------------------------------------
# walk_repo: large file exactly at threshold is NOT warned; one byte over IS
# ---------------------------------------------------------------------------

def test_large_file_exactly_at_threshold_not_warned(tmp_path: Path) -> None:
    """A file exactly equal to LARGE_FILE_THRESHOLD_BYTES must NOT produce a warning.

    The spec says 'exceeding 10 MB', i.e. strictly greater than.
    """
    from spelunk.utils import LARGE_FILE_THRESHOLD_BYTES, walk_repo

    repo = tmp_path / "repo"
    repo.mkdir()
    exact = repo / "exact.bin"
    exact.write_bytes(b"x" * LARGE_FILE_THRESHOLD_BYTES)

    file_paths, errors, warnings = walk_repo(repo)
    names = [p.name for p in file_paths]
    assert "exact.bin" in names
    assert not any("exact.bin" in w for w in warnings), (
        "File at exactly the threshold should not trigger a large-file warning"
    )


def test_large_file_one_byte_over_threshold_warned(tmp_path: Path) -> None:
    """A file one byte over LARGE_FILE_THRESHOLD_BYTES must produce a warning."""
    from spelunk.utils import LARGE_FILE_THRESHOLD_BYTES, walk_repo

    repo = tmp_path / "repo"
    repo.mkdir()
    over = repo / "over.bin"
    over.write_bytes(b"x" * (LARGE_FILE_THRESHOLD_BYTES + 1))

    file_paths, errors, warnings = walk_repo(repo)
    names = [p.name for p in file_paths]
    assert "over.bin" in names
    assert any("over.bin" in w for w in warnings)


# ---------------------------------------------------------------------------
# walk_repo: multiple files with PermissionError — walk continues for all
# ---------------------------------------------------------------------------

@pytest.mark.skipif(os.getuid() == 0, reason="root can read any file")
def test_walk_continues_after_multiple_permission_errors(tmp_path: Path) -> None:
    """walk_repo must continue and collect remaining files after multiple PermissionErrors."""
    import stat
    from spelunk.utils import walk_repo

    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "readable.py", "pass")
    secret1 = repo / "secret1.txt"
    secret1.write_text("classified")
    secret2 = repo / "secret2.txt"
    secret2.write_text("also classified")
    secret1.chmod(0)
    secret2.chmod(0)

    try:
        file_paths, errors, warnings = walk_repo(repo)
        names = [p.name for p in file_paths]
        assert "readable.py" in names
        assert any("secret1.txt" in e for e in errors)
        assert any("secret2.txt" in e for e in errors)
    finally:
        secret1.chmod(stat.S_IRUSR | stat.S_IWUSR)
        secret2.chmod(stat.S_IRUSR | stat.S_IWUSR)


# ---------------------------------------------------------------------------
# walk_repo: symlink to a file within repo root IS included
# ---------------------------------------------------------------------------

def test_symlink_within_root_is_included(tmp_path: Path) -> None:
    """A symlink whose resolved target is inside the repo root must appear in file_paths."""
    from spelunk.utils import walk_repo

    repo = tmp_path / "repo"
    repo.mkdir()
    real = repo / "real.py"
    real.write_text("pass")
    link = repo / "alias.py"
    link.symlink_to(real)

    file_paths, errors, warnings = walk_repo(repo)
    names = [p.name for p in file_paths]
    assert "real.py" in names
    assert "alias.py" in names
    assert errors == []


# ---------------------------------------------------------------------------
# schema: OUTPUT_SCHEMA has additionalProperties = false at root
# ---------------------------------------------------------------------------

def test_output_schema_additional_properties_false() -> None:
    """OUTPUT_SCHEMA must set additionalProperties to false at the root level.

    This ensures the drift test will catch fields added to the output that
    are not listed in the schema.
    """
    from spelunk.schema import OUTPUT_SCHEMA

    assert OUTPUT_SCHEMA.get("additionalProperties") is False, (
        "OUTPUT_SCHEMA must have additionalProperties: false to catch schema drift"
    )


# ---------------------------------------------------------------------------
# models: RepoScanResult to_dict round-trips through json.loads correctly
# ---------------------------------------------------------------------------

def test_repo_scan_result_to_dict_round_trip_values() -> None:
    """to_dict() values must round-trip through json.loads with correct types.

    Verifies that no Path objects or other non-JSON-native types leak through.
    """
    import json
    from spelunk.models import (
        DependenciesInfo,
        FileTreeInfo,
        GitInfo,
        LanguageInfo,
        NotableFiles,
        RepoInfo,
        RepoScanResult,
        ScanMeta,
        TestingInfo,
    )

    result = RepoScanResult(
        schema_version="1.0.0",
        scanned_at="2026-06-16T00:00:00Z",
        repo=RepoInfo(
            name="test", description=None, version=None, license=None, root_path="/tmp"
        ),
        git=GitInfo(
            present=False,
            remote_url=None,
            default_branch=None,
            last_commit=None,
            contributor_count=None,
            tags=[],
        ),
        languages=LanguageInfo(primary=None, languages=[]),
        frameworks=[],
        file_tree=FileTreeInfo(
            total_files=0,
            total_bytes=0,
            max_depth=0,
            extensions=[],
            notable_files=NotableFiles(),
        ),
        dependencies=DependenciesInfo(),
        testing=TestingInfo(),
        meta=ScanMeta(scanner_version="0.1.0"),
    )

    raw = json.loads(json.dumps(result.to_dict()))
    # git.present must be bool False — not None or 0
    assert raw["git"]["present"] is False
    # languages.primary must be None (JSON null)
    assert raw["languages"]["primary"] is None
    # All list fields must be lists
    assert isinstance(raw["frameworks"], list)
    assert isinstance(raw["file_tree"]["extensions"], list)
    assert isinstance(raw["meta"]["errors"], list)
    assert isinstance(raw["meta"]["warnings"], list)
