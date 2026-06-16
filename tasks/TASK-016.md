# TASK-016: Write 50k-file performance test (marked slow)

**Status**: Pending
**Wave**: 5
**Assignee**: tc-qa-test-engineer
**Effort**: S — test harness generation is simple; the slow-marker CI gating setup is the primary concern
**Base Branch**: main
**Dependencies**: TASK-009, TASK-007

## Description

Implement the performance boundary test for the 50,000-file walk described in the brief acceptance criteria. This test validates that the scanner completes without hanging and does not unboundedly accumulate file content in memory.

The test is marked `@pytest.mark.slow` and is skipped unless `--run-slow` is passed. It should be enabled in CI via a dedicated job or workflow step.

### Test file: `tests/test_performance.py`

#### Helper: generate a large repo

```python
def _build_large_repo(root: Path, n_files: int = 50_000) -> None:
    """Create n_files small Python files spread across subdirectories."""
    files_per_dir = 500
    n_dirs = n_files // files_per_dir
    for i in range(n_dirs):
        d = root / f"pkg_{i:04d}"
        d.mkdir()
        for j in range(files_per_dir):
            (d / f"module_{j:03d}.py").write_text(f"# file {i}-{j}\nx = {i * j}\n")
```

Each file is ~30 bytes. Total size ≈ 1.5 MB. This is well within memory bounds for file content. The test is about walk overhead, not content size.

#### Test: `test_50k_file_walk_completes`

```python
import time
import resource  # Unix only

@pytest.mark.slow
def test_50k_file_walk_completes(tmp_path):
    _build_large_repo(tmp_path, n_files=50_000)

    start = time.monotonic()
    result = scan(str(tmp_path))
    elapsed = time.monotonic() - start

    # Correctness
    assert result.file_tree.total_files == 50_000
    assert result.meta.errors == []

    # Performance bounds
    assert elapsed < 120.0, f"Walk took {elapsed:.1f}s — exceeded 120s bound"
```

#### Memory check (optional, Unix only)

```python
    # Peak RSS should not grow unboundedly — rough sanity check
    peak_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # On Linux ru_maxrss is in KB; on macOS it's in bytes
    import sys
    peak_mb = peak_kb / 1024 if sys.platform != "darwin" else peak_kb / (1024 * 1024)
    assert peak_mb < 500, f"Peak RSS {peak_mb:.0f} MB exceeded 500 MB bound"
```

The memory bound is a sanity check, not a hard performance SLA. Adjust based on observed CI baseline. The key invariant is "no unbounded in-memory accumulation of file content" (from the spec) — this test catches regressions like loading all file contents into a list.

### CI integration guidance

In the `pyproject.toml` or CI workflow, define a separate step:

```yaml
- name: Run slow tests
  run: pytest --run-slow tests/test_performance.py -v
  if: github.event_name == 'push' && github.ref == 'refs/heads/main'
```

Or always run on CI regardless of branch by using a CI environment variable:

```bash
pytest --run-slow tests/test_performance.py
```

Document the chosen CI gating strategy in a comment at the top of `test_performance.py`.

## Acceptance Criteria

- [ ] [qa] Given `pytest` runs without `--run-slow` · When test collection completes · Then `test_50k_file_walk_completes` is marked as skipped, not failed
- [ ] [qa] Given `pytest --run-slow` runs and 50,000 small files are present under `tmp_path` · When `scan()` completes · Then `result.file_tree.total_files == 50_000` and `result.meta.errors == []`
- [ ] [qa] Given the 50k-file scan runs · When timing is measured · Then wall-clock time is under 120 seconds
- [ ] [qa] Given the 50k-file scan runs on Linux/macOS · When peak RSS is measured · Then it is below 500 MB

## Notes / Risks

- File generation: 50,000 files in one flat directory would be slow on HFS+ and ext4 due to directory entry overhead. Spread across 100 subdirectories of 500 files each to avoid filesystem bottlenecks. The helper uses 500 files/dir as above.
- The 120-second wall-clock bound is generous for CI. The intent is to catch infinite loops and unbounded growth, not to enforce a tight SLA. Adjust downward once baseline is established on the CI runner.
- `resource.getrusage` is Unix-only. On Windows, wrap in `if sys.platform != "win32"` and skip the memory assertion.
- The `tmp_path` fixture is function-scoped, so the 50k files are created and torn down per test run. This adds ~5–10 seconds to the test runtime for file creation/deletion. This is acceptable given the test is marked slow and runs separately.
- Do NOT check the generated 50k files into the repository. They are created at test time by `_build_large_repo`.
- This test depends only on TASK-007 (the scanner pipeline) and TASK-009 (the slow-marker infra). It does not require all analysers to be wired in — the scan with stub analysers is sufficient to test walk performance.
