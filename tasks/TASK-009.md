# TASK-009: Establish conftest.py build_repo factory and test infrastructure

**Status**: Pending
**Wave**: 2
**Assignee**: tc-qa-test-engineer
**Effort**: M — factory design and git subprocess fixture have non-trivial setup; slow-test marker and CI gating add platform concerns
**Base Branch**: main
**Dependencies**: TASK-001, TASK-007

## Description

Implement the primary test fixture infrastructure in `tests/conftest.py`. This provides the `build_repo` factory that all subsequent test files use as their default fixture mechanism. Without this, later test tasks cannot write meaningful integration tests.

### Primary fixture: `build_repo`

```python
@pytest.fixture
def build_repo(tmp_path):
    def factory(spec: dict[str, str | bytes], *, git_init: bool = False) -> Path:
        ...
    return factory
```

The `factory` callable:
- Accepts a `spec` dict mapping relative path strings to file content (str or bytes).
- Materialises each file under `tmp_path` using `Path.write_text()` / `Path.write_bytes()`, creating parent directories as needed.
- If `git_init=True`, runs `git init` + `git add .` + `git commit -m "init"` via `subprocess.run` (not via gitpython — this avoids gitpython test-environment coupling). Configure `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL` env vars to prevent CI failures on machines with no git config.
- Returns the `Path` to the root of the built repo (i.e. `tmp_path`).
- Is automatically cleaned up by pytest's `tmp_path` fixture at test end.

Example usage:
```python
def test_file_tree(build_repo):
    root = build_repo({"src/main.py": "print('hello')", ".gitignore": "*.pyc"})
    result = scan(str(root))
    assert result.file_tree.total_files == 2
```

### Symlink cycle fixture helper

Provide a helper (either a separate fixture or a utility function) for creating symlink cycles at test time:

```python
@pytest.fixture
def build_repo_with_symlink_cycle(build_repo, tmp_path):
    root = build_repo({"a.py": "x = 1", "b.py": "y = 2"})
    cycle_dir = root / "cycle"
    cycle_dir.mkdir()
    os.symlink(cycle_dir, cycle_dir / "self_link")
    return root
```

Do NOT commit symlinks to the repository — create them at test time.

### Symlink scope escape fixture helper

```python
@pytest.fixture
def build_repo_with_external_symlink(build_repo, tmp_path):
    root = build_repo({"a.py": "x = 1"})
    external_dir = tmp_path / "external"
    external_dir.mkdir()
    (external_dir / "secret.txt").write_text("sensitive")
    os.symlink(external_dir, root / "escaped_link")
    return root, external_dir
```

### `tests/fixtures/` directory

Create `tests/fixtures/` for static content. Initially populate with:
- `tests/fixtures/sample_gitignore` — a `.gitignore` with a few realistic rules (e.g. `*.pyc`, `node_modules/`, `__pycache__/`, `.env`)

Do NOT commit 50k files, nested `.git` directories, or symlinks.

### Slow test marker

Register `@pytest.mark.slow` in `pyproject.toml` (already done in TASK-001). In `conftest.py`, add a `--run-slow` CLI option that enables slow tests:

```python
def pytest_addoption(parser):
    parser.addoption("--run-slow", action="store_true", default=False)

def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-slow"):
        skip_slow = pytest.mark.skip(reason="Use --run-slow to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
```

### Smoke test

Write one smoke integration test in `tests/test_smoke.py` that:
1. Uses `build_repo` to create a minimal repo with 3 files.
2. Calls `scan(str(root))`.
3. Asserts `result.meta.errors == []` and `result.file_tree.total_files == 3` and `json.dumps(result.to_dict())` succeeds.

This test must pass with only the `file_tree` analyser wired in (TASK-007 stubs other fields).

## Acceptance Criteria

- [ ] [qa] Given the `build_repo` factory is called with a path-to-content spec · When the factory returns · Then all specified files exist under `tmp_path` with the correct content and are removed automatically after the test
- [ ] [qa] Given `build_repo(spec, git_init=True)` is called · When the factory returns · Then a `.git` directory exists and `git log` shows one commit
- [ ] [qa] Given a symlink cycle created via `build_repo_with_symlink_cycle` · When `scan()` runs · Then the scan completes without hanging and the cycle link is not in `meta.errors[]`
- [ ] [qa] Given an external symlink created via `build_repo_with_external_symlink` · When `scan()` runs · Then no file from `external_dir` appears in any output section
- [ ] [qa] Given a test marked `@pytest.mark.slow` · When `pytest` runs without `--run-slow` · Then it is skipped
- [ ] [qa] Given `pytest` is run · When the smoke test in `tests/test_smoke.py` runs · Then it passes with `result.meta.errors == []` and correct `total_files` count

## Notes / Risks

- Git subprocess in `git_init=True` path: some CI environments do not have git configured with a user identity. Always pass the env vars `GIT_AUTHOR_NAME="Test"`, `GIT_AUTHOR_EMAIL="test@test.com"` etc. in the `subprocess.run` call, or set them via `git config --local` after `git init`.
- Do NOT commit a `.git` directory inside the `tests/fixtures/` tree — nested git repos cause confusing behaviour with the outer repo.
- The `tmp_path` fixture is function-scoped by default. `build_repo` inherits this scope. If a test needs session-scoped repos (e.g. the performance test), it should build its own fixture with `scope="session"` — do not change the default scope of `build_repo`.
- `os.symlink` on Windows requires either Developer Mode or elevated privileges. CI should be Linux/macOS. Note this constraint in a comment.
