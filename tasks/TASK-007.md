# TASK-007: Implement scanner.py orchestrator and __init__.py public API

**Status**: In Review
**Wave**: 2
**Assignee**: tc-backend-engineer
**Effort**: M — orchestrator error envelope merging logic and public API contract require care; this is the integration seam
**Base Branch**: main
**Dependencies**: TASK-002, TASK-003, TASK-004, TASK-006

## Description

Implement `spelunk/scanner.py` (the orchestrator) and `spelunk/__init__.py` (the public API). Together these form the public `scan()` entry point that all consumers use.

At the end of this task, `from spelunk import scan; result = scan("/path/to/repo")` must work end-to-end — even with only the `file_tree` analyser wired in — and produce schema-conforming JSON.

### `scanner.py`

#### `scan_repo(root: Path) -> RepoScanResult`

This is the internal orchestrator. Steps:

1. **Resolve root**: `root = Path(root).resolve()`. Raise `ValueError` if it does not exist or is not a directory (this is one of the few places a raise is acceptable — the public `scan()` wrapper catches it).

2. **Walk filesystem**: call `utils.walk_repo(root)` to get `(file_paths, walk_errors, walk_warnings)`.

3. **Build `ScanInputs`**: `ctx = ScanInputs(root=root, file_paths=file_paths)`.

4. **Collect `RepoInfo`**: Derive `name` from `root.name`. Attempt to read `pyproject.toml`/`setup.cfg`/`setup.py` for `description`, `version`, `license`. If not found, set to `None`. Wrap in try/except; errors go to `meta.errors`.

5. **Run analysers in sequence**:
   - Start with the registered analyser list. In this task, only `file_tree` is wired in. The list will grow in TASK-010 through TASK-014.
   - For each analyser in the list, call `analyser(root, ctx)` inside a `try/except Exception as exc` block (the backstop — F2).
   - On success: merge `output.errors` and `output.warnings` into the top-level accumulators.
   - On unexpected exception: append `ScanError(source=analyser.name, message=str(exc))` to the error accumulator. Continue to the next analyser.

6. **Assemble stubs for not-yet-implemented analysers**: until TASK-010–014 are merged, populate `git`, `languages`, `frameworks`, `dependencies`, `testing` with safe empty/null defaults so the output is schema-conforming from day one.

7. **Build `ScanMeta`**: include `scanner_version` (read from `importlib.metadata.version("spelunk")` or hard-code `"0.1.0"` as a fallback), merge all collected errors and warnings (including walk errors/warnings and per-analyser errors/warnings).

8. **Return `RepoScanResult`** with `schema_version = SCHEMA_VERSION`, `scanned_at = datetime.now(timezone.utc).isoformat()`.

#### Analyser registration

Use a module-level list:
```python
_ANALYSERS: list[Analyser] = [
    file_tree,
    # git_meta,       # wired in TASK-010
    # dependencies,   # wired in TASK-011/012
    # languages,      # wired in TASK-013
    # testing,        # wired in TASK-014
]
```

Commented entries keep the intent clear and reduce merge conflicts when future tasks add analysers.

#### Two-layer error contract (F2)

Layer 1 (expected errors): each analyser collects per-item errors internally and returns them in `AnalyserOutput.errors`. The orchestrator merges these.

Layer 2 (backstop): the orchestrator wraps each `analyser(root, ctx)` call in `try/except Exception`. If the analyser itself crashes (unexpected), the orchestrator catches it, records `ScanError(source=analyser.name, message=str(exc))`, and continues. This ensures the scan always completes.

### `__init__.py`

```python
from spelunk.scanner import scan_repo
from spelunk.models import RepoScanResult
from pathlib import Path

def scan(path: str | Path) -> RepoScanResult:
    """
    Scan the repository at `path` and return a RepoScanResult.
    Never raises. All errors surface via result.meta.errors[].
    """
    try:
        return scan_repo(Path(path))
    except Exception as exc:
        # Final safety net — should not normally be reached
        from spelunk.models import ScanMeta, ScanError, RepoInfo, GitInfo, \
            LanguageInfo, FileTreeInfo, NotableFiles, DependenciesInfo, TestingInfo
        from spelunk.schema import SCHEMA_VERSION
        from datetime import datetime, timezone
        # ... return a minimal valid result with the error recorded
```

The outer `try/except` in `scan()` is the final safety net — `scan_repo` should not raise, but if it does, `scan()` must still return a valid `RepoScanResult`.

**Contract**: `scan()` NEVER raises an exception. This is the project's primary public API guarantee.

## Acceptance Criteria

- [x] [eng] Given a valid directory path · When `scan(path)` is called · Then a `RepoScanResult` is returned without raising an exception
- [x] [eng] Given a non-existent path · When `scan(path)` is called · Then a `RepoScanResult` is returned (not raised), with an error in `meta.errors[]` describing the invalid path
- [x] [eng] Given an analyser that raises an unexpected exception · When `scan_repo` runs · Then `meta.errors[]` contains `{source: analyser.name, message: str(exc)}` and all other analysers still execute
- [x] [eng] Given an analyser that returns errors in its `AnalyserOutput.errors` · When the scan completes · Then those errors appear in `meta.errors[]` with the correct `source`
- [x] [eng] Given a scan of any valid directory · When `result.to_dict()` is called · Then `json.dumps(result.to_dict())` succeeds and the output contains `schema_version: "1.0.0"` and a valid ISO 8601 `scanned_at`
- [x] [eng] Given `mypy --strict` runs against `scanner.py` and `__init__.py` · When it completes · Then zero type errors are reported
- [ ] [qa] Given `from spelunk import scan; result = scan("/some/valid/path")` · When executed in a Python REPL · Then `result` is a `RepoScanResult` instance and `result.meta.errors` is a list

## Notes / Risks

- The stub defaults for not-yet-implemented analysers (`git`, `languages`, `frameworks`, `dependencies`, `testing`) must be schema-conforming. Use model constructors with safe defaults: e.g. `GitInfo(present=False, remote_url=None, ...)`, `LanguageInfo(primary=None, languages=[])`, etc.
- `importlib.metadata.version("spelunk")` will fail if the package is not installed — use a try/except fallback to `"0.1.0"`.
- `datetime.now(timezone.utc).isoformat()` produces a timezone-aware ISO 8601 string. This is the correct form (not `datetime.utcnow()` which is deprecated in 3.12).
- The minimal `RepoScanResult` returned in the final safety net of `scan()` must still pass `json.dumps()` — instantiate all model fields with empty/null defaults, not `None` for list fields.
- Future tasks (TASK-010 through TASK-014) will uncomment entries in `_ANALYSERS` and pass the analyser's output into the correct `RepoScanResult` field. The orchestrator's merge logic should already be in place.
