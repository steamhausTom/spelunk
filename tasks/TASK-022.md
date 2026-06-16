# TASK-022: Optimise walk_repo hot path by gating the _can_open probe on mode bits

**Status**: In Review
**Wave**: 1 — Remediation
**Effort**: S — replace the unconditional `_can_open()` call with a mode-bit check that only falls back to open() when permission is ambiguous; benchmark confirms improvement at scale
**Base Branch**: feature/wave-1-foundation
**Dependencies**: TASK-005

## Description

`_can_open` performs a full `open()` syscall on every file in the walk, in addition to the `stat()` call already performed for size. For a 50k-file repo this doubles the number of syscalls on the hot path, significantly increasing wall-clock scan time.

For the majority of files, readability can be determined from the mode bits already returned by `stat()`:
- If `stat().st_mode` indicates the file is readable by the current process (using `os.access(path, os.R_OK)` or mode-bit inspection), skip the `open()` probe entirely.
- Only fall back to `_can_open()` when the mode bits are ambiguous — e.g. the file is owned by root with `0o004` (world-readable) and the effective UID is not root, where `os.access` gives the authoritative answer.

The recommended implementation: replace the `_can_open(path)` call with `os.access(path, os.R_OK)`, which uses the kernel's access check (honours ACLs, set-uid, etc.) without opening the file. `_can_open` can be retained as a private helper for test purposes but should not be called on the hot path.

Affected: `spelunk/utils.py:179-185` (the `_can_open` call site) and `spelunk/utils.py:193-205` (the helper itself).

## Acceptance Criteria

- [x] [eng] Given a repo of 1,000 readable files · When `walk_repo` runs · Then `_can_open` is not called for any of those files (confirmed by monkeypatching `_can_open` to raise and asserting no exception)
- [x] [eng] Given a file for which `os.access(path, os.R_OK)` returns `False` · When `walk_repo` runs · Then the file is recorded as an error and is absent from `file_paths`
- [x] [eng] Given a file for which `os.access(path, os.R_OK)` returns `True` · When `walk_repo` runs · Then the file appears in `file_paths` without errors
- [x] [eng] Given the optimised `walk_repo` with no unreadable files · When `walk_repo` returns · Then the `errors` list is empty (no regression in error-path handling)

## Notes / Risks

- `os.access` uses the real UID/GID on Linux and the effective UID on macOS. This is the correct check for determining whether the current process can open the file.
- The behaviour change is observable only in edge cases involving mode-0 files or ACL-controlled files. Existing tests are not expected to break.
- This is a Low-severity refactor. It does not block the Wave 1 PR but is grouped with other Wave 1 remediation tasks because it touches the same hot-path code as TASK-017 and TASK-019 and is cheapest to apply here.
- The `@pytest.mark.slow` 50k-file performance test (TASK-016) will serve as the benchmark regression test for this optimisation.
