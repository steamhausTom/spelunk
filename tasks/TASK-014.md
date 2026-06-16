# TASK-014: Implement testing.py analyser

**Status**: Pending
**Wave**: 4
**Assignee**: tc-backend-engineer
**Effort**: S — pattern matching against file paths and manifest data; no complex parsing
**Base Branch**: main
**Dependencies**: TASK-002, TASK-004, TASK-007

## Description

Implement `spelunk/analysers/testing.py` — the analyser that detects test frameworks, test directories, and test file counts.

This analyser consumes `ctx.file_paths` (file paths from `ScanInputs`) and, optionally, the `DependenciesInfo` payload (if available in `ctx.dependencies`). It does not re-read file content.

At the end of this task, wire `testing` into `scanner.py`'s `_ANALYSERS` list and assign its payload to `RepoScanResult.testing`.

### Module-level attributes

```python
name = "analysers.testing"
```

### `__call__(root: Path, ctx: ScanInputs) -> AnalyserOutput`

#### Test file detection

A file is a test file if any of the following match:
- Its `path.name` starts with `test_` (Python convention: `test_*.py`)
- Its `path.name` ends with `_test.py` (Go/Rust convention)
- Its `path.name` ends with `.test.js`, `.test.ts`, `.test.jsx`, `.test.tsx` (JavaScript/TypeScript)
- Its `path.name` ends with `.spec.js`, `.spec.ts`, `.spec.jsx`, `.spec.tsx`
- Its `path.name` is `*Test.java`, `*Tests.java`, `*Spec.rb` (Java/Ruby)

Count matching files → `test_file_count`.

#### Test directory detection

Collect unique immediate parent directories of test files, expressed as paths relative to `root`. Additionally, include well-known test directory names if they exist in `ctx.file_paths`:
- `tests/`, `test/`, `__tests__/`, `spec/`

Deduplicate. Sort. Store as strings in `test_directories`.

#### Test framework detection

Detection strategy: look for framework-specific signals in two places.

**From `ctx.dependencies`** (if available — check `ctx.dependencies is not None`):

| Framework | Signal |
|-----------|--------|
| `pytest` | dep name `pytest`, ecosystem `python` |
| `unittest` | any test file matching `test_*.py` (stdlib — no manifest signal) |
| `Jest` | dep name `jest`, ecosystem `node` |
| `Vitest` | dep name `vitest`, ecosystem `node` |
| `Mocha` | dep name `mocha`, ecosystem `node` |
| `Jasmine` | dep name `jasmine`, ecosystem `node` |
| `RSpec` | dep name `rspec`, ecosystem `ruby` |
| `Minitest` | dep name `minitest`, ecosystem `ruby` |
| `JUnit` | dep groupId:artifactId contains `junit`, ecosystem `java` |
| `TestNG` | dep groupId:artifactId contains `testng`, ecosystem `java` |
| `PHPUnit` | dep name `phpunit/phpunit`, ecosystem `php` |
| `Go testing` | presence of `*_test.go` files (stdlib — no manifest signal) |
| `Rust test` | presence of `#[test]` — too expensive to parse in v1; use `*_test.rs` files as a proxy |

**From file patterns** (always checked, regardless of dependency data):
- `unittest`: any `test_*.py` file → include `"unittest"` as a detected framework (it is the default Python test runner even without pytest).
- `Go testing`: any file ending `_test.go`.

Use a `set[str]` for framework labels and return a `sorted(list(...))`.

#### Return

Return `AnalyserOutput(payload=TestingInfo(frameworks=[...], test_directories=[...], test_file_count=N), errors=[], warnings=[], source=name)`.

### Wire into orchestrator

In `scanner.py`:
1. Import `testing` from `spelunk.analysers.testing`.
2. Uncomment `testing` in `_ANALYSERS` (place after `languages` — ensures `ctx.dependencies` is populated).
3. Assign `output.payload` to `RepoScanResult.testing`.

## Acceptance Criteria

- [ ] [eng] Given a repo with 5 files named `test_*.py` in a `tests/` directory · When the testing analyser runs · Then `testing.test_file_count` equals 5 and `testing.test_directories` includes `"tests"`
- [ ] [eng] Given `ctx.dependencies` containing a dep `{name: "pytest", ecosystem: "python"}` · When the testing analyser runs · Then `"pytest"` appears in `testing.frameworks`
- [ ] [eng] Given `ctx.dependencies` containing a dep `{name: "jest", ecosystem: "node"}` · When the testing analyser runs · Then `"Jest"` appears in `testing.frameworks`
- [ ] [eng] Given a repo with `*_test.go` files and no dependency manifest · When the testing analyser runs · Then `"Go testing"` appears in `testing.frameworks`
- [ ] [eng] Given a repo with no test files and no test-related dependencies · When the testing analyser runs · Then `testing.test_file_count` equals 0 and `testing.frameworks` equals `[]`
- [ ] [eng] Given `ctx.dependencies` is `None` (not yet computed) · When the testing analyser runs · Then it still completes without error, using only file-pattern detection
- [ ] [eng] Given `mypy --strict` runs against `testing.py` · When it completes · Then zero type errors are reported
- [ ] [qa] Given a repository with a `tests/` directory containing `test_*.py` files · When the full scan completes · Then `testing.test_file_count` is greater than zero and `testing.test_directories` includes `"tests"` in the JSON output

## Notes / Risks

- `unittest` is included as a detected framework whenever Python test files are found, regardless of whether `pytest` is also detected. Both can be true simultaneously (pytest runs unittest tests).
- `ctx.dependencies` is `None` until the `dependencies` analyser has run. Since `testing` is wired after `languages` (which is after `dependencies`), `ctx.dependencies` should always be populated. But defend against `None` anyway.
- The `*_test.go` file detection depends purely on the filename suffix. Go's testing package is stdlib, so there is no manifest signal — file-based detection is the only option.
- Java test detection from `groupId:artifactId` string: `junit` appears in many forms (`junit:junit`, `org.junit.jupiter:junit-jupiter-api`, etc.). Use `"junit" in dep.name.lower()` as the detection heuristic.
- Do NOT scan file content for `import pytest` or `import unittest` — content scanning is out of scope for the testing analyser. File name pattern and dependency manifest signals are sufficient for v1.
