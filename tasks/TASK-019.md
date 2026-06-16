# TASK-019: Fix in-scope symlink double-counting in walk_repo

**Status**: Pending
**Wave**: 1 — Remediation
**Effort**: S — the cycle-detection inode set already exists for directories; extend the same dedup to file symlinks
**Base Branch**: feature/wave-1-foundation
**Dependencies**: TASK-017

## Description

The current directory-level inode dedup set (`visited_dir_inodes`) prevents cyclic directory traversal but has no equivalent for file symlinks. When a file symlink within the repo points to another regular file also within the repo, both the symlink path and the real file path pass the scope-escape check and are appended to `file_paths`. Their bytes and extension are counted twice, corrupting `file_tree` statistics.

The fix is to maintain a `visited_file_inodes: set[int]` set. When a file is encountered (symlink or not), resolve it and stat the resolved target. If the inode is already in the set, skip the path. Otherwise, add the inode and proceed.

For non-symlink files the inode is just `os.stat(path).st_ino`; the dedup still has value because hard links to the same inode should also be counted once.

Affected section: `spelunk/utils.py:149-190` (the file loop within `walk_repo`).

## Acceptance Criteria

- [ ] [eng] Given a repo where file `a.py` exists and a symlink `b.py -> a.py` also exists within the repo · When `walk_repo` runs · Then exactly one of `a.py` or `b.py` appears in `file_paths` (the target is not double-counted)
- [ ] [eng] Given a repo with no symlinks · When `walk_repo` runs · Then every regular file appears exactly once in `file_paths` (no regression from inode dedup)
- [ ] [eng] Given a repo with a hard link pair `a.py` and `b.py` pointing to the same inode · When `walk_repo` runs · Then exactly one path appears in `file_paths`
- [ ] [eng] Given a repo where a file symlink points outside the root · When `walk_repo` runs · Then that symlink is still excluded (scope-escape check is not bypassed by the inode dedup)

## Notes / Risks

- The choice of which path to keep (symlink or target) when deduplicating is arbitrary — choose the first one encountered (walk order). Document this choice in a comment.
- Hard link deduplication is a desirable side effect, not a primary goal. If it causes test friction, the inode dedup can be scoped to symlinks only — document the decision.
- Resolving this finding is not a hard blocker for the Wave 1 PR (severity Medium), but it is sequenced here so that TASK-019 (coverage tests) can pin all four scenarios together.
- Sequenced after TASK-017 (root consistency fix) because `path.resolve()` must be reliable.
