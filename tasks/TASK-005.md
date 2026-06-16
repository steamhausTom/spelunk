# TASK-005: Implement utils.py — directory walk, .gitignore filtering, and symlink containment

**Status**: Pending
**Wave**: 1
**Assignee**: tc-backend-engineer
**Effort**: M — three distinct behaviours (walk, gitignore, symlink safety) each with non-trivial edge cases
**Base Branch**: main
**Dependencies**: None

## Description

Implement `spelunk/utils.py` — the filesystem traversal layer consumed by `scanner.py` to produce the filtered path list passed to all analysers via `ScanInputs.file_paths`.

This module is the gatekeeper: nothing outside the repo root, nothing in gitignored paths, and no symlink cycles or scope escapes should reach an analyser.

### Functions to implement

#### `collect_gitignore_spec(root: Path) -> pathspec.PathSpec`

Walk the directory tree and collect all `.gitignore` files (root and nested). Build a single `pathspec.PathSpec` from all rules using `pathspec.PathSpec.from_lines("gitwildmatch", lines)`. Return the combined spec.

Rules:
- Include the root `.gitignore` if present.
- Include any `.gitignore` found in subdirectories encountered during the walk.
- Use `pathspec` — do NOT hand-roll gitignore semantics.

#### `is_ignored(path: Path, root: Path, spec: pathspec.PathSpec) -> bool`

Return `True` if `path` should be excluded. Compute the path relative to `root` and test against `spec`. Always use forward slashes for the relative path string (pathspec expects POSIX-style).

#### `is_binary(path: Path) -> bool`

Read the first 8 KB of the file. Return `True` if a null byte (`\x00`) is present. Return `False` on `PermissionError` or `OSError` (let the walk handle those separately).

#### `walk_repo(root: Path) -> tuple[list[Path], list[str], list[str]]`

The primary entry point. Returns `(file_paths, errors, warnings)`:
- `file_paths`: all non-ignored, non-binary-content-skipped, non-scope-escaped paths to regular files.
- `errors`: list of error message strings for paths that raised `PermissionError`.
- `warnings`: list of warning strings for files exceeding 10 MB.

Walk algorithm:
1. Resolve `root` to an absolute real path.
2. Build `spec` via `collect_gitignore_spec(root)`.
3. Walk using `os.walk` (or `Path.rglob`) with `followlinks=True`.
4. For each entry encountered:
   a. **Gitignore check**: skip if `is_ignored(path, root, spec)` is `True`.
   b. **Symlink cycle check**: if the path is a symlink, resolve it and check whether the resolved inode is already in a `visited_inodes: set[int]` set. If yes, skip silently. If no, add `os.stat(resolved).st_ino` to the set.
   c. **Symlink scope escape check** (F7): if the path is a symlink, resolve it via `.resolve()`. If the resolved path is not within `root.resolve()`, skip it — do NOT add to `file_paths`, do NOT add to errors. This prevents external files (e.g. `/etc/passwd`, `~/.ssh`) from entering the scan.
   d. **PermissionError**: catch `PermissionError` on `os.stat()` or file open; add `f"Permission denied: {path}"` to `errors`; continue.
   e. **Large file check**: if `path.stat().st_size > 10 * 1024 * 1024` (10 MB), add a warning `f"Large file skipped: {path}"` to `warnings`; add the path to `file_paths` anyway (so extension stats are recorded) but mark it so the content is not read. Use a sentinel: return a second list `large_file_paths` or set a flag. Simpler approach: include large files in `file_paths` and let each analyser check `path.stat().st_size` before reading. Document the convention in a module-level docstring.
   f. **Binary check**: call `is_binary(path)`. If `True`, include in `file_paths` (extension is recorded) but do NOT read content — analysers check `is_binary()` before reading.
   g. Add to `file_paths`.

Binary files and large files ARE included in `file_paths` so that `file_tree.py` can count them and record their extensions. Analysers that care about content (language/dependency detection) must guard with `is_binary()` and size checks before reading.

### Constants (module level)

```python
LARGE_FILE_THRESHOLD_BYTES = 10 * 1024 * 1024  # 10 MB
BINARY_READ_BYTES = 8192  # 8 KB
```

## Acceptance Criteria

- [ ] [eng] Given a repo with a `.gitignore` containing `node_modules/` · When `walk_repo` runs · Then no path inside `node_modules/` appears in the returned `file_paths`
- [ ] [eng] Given a symlink pointing to a file outside the scan root · When `walk_repo` runs · Then the symlink target does not appear in `file_paths` and no error is added
- [ ] [eng] Given a symlink cycle within the repo · When `walk_repo` runs · Then the walk terminates (no infinite loop), the cyclic link is not in `file_paths`, and no error is added
- [ ] [eng] Given a file that raises `PermissionError` on stat · When `walk_repo` runs · Then the path appears in the returned `errors` list and the walk continues to completion
- [ ] [eng] Given a file larger than 10 MB · When `walk_repo` runs · Then the path is in `file_paths` and a warning string is in the returned `warnings` list
- [ ] [eng] Given a file containing a null byte in its first 8 KB · When `is_binary` is called · Then it returns `True`
- [ ] [eng] Given a plain text file with no null bytes · When `is_binary` is called · Then it returns `False`
- [ ] [eng] Given `mypy --strict` runs against `utils.py` · When it completes · Then zero type errors are reported

## Notes / Risks

- **Scope escape check (F7)** is security-critical. The check is `not resolved_symlink.is_relative_to(resolved_root)`. Use `Path.is_relative_to()` (Python 3.9+, fine for our 3.10 target) rather than string prefix matching (fragile on case-insensitive filesystems or paths with `..` components).
- `os.walk` with `followlinks=True` will follow symlinks into subdirectories. The inode-based cycle detection handles the loop case; the scope escape check handles the external-target case. Both checks are required — they are not redundant.
- The `pathspec.PathSpec` object is stateful only in the sense of holding compiled patterns — it is safe to construct once and reuse across the walk.
- Nested `.gitignore` files: collect them during the walk itself. The simplest approach is a two-pass: first collect all `.gitignore` files via a walk, then re-walk using the combined spec. This is inefficient but correct. An alternative is to build the spec incrementally and accept that directories encountered before their `.gitignore` is found may not be filtered — document the chosen behaviour.
- On macOS (HFS+), `st_ino` may not be unique across volumes. The resolved-path containment check is the primary safety mechanism; inode dedup is a cycle-detection secondary.
