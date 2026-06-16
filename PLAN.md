# Project Plan: spelunk Initial Build

## Overview

`spelunk` is a greenfield Python CLI utility and importable library that performs static analysis on a local code repository and emits a single versioned JSON document. This plan covers the complete initial build: project scaffold, all five analysers, all seven ecosystem dependency parsers, the public API contract, output schema, and the full pytest test suite. The architect has defined the analyser `Protocol` interface, error envelope contract, framework detection strategy, schema versioning guard, and security constraints (symlink containment, static `setup.py` parsing) — all of which are reflected in the task ordering below.

## Assumptions

- Python 3.10+ is the target runtime; `match` statements and `X | Y` union syntax are permitted.
- All tasks are greenfield (no existing code to preserve or refactor).
- `tc-frontend-engineer` has no scope in this project — it is a CLI/library only.
- All implementation tasks are `tc-backend-engineer`; there is no platform scope (this is a local CLI tool only).
- `from_dict()` on models is explicitly out of scope per architect decision (F5).
- The framework detection rule table is bounded to the 14 frameworks named in F3.
- The `build_repo` factory fixture (F9) is owned by `tc-qa-test-engineer` and is available from Wave 2 onwards to support integration test authoring.
- A `tests/fixtures/` directory exists for static content but the primary fixture strategy is `build_repo` on `tmp_path`.
- The schema drift test (F4) requires a complete scan output to validate against and so is placed after all analysers are implemented.

## Open Decisions

- [x] Analyser interface shape — resolved by architect: `typing.Protocol` in `interfaces.py` (F1).
- [x] Framework detection matrix — resolved by architect: bounded in-source rule table of 14 frameworks (F3).

---

## Task Index

### Wave 1 — Foundation: packaging, data layer, interfaces, and utils

| ID | Title | Assignee | Status | Effort | Depends On | Task File |
|----|-------|----------|--------|--------|------------|-----------|
| TASK-001 | Scaffold pyproject.toml and project packaging | tc-backend-engineer | Pending | S | None | [tasks/TASK-001.md](tasks/TASK-001.md) |
| TASK-002 | Implement models.py data layer | tc-backend-engineer | Pending | S | None | [tasks/TASK-002.md](tasks/TASK-002.md) |
| TASK-003 | Implement schema.py with SCHEMA_VERSION and JSON Schema dict | tc-backend-engineer | Pending | S | None | [tasks/TASK-003.md](tasks/TASK-003.md) |
| TASK-004 | Implement interfaces.py Analyser Protocol | tc-backend-engineer | Pending | S | None | [tasks/TASK-004.md](tasks/TASK-004.md) |
| TASK-005 | Implement utils.py: directory walk, .gitignore filtering, symlink containment | tc-backend-engineer | Pending | M | None | [tasks/TASK-005.md](tasks/TASK-005.md) |

### Wave 2 — Core pipeline: first end-to-end slice + test infrastructure

| ID | Title | Assignee | Status | Effort | Depends On | Task File |
|----|-------|----------|--------|--------|------------|-----------|
| TASK-006 | Implement file_tree.py analyser | tc-backend-engineer | Pending | M | TASK-002, TASK-004, TASK-005 | [tasks/TASK-006.md](tasks/TASK-006.md) |
| TASK-007 | Implement scanner.py orchestrator and __init__.py public API | tc-backend-engineer | Pending | M | TASK-002, TASK-003, TASK-004, TASK-006 | [tasks/TASK-007.md](tasks/TASK-007.md) |
| TASK-008 | Implement __main__.py CLI entry point | tc-backend-engineer | Pending | S | TASK-007 | [tasks/TASK-008.md](tasks/TASK-008.md) |
| TASK-009 | Establish conftest.py build_repo factory and test infrastructure | tc-qa-test-engineer | Pending | M | TASK-001, TASK-007 | [tasks/TASK-009.md](tasks/TASK-009.md) |

