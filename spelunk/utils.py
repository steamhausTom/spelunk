"""Filesystem traversal utilities for spelunk.

This module is the gatekeeper for the scan: nothing outside the repo root,
nothing in gitignored paths, and no symlink cycles or scope escapes should
reach an analyser.

Binary files and large files ARE included in the returned file_paths list so
that file_tree.py can record their extensions and counts. Analysers that read
file content must guard with:
    - is_binary(path) before reading content
    - path.stat().st_size <= LARGE_FILE_THRESHOLD_BYTES before reading content

Large file convention: a large file IS added to file_paths (so the extension is
counted) but a warning is emitted. Analysers must check the size before reading.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pathspec

# Module-level constants
LARGE_FILE_THRESHOLD_BYTES: int = 10 * 1024 * 1024  # 10 MB
BINARY_READ_BYTES: int = 8192  # 8 KB


def collect_gitignore_spec(root: Path) -> "pathspec.PathSpec[Any]":
    """Walk the directory tree and build a combined PathSpec from all .gitignore files.

    Rules from root .gitignore and all nested .gitignore files are merged into
    a single PathSpec using the gitwildmatch pattern syntax. The walk does not
    follow symlinks here (we only want gitignore files in the real tree).
    """
    lines: list[str] = []

    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        if ".gitignore" in filenames:
            gitignore_path = Path(dirpath) / ".gitignore"
            try:
                content = gitignore_path.read_text(encoding="utf-8", errors="replace")
                lines.extend(content.splitlines())
            except (PermissionError, OSError):
                pass  # skip unreadable .gitignore files silently

    return pathspec.PathSpec.from_lines("gitignore", lines)


def is_ignored(path: Path, root: Path, spec: "pathspec.PathSpec[Any]") -> bool:
    """Return True if path should be excluded based on the combined gitignore spec."""
    try:
        # Use POSIX-style relative paths — pathspec expects forward slashes
        relative = path.relative_to(root).as_posix()
        return spec.match_file(relative)
    except ValueError:
        # path is not relative to root — should not happen in normal walk
        return False


def is_binary(path: Path) -> bool:
    """Return True if the file contains a null byte in its first 8 KB.

    Returns False on PermissionError or OSError — the walk handles those separately.
    """
    try:
        with open(path, "rb") as f:
            chunk = f.read(BINARY_READ_BYTES)
        return b"\x00" in chunk
    except (PermissionError, OSError):
        return False


def walk_repo(root: Path) -> tuple[list[Path], list[str], list[str]]:
    """Walk the repository at root and return a filtered list of file paths.

    Returns:
        file_paths: all non-ignored, non-scope-escaped paths to regular files.
                    Binary files and large files ARE included so extension stats
                    can be recorded; content guards are the analyser's responsibility.
        errors: error message strings for paths that raised PermissionError.
        warnings: warning strings for files exceeding LARGE_FILE_THRESHOLD_BYTES.

    Security properties enforced:
    - Symlinks whose resolved target is outside root are silently dropped (scope escape).
    - Symlink cycles are detected via directory inode tracking and skipped silently.
    - Gitignored paths are excluded using pathspec gitignore semantics.
    """
    resolved_root = root.resolve()
    spec = collect_gitignore_spec(root)

    file_paths: list[Path] = []
    errors: list[str] = []
    warnings: list[str] = []

    # Track visited directory inodes to detect cycles when followlinks=True.
    # This set is populated as we enter each directory (including via symlink).
    visited_dir_inodes: set[int] = set()

    # Seed with the root directory's inode
    try:
        root_stat = os.stat(str(resolved_root))
        visited_dir_inodes.add(root_stat.st_ino)
    except (OSError, PermissionError):
        pass

    for dirpath_str, dirnames, filenames in os.walk(
        str(root), followlinks=True, topdown=True
    ):
        dirpath = Path(dirpath_str)

        # Build the pruned list of child directories to descend into.
        # For each child dir, apply: .git exclusion, gitignore filter, scope escape check,
        # and cycle detection (inode dedup).
        valid_dirs: list[str] = []
        for dname in dirnames:
            # Always skip the .git directory — git never lists it in .gitignore
            # and its internals (loose objects, pack files, refs) pollute stats.
            if dname == ".git":
                continue

            child_dir = dirpath / dname

            # Gitignore check on the directory
            if is_ignored(child_dir, resolved_root, spec):
                continue

            # Resolve target for symlink directories
            try:
                resolved_child = child_dir.resolve()
            except (OSError, RuntimeError):
                continue  # broken symlink directory

            # Scope escape check
            if not _is_within(resolved_child, resolved_root):
                continue

            # Cycle / dedup detection via inode
            try:
                child_inode = os.stat(str(resolved_child)).st_ino
            except (OSError, PermissionError):
                continue

            if child_inode in visited_dir_inodes:
                continue  # cycle — skip silently

            visited_dir_inodes.add(child_inode)
            valid_dirs.append(dname)

        dirnames[:] = valid_dirs

        # Process files in this directory
        for filename in filenames:
            path = dirpath / filename

            # Gitignore check
            if is_ignored(path, resolved_root, spec):
                continue

            # Symlink handling for files
            if path.is_symlink():
                try:
                    resolved_target = path.resolve()
                except (OSError, RuntimeError):
                    # Broken symlink — skip silently
                    continue

                # Scope escape check (F7): target must be within the scan root
                if not _is_within(resolved_target, resolved_root):
                    continue  # silently drop — no error added

            # Permission / stat check
            try:
                size = path.stat().st_size
            except PermissionError:
                errors.append(f"Permission denied: {path}")
                continue
            except OSError as exc:
                errors.append(f"OS error: {path}: {exc}")
                continue

            # Check open permission explicitly (stat may succeed on owned mode-0 files)
            if not _can_open(path):
                errors.append(f"Cannot open for reading: {path}")
                continue

            # Large file check
            if size > LARGE_FILE_THRESHOLD_BYTES:
                warnings.append(f"Large file skipped: {path}")
                # Include in file_paths so extension stats are recorded

            file_paths.append(path)

    return file_paths, errors, warnings


def _can_open(path: Path) -> bool:
    """Return True if the file can be opened for reading.

    Attempts a read-only open and immediately closes. Used to detect
    permission errors that stat() does not surface (e.g. on macOS when
    the file is owned by the current user but has mode 0).
    """
    try:
        with open(path, "rb"):
            pass
        return True
    except (PermissionError, OSError):
        return False


def _is_within(target: Path, root: Path) -> bool:
    """Return True if target is within root (inclusive).

    Uses Path.is_relative_to() (Python 3.9+) which is correct on all
    platforms including case-insensitive filesystems.
    """
    try:
        return target.is_relative_to(root)
    except ValueError:
        return False
