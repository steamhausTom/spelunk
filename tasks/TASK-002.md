# TASK-002: Implement models.py data layer

**Status**: In Review
**Wave**: 1
**Assignee**: tc-backend-engineer
**Effort**: S — pure data definitions; no business logic; the shape is fully specified in the output schema
**Base Branch**: main
**Dependencies**: None

## Description

Implement `spelunk/models.py` — the canonical data layer for all output types. This module must contain only `dataclasses.dataclass` definitions and their `to_dict()` serialisation helper. No business logic, no imports from other `spelunk` modules (except potentially `__future__`).

### Models to implement

All dataclasses must use `from __future__ import annotations` for forward reference support. All fields must be type-annotated.

**`ScanError`**
```
source: str        # e.g. "analysers.git_meta"
message: str
```

**`ScanMeta`**
```
scanner_version: str
errors: list[ScanError]
warnings: list[str]
```

**`RepoInfo`**
```
name: str
description: str | None
version: str | None
license: str | None
root_path: str          # store as string, not Path
```

**`GitInfo`**
```
present: bool
remote_url: str | None
default_branch: str | None
last_commit: str | None   # ISO 8601 or short SHA
contributor_count: int | None
tags: list[str]
```

**`LanguageStats`**
```
name: str
file_count: int
byte_total: int
```

**`LanguageInfo`**
```
primary: str | None
languages: list[LanguageStats]
```

**`ExtensionStats`**
```
extension: str
file_count: int
byte_total: int
```

**`NotableFiles`**
```
entrypoints: list[str]
config_files: list[str]
ci_configs: list[str]
docker: list[str]
iac: list[str]
```

**`FileTreeInfo`**
```
total_files: int
total_bytes: int
max_depth: int
extensions: list[ExtensionStats]
notable_files: NotableFiles
```

**`Dependency`**
```
name: str
version: str | None
ecosystem: str
dev: bool
```

**`ManifestInfo`**
```
path: str
ecosystem: str
```

**`DependenciesInfo`**
```
manifests: list[ManifestInfo]
runtime: list[Dependency]
dev: list[Dependency]
```

**`TestingInfo`**
```
frameworks: list[str]
test_directories: list[str]
test_file_count: int
```

**`RepoScanResult`** (top-level)
```
schema_version: str
scanned_at: str           # ISO 8601 string
repo: RepoInfo
git: GitInfo
languages: LanguageInfo
frameworks: list[str]
file_tree: FileTreeInfo
dependencies: DependenciesInfo
testing: TestingInfo
meta: ScanMeta
```

### `to_dict()` implementation

Every dataclass must have a `to_dict()` method implemented as:
```python
def to_dict(self) -> dict:
    return dataclasses.asdict(self)
```

`dataclasses.asdict()` recurses into nested dataclasses and lists automatically. Store `scanned_at` and all paths as `str` in the model so no custom JSON encoder is needed.

Verify that `json.dumps(result.to_dict())` succeeds with no custom encoder — this is the serialisation contract.

Do NOT implement `from_dict()` — it is explicitly out of scope per architect decision (F5).

## Acceptance Criteria

- [x] [eng] Given a fully populated `RepoScanResult` · When `to_dict()` is called · Then `json.dumps(result.to_dict())` succeeds with no custom encoder and no `TypeError`
- [x] [eng] Given `models.py` · When imported · Then it imports only from the Python standard library (no `spelunk` sub-imports)
- [x] [eng] Given `models.py` · When inspected · Then it contains no `from_dict()` method and no business logic (no conditionals, no data transformations)
- [x] [eng] Given a `ScanError` instance · When `to_dict()` is called · Then the result contains `source` and `message` keys with string values
- [x] [eng] Given a `RepoScanResult` with an empty `GitInfo` (`present=False`, all other fields `None` or `[]`) · When `to_dict()` is called · Then the `git` key is present and its `present` value is `False`
- [x] [eng] Given `mypy --strict` runs against `models.py` · When it completes · Then zero type errors are reported

## Notes / Risks

- `dataclasses.asdict()` does not handle `Path` objects — store all paths as `str` to avoid a `TypeError` at serialisation time. This is an architect-mandated decision (F5).
- `list[ScanError]` inside `ScanMeta` will be recursed by `dataclasses.asdict()` correctly since `ScanError` is itself a dataclass.
- Under `mypy --strict`, `list[str]` default fields must use `field(default_factory=list)`, not `= []`, to avoid the mutable default error.
- `LanguageInfo.primary` is `str | None` because a completely empty repo has no detectable primary language.
