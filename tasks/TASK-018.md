# TASK-018: Fix nested .gitignore rules to apply relative to their own directory only

**Status**: Pending
**Wave**: 1 — Remediation
**Effort**: M — requires reworking `collect_gitignore_spec` from a flat merge to a per-directory spec strategy; involves a moderate refactor of the is_ignored call path
**Base Branch**: feature/wave-1-foundation
**Dependencies**: TASK-017

## Description

`collect_gitignore_spec` currently flattens all `.gitignore` patterns across every nested `.gitignore` into a single global `PathSpec`. This violates git semantics: a pattern in `subdir/.gitignore` should only exclude files within `subdir/`, not files with the same name elsewhere in the repo.

For example, if `subdir/.gitignore` contains `foo.txt`, the current implementation will also exclude `root/foo.txt` and `other/foo.txt` — over-excluding files that git would include.

The fix requires replacing the flat-merge strategy with a per-directory spec approach:
- For each `.gitignore` found at `dir/.gitignore`, build a `PathSpec` scoped to that directory.
- When checking whether a path is ignored, find all `.gitignore` specs whose directory is an ancestor of (or equal to) the path's parent directory, and evaluate each spec using the path relative to that spec's directory.

This may require changing the signature of `collect_gitignore_spec` and `is_ignored`, or introducing a new helper type to carry the `(directory, PathSpec)` pairs.

Affected module: `spelunk/utils.py:30-60`.

## Acceptance Criteria

- [ ] [eng] Given a nested `subdir/.gitignore` containing `foo.txt` and a `foo.txt` at the repo root · When `walk_repo` runs · Then the root-level `foo.txt` is present in `file_paths` and `subdir/foo.txt` is absent
- [ ] [eng] Given a root `.gitignore` containing `*.log` and a `subdir/.gitignore` containing `*.tmp` · When `walk_repo` runs · Then `.log` files anywhere in the repo are excluded, and `.tmp` files outside `subdir/` are included
- [ ] [eng] Given a repo with only a root `.gitignore` (no nested gitignore files) · When `walk_repo` runs · Then behaviour is identical to the current flat-merge implementation (no regression)
- [ ] [eng] Given `collect_gitignore_spec` (or its replacement) is called on a repo · When it returns · Then the returned structure can be queried with a `(path, ancestor_dir)` pair to determine exclusion

## Notes / Risks

- This is a Medium-severity correctness bug. It does not block the Wave 1 PR on its own (severity is Medium, not High), but it is sequenced here to be fixed on the same branch before Wave 2 code starts calling `walk_repo` in more complex repos.
- Reworking `is_ignored`'s signature may require updating call sites in `walk_repo` (lines 121 and 153) and in any existing tests.
- Consider a `list[tuple[Path, PathSpec]]` — one entry per discovered `.gitignore` — sorted by directory depth. Evaluation iterates the list and checks only specs whose directory is an ancestor of the path.
- TASK-017 (resolved root consistency) must be merged first: the per-directory spec approach depends on consistent resolved paths.
- Sequenced as a dependency of TASK-019 (coverage tests), which pins all four STR-F1–F4 scenarios.
