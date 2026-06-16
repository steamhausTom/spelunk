# TASK-020: Add coverage tests for STR-F1 through STR-F4 utils scenarios

**Status**: Pending
**Wave**: 1 — Remediation
**Effort**: S — four targeted test scenarios; all use the existing tmp_path pattern; no new fixtures needed beyond symlink creation helpers
**Base Branch**: feature/wave-1-foundation
**Dependencies**: TASK-017, TASK-018, TASK-019

## Description

The existing `tests/test_utils.py` suite uses `pytest tmp_path` exclusively, which is always a fully resolved path on the real filesystem. This masked all four bugs found in review:

- STR-F1: root/resolved-root mismatch (relative path or symlinked-component invocation silently disables .gitignore)
- STR-F2: `.git/` not excluded (inline-fixed; needs a pinning test)
- STR-F3: nested `.gitignore` over-excludes files outside its subtree
- STR-F4: in-scope file symlink double-counts bytes/extension

Each scenario must be pinned by a dedicated test that was failing before the corresponding fix and passes after. This task is owned by `tc-qa-test-engineer` and is placed after TASK-017–019 have been implemented so the tests can be written as green confirming tests.

Additionally, the `collect_gitignore_spec` unit-level test for nested `.gitignore` merging (QA-F2) is included here: a root `.gitignore` plus a subdirectory `.gitignore` with different rules, verified both rule sets appear in the returned structure.

## Acceptance Criteria

- [ ] [qa] Given STR-F1 scenario: a repo invoked via a relative path · When `walk_repo` runs against a `.gitignore` with `node_modules/` · Then files under `node_modules/` are absent from `file_paths` (test was failing before TASK-017)
- [ ] [qa] Given STR-F2 scenario: a repo with a `.git/` directory containing files · When `walk_repo` runs · Then no path inside `.git/` appears in `file_paths`
- [ ] [qa] Given STR-F3 scenario: `subdir/.gitignore` contains `foo.txt` and `foo.txt` exists at the root · When `walk_repo` runs · Then root `foo.txt` is in `file_paths` and `subdir/foo.txt` is not
- [ ] [qa] Given STR-F4 scenario: symlink `b.py -> a.py` both within the repo · When `walk_repo` runs · Then `a.py` appears exactly once in `file_paths`
- [ ] [qa] Given a repo with a root `.gitignore` and a subdirectory `.gitignore` with different rules · When `walk_repo` runs · Then `.log` files in the subdirectory are excluded and `.log` files outside it are not

## Notes / Risks

- All five scenarios must create their fixture repos using `tmp_path`; the STR-F1 test must additionally call `os.chdir` or pass a `Path(".")` equivalent, or construct a symlinked path via `os.symlink` at the OS level.
- On macOS, `/tmp` resolves to `/private/tmp`. The symlinked-component test is naturally exercised there if the fixture is created under `/tmp` and the scan is invoked with the `/tmp/...` path.
- Symlink creation in tests requires `os.symlink`. Tests that create symlinks should be marked to skip gracefully on filesystems that do not support them (e.g. some CI environments), using `pytest.importorskip` or a `skipif` condition.
- QA-F3 (null byte beyond 8 KB window) is an adversarial test already added by the QA agent in the previous commit — do not duplicate it; reference it in a comment.
