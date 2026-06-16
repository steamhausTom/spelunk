# TASK-017: Fix root vs resolved_root mismatch in walk_repo that silently disables .gitignore filtering

**Status**: In Review
**Wave**: 1 — Remediation
**Effort**: S — two-line fix in walk, plus ensuring `is_ignored` and `collect_gitignore_spec` all receive the same resolved root; test authoring is modest
**Base Branch**: feature/wave-1-foundation
**Dependencies**: TASK-005

## Description

`walk_repo` resolves `root` to `resolved_root` (line 90) but passes the original `str(root)` to `os.walk`. When `root` is a relative path or contains a symlinked component (e.g. `/tmp` → `/private/tmp` on macOS), `path.relative_to(resolved_root)` inside `is_ignored` raises `ValueError`. The `except ValueError` clause in `is_ignored` returns `False`, silently disabling all `.gitignore` filtering for the entire walk.

The fix is to use `resolved_root` consistently as the `os.walk` base and as the root argument to every `is_ignored` call — so the relative-path computation is always comparing two resolved paths.

Affected lines: `spelunk/utils.py:90,108,121,153`.

## Acceptance Criteria

- [x] [eng] Given a repo invoked via a relative path (e.g. `Path(".")` run from inside the repo) · When `walk_repo` runs against a `.gitignore` containing `node_modules/` · Then no paths under `node_modules/` appear in `file_paths`
- [x] [eng] Given a repo path whose components contain a symlinked segment (e.g. `/tmp/repo` where `/tmp` resolves to `/private/tmp`) · When `walk_repo` runs · Then `.gitignore` rules are still applied (no silent suppression)
- [x] [eng] Given `walk_repo` · When it walks · Then the base path passed to `os.walk` and the `root` argument to every `is_ignored` call are both the same resolved absolute path
- [x] [eng] Given `walk_repo` is called with a relative path · When it returns · Then `is_ignored` never raises `ValueError` and no path is silently included due to the exception fallback

## Notes / Risks

- The fix is low-risk: change `os.walk(str(root))` to `os.walk(str(resolved_root))` and propagate `resolved_root` to the two `is_ignored` call sites at lines 121 and 153.
- `collect_gitignore_spec` is called with the original `root` (line 91) — this only matters for finding `.gitignore` files, not for applying the spec. However it should also receive `resolved_root` for consistency.
- Existing `tmp_path`-based tests pass because `tmp_path` is already a fully resolved path. New tests (TASK-018) must exercise the unresolved-root and symlinked-component scenarios explicitly.
- Resolving this finding is a blocking prerequisite for raising the Wave 1 PR.