### Wave 3 — Independent analysers: git metadata and dependency parsing

| ID | Title | Assignee | Status | Effort | Depends On | Task File |
|----|-------|----------|--------|--------|------------|-----------|
| TASK-010 | Implement git_meta.py analyser | tc-backend-engineer | Pending | M | TASK-002, TASK-004, TASK-007 | [tasks/TASK-010.md](tasks/TASK-010.md) |
| TASK-011 | Implement dependencies.py: Python and Node ecosystem parsers | tc-backend-engineer | Pending | M | TASK-002, TASK-004, TASK-007 | [tasks/TASK-011.md](tasks/TASK-011.md) |
| TASK-012 | Implement dependencies.py: Go, Rust, Ruby, Java/Kotlin, PHP ecosystem parsers | tc-backend-engineer | Pending | M | TASK-011 | [tasks/TASK-012.md](tasks/TASK-012.md) |

### Wave 4 — Derived analysers: languages/frameworks and testing

| ID | Title | Assignee | Status | Effort | Depends On | Task File |
|----|-------|----------|--------|--------|------------|-----------|
| TASK-013 | Implement languages.py: language detection and framework rule table | tc-backend-engineer | Pending | M | TASK-002, TASK-004, TASK-011, TASK-012 | [tasks/TASK-013.md](tasks/TASK-013.md) |
| TASK-014 | Implement testing.py analyser | tc-backend-engineer | Pending | S | TASK-002, TASK-004, TASK-007 | [tasks/TASK-014.md](tasks/TASK-014.md) |

### Wave 5 — Schema drift test and performance test

| ID | Title | Assignee | Status | Effort | Depends On | Task File |
|----|-------|----------|--------|--------|------------|-----------|
| TASK-015 | Write schema drift test and top-level key pin test | tc-qa-test-engineer | Pending | S | TASK-003, TASK-007, TASK-013, TASK-014 | [tasks/TASK-015.md](tasks/TASK-015.md) |
| TASK-016 | Write 50k-file performance test (marked slow) | tc-qa-test-engineer | Pending | S | TASK-009, TASK-007 | [tasks/TASK-016.md](tasks/TASK-016.md) |

---

## Summary

**Total Estimated Effort**: L–XL (12–18 engineer-days across two specialties)

**Recommended delivery sequence**:
1. Wave 1 tasks can all run in parallel — they have no inter-dependencies and establish the data contract everything else builds on.
2. Wave 2 tasks run after Wave 1 merges. TASK-006 through TASK-008 can run in parallel with TASK-009 (test infra). TASK-007 depends on TASK-006, so launch TASK-006 first and TASK-007 immediately after it merges.
3. Wave 3 tasks (TASK-010 and TASK-011) can run in parallel after Wave 2 merges. TASK-012 must follow TASK-011 as it extends the same module.
4. Wave 4 tasks run after Wave 3 fully merges. TASK-013 and TASK-014 can run in parallel.
5. Wave 5 tests run after Wave 4 merges and validate the complete implementation.

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| `setup.py` static AST parsing misses dynamically constructed `install_requires` | Medium | Medium | Emit a warning and return empty deps rather than failing; cover in test with a dynamic `install_requires` fixture |
| `gitpython` behaviour diverges across git versions in CI | Medium | Low | Pin a minimum git version in CI; fall back to subprocess `git` where gitpython is unreliable; test both paths |
| `mypy --strict` breaks on `dataclasses.asdict()` with nested generics | Low | Medium | Test `to_dict()` + `json.dumps` round-trip in TASK-002 before other tasks depend on it |
| 50k-file walk exceeds CI memory/time limits | Low | High | Mark test `@pytest.mark.slow`; gate it on CI environment variable; set an explicit wall-clock timeout assertion |
| `.gitignore` pathspec edge cases (negation, double-star) causing over/under exclusion | Medium | Medium | Use `pathspec` library (not hand-rolled); include fixture repos with non-trivial gitignore patterns in TASK-009 |
