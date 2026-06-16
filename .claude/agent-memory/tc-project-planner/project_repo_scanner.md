---
name: project-repo-scanner
description: Core facts about the repo-scanner greenfield project — stack, architecture decisions, plan structure, and key constraints
metadata:
  type: project
---

repo-scanner is a greenfield Python 3.10+ CLI/library that performs static analysis on local repos and emits a versioned JSON document. Initial build (BRIEF-001) covers the full module scaffold, all five analysers, all seven ecosystem dependency parsers, and the complete test suite.

**Why:** Developers and automated pipelines need a machine-readable snapshot of a codebase without executing it.

**How to apply:** All implementation is tc-backend-engineer or tc-platform-engineer (no frontend scope). `scan()` public API must never raise — errors surface via `meta.errors[]`. All architect decisions below are locked constraints, not suggestions.

## Key architect decisions (F1–F10)

- **F1**: Analyser interface is `typing.Protocol` in `interfaces.py` — NOT duck-typing, NOT ABC.
- **F2**: Two-layer error contract: analyser collects expected errors in `AnalyserOutput.errors`; orchestrator wraps each analyser call in try/except as a backstop.
- **F3**: Framework detection via bounded in-source rule table `(ecosystem, dep_name) → label`. 14 frameworks. No config-file matrix. No extension-based inference.
- **F4**: Schema drift guard is a CI test, NOT runtime validation. `jsonschema` is dev-only dep.
- **F5**: `to_dict()` = `dataclasses.asdict()`. `from_dict()` explicitly deferred — do NOT create a task for it.
- **F6**: `tomli` is a conditional runtime dep via PEP 508 marker `; python_version < "3.11"`. Both the marker in `pyproject.toml` AND a try/import guard in code are required.
- **F7**: Symlink containment: resolve symlink → check `is_relative_to(root)`. This is IN ADDITION to inode-based cycle detection.
- **F8**: `setup.py` parsing via AST only — NEVER import/exec/eval the target file. Security-critical.
- **F9**: Primary fixture strategy is `build_repo` factory on `tmp_path`. No committed symlinks or nested `.git`. 50k-file test generated at runtime, marked `@pytest.mark.slow`.
- **F10**: Analyser execution order: `file_tree` → `dependencies` → `languages`/`testing`. `languages` consumes dependency output so must run after `dependencies`.

## Plan structure (TASK-001 through TASK-016)

- **Wave 1** (parallel): TASK-001 pyproject.toml, TASK-002 models.py, TASK-003 schema.py, TASK-004 interfaces.py, TASK-005 utils.py
- **Wave 2** (after Wave 1): TASK-006 file_tree.py, TASK-007 scanner.py + __init__.py, TASK-008 __main__.py, TASK-009 conftest.py (qa)
- **Wave 3** (after Wave 2): TASK-010 git_meta.py, TASK-011 dependencies.py Python/Node, TASK-012 dependencies.py Go/Rust/Ruby/Java/PHP
- **Wave 4** (after Wave 3): TASK-013 languages.py, TASK-014 testing.py
- **Wave 5** (after Wave 4): TASK-015 schema drift test, TASK-016 performance test

## Assignee split

- tc-platform-engineer: TASK-001 only
- tc-qa-test-engineer: TASK-009, TASK-015, TASK-016
- tc-backend-engineer: all remaining tasks

## Key constraints

- No `from_dict()` task — architect-deferred.
- `ScanInputs` will need a `dependencies` field added (in TASK-013) so `languages.py` can consume dependency output without re-parsing.
- `dependencies` analyser is wired into orchestrator at end of TASK-012 (not TASK-011), since TASK-012 completes the module.
- `jsonschema` goes in dev optional-dependencies only, not runtime.
