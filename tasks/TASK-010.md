# TASK-010: Implement git_meta.py analyser

**Status**: Pending
**Wave**: 3
**Assignee**: tc-backend-engineer
**Effort**: M — gitpython API plus subprocess fallback, multiple git data points, and absent-.git handling
**Base Branch**: main
**Dependencies**: TASK-002, TASK-004, TASK-007

## Description

Implement `spelunk/analysers/git_meta.py` — the analyser that extracts git metadata from the scanned repository. It must handle repos with and without a `.git` directory gracefully.

At the end of this task, uncomment `git_meta` in `scanner.py`'s `_ANALYSERS` list and wire its `payload` into `RepoScanResult.git`.

### Module-level attributes

```python
name = "analysers.git_meta"
```

### `__call__(root: Path, ctx: ScanInputs) -> AnalyserOutput`

#### Step 1 — detect git presence

Check `(root / ".git").exists()`. If not present, return immediately:
```python
return AnalyserOutput(
    payload=GitInfo(present=False, remote_url=None, default_branch=None,
                    last_commit=None, contributor_count=None, tags=[]),
    errors=[], warnings=[], source=name
)
```

#### Step 2 — extract git data (gitpython primary, subprocess fallback)

Use `gitpython` as the primary extraction method. Wrap in `try/except` — on any gitpython failure, fall back to subprocess `git` commands.

**Data to extract**:

| Field | gitpython | subprocess fallback |
|-------|-----------|---------------------|
| `remote_url` | `repo.remotes[0].url` if remotes exist | `git remote get-url origin` |
| `default_branch` | `repo.active_branch.name` | `git rev-parse --abbrev-ref HEAD` |
| `last_commit` | `repo.head.commit.committed_datetime.isoformat()` | `git log -1 --format=%cI` |
| `contributor_count` | `len(set(c.author.email for c in repo.iter_commits()))` | `git shortlog -s HEAD \| wc -l` |
| `tags` | `[t.name for t in repo.tags]` | `git tag --list` |

Notes:
- `contributor_count` via `repo.iter_commits()` can be slow on repos with thousands of commits. Limit to the last 500 commits for the initial implementation and document the limitation in a warning if the repo has more: `meta.warnings.append("contributor_count limited to last 500 commits")`.
- A detached HEAD has no `active_branch` — catch `TypeError` and return `None` for `default_branch`.
- If `repo.remotes` is empty, `remote_url` is `None`.
- `tags` list: tag names only, not full refs.

#### Step 3 — return AnalyserOutput

Return `AnalyserOutput(payload=GitInfo(...), errors=errors, warnings=warnings, source=name)`.

#### Error handling

Per the two-layer contract (F2):
- Expected failures (missing remote, detached HEAD, empty repo): handle inline, return `None` for the affected field.
- Unexpected failures (gitpython crash): caught by the orchestrator's backstop in `scanner.py`. The analyser may also catch unexpected gitpython exceptions internally and add them to `errors` with the repo path, then return a partial result.

### Wire into orchestrator

In `scanner.py`, after this task is merged:
1. Import `git_meta` from `spelunk.analysers.git_meta`.
2. Uncomment `git_meta` in `_ANALYSERS`.
3. Assign `output.payload` to `RepoScanResult.git` when the analyser name matches.

## Acceptance Criteria

- [ ] [eng] Given a directory with a `.git` directory · When the git_meta analyser runs · Then `git.present` is `True` and `git.default_branch` is a non-empty string
- [ ] [eng] Given a directory with no `.git` directory · When the git_meta analyser runs · Then the returned `GitInfo` has `present=False` and all other fields are `None` or `[]`
- [ ] [eng] Given a git repo with at least one remote named `origin` · When the git_meta analyser runs · Then `git.remote_url` is the origin URL
- [ ] [eng] Given a git repo with at least one tag · When the git_meta analyser runs · Then `git.tags` contains that tag name
- [ ] [eng] Given a git repo in detached HEAD state · When the git_meta analyser runs · Then `git.default_branch` is `None` and no exception propagates
- [ ] [eng] Given gitpython raises an unexpected exception · When the git_meta analyser runs · Then the analyser returns a partial result with the error recorded in `AnalyserOutput.errors`, not a raised exception
- [ ] [eng] Given `mypy --strict` runs against `git_meta.py` · When it completes · Then zero type errors are reported
- [ ] [qa] Given a repository with a `.git` directory · When the full scan completes · Then `git.present` is `true`, `git.remote_url` and `git.default_branch` are populated in the JSON output

## Notes / Risks

- gitpython's `iter_commits()` on a shallow clone (common in CI) may behave unexpectedly. Catch `git.exc.GitCommandError` and return what was collected.
- The subprocess fallback must use `subprocess.run([...], capture_output=True, text=True, cwd=root)` — never `shell=True` (security risk).
- `contributor_count` from subprocess `git shortlog -s HEAD | wc -l` requires a pipe — use two subprocess calls or `subprocess.PIPE` chaining rather than `shell=True`.
- On Windows, `git` may not be in PATH. Catch `FileNotFoundError` from subprocess and return a partial result with a warning.
- The 500-commit limit on `contributor_count` is a v1 constraint to avoid performance issues. Document it clearly.
