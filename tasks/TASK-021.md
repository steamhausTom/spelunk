# TASK-021: Add size cap to .gitignore reads in collect_gitignore_spec to prevent memory exhaustion

**Status**: In Review
**Wave**: 1 — Remediation
**Effort**: S — add a pre-read size check and a cumulative line-count guard to the existing read loop; test with an oversized fixture
**Base Branch**: feature/wave-1-foundation
**Dependencies**: TASK-005

## Description

`collect_gitignore_spec` reads every `.gitignore` encountered during the walk using `gitignore_path.read_text()` with no size limit. A crafted or accidentally large `.gitignore` (e.g. a 1 GB file) will exhaust process memory. There is also no cumulative cap on the total number of lines accumulated across all `.gitignore` files in a deep monorepo.

Two guards are needed:

1. **Per-file size cap**: before reading, stat the `.gitignore` file. If its size exceeds 1 MB, skip it and append a warning: `"Skipped oversized .gitignore: {path} ({size} bytes)"`.
2. **Cumulative line cap**: track the total number of lines accumulated. If adding the current file would push the total past 50,000 lines, skip all remaining `.gitignore` files and append a warning for each: `"Skipped .gitignore due to line cap: {path}"`.

Both caps must surface warnings through the return value — `collect_gitignore_spec` must return a tuple `(PathSpec, list[str])` where the second element is the list of warning strings for the caller (`walk_repo`) to append to its `warnings` list.

Affected module: `spelunk/utils.py:30-48`.

## Acceptance Criteria

- [x] [eng] Given a `.gitignore` file whose size exceeds 1 MB · When `collect_gitignore_spec` is called · Then the file is skipped, the returned `PathSpec` excludes its patterns, and a warning string is returned naming the skipped file
- [x] [eng] Given `.gitignore` files whose combined line count exceeds 50,000 · When `collect_gitignore_spec` is called · Then accumulation stops at the cap, a warning string is returned for each file that was skipped, and no `MemoryError` is raised
- [x] [eng] Given a normal repo where no `.gitignore` exceeds the caps · When `collect_gitignore_spec` is called · Then behaviour is identical to the current implementation (no regression) and the returned warnings list is empty
- [x] [eng] Given `walk_repo` is called on a repo with an oversized `.gitignore` · When it returns · Then the oversized-file warning appears in the returned `warnings` list
- [ ] [qa] Given a repository with a `.gitignore` file of 2 MB · When `walk_repo` is called · Then it completes in under 2 seconds and a warning naming the skipped file appears in the returned warnings

## Notes / Risks

- This is a High-severity security finding. It is a blocking prerequisite for raising the Wave 1 PR.
- Changing `collect_gitignore_spec` to return `(PathSpec, list[str])` is a breaking signature change. The call site in `walk_repo` (line 91) must be updated accordingly.
- Any existing test that calls `collect_gitignore_spec` directly must be updated to unpack the tuple.
- The 1 MB and 50,000-line caps are the specified defaults. Add module-level constants `GITIGNORE_MAX_BYTES` and `GITIGNORE_MAX_TOTAL_LINES` so they can be adjusted without hunting through the code.
- The 2-second wall-clock assertion in the QA AC is a performance pin, not a functional correctness test. Mark it `@pytest.mark.slow` and ensure it uses a real-filesystem fixture (not mocked), consistent with the project's no-mock-filesystem convention.
