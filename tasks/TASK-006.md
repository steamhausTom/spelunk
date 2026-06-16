# TASK-006: Implement file_tree.py analyser

**Status**: Pending
**Wave**: 2
**Assignee**: tc-backend-engineer
**Effort**: M — notable file category logic and extension aggregation have non-trivial mapping tables
**Base Branch**: main
**Dependencies**: TASK-002, TASK-004, TASK-005

## Description

Implement `spelunk/analysers/file_tree.py` — the first concrete analyser. It consumes the pre-walked `ScanInputs.file_paths` list from `utils.py` and produces a `FileTreeInfo` payload.

This analyser does not re-walk the filesystem. It iterates `ctx.file_paths` and computes statistics.

### Module structure

```python
# spelunk/analysers/file_tree.py

from pathlib import Path
from spelunk.interfaces import Analyser, AnalyserOutput, ScanInputs
from spelunk.models import FileTreeInfo, ExtensionStats, NotableFiles, ScanError
from spelunk.utils import is_binary, LARGE_FILE_THRESHOLD_BYTES

name = "analysers.file_tree"

def __call__(root: Path, ctx: ScanInputs) -> AnalyserOutput:
    ...
```

Because analysers are plain modules with `name` and `__call__`, not class instances, `scanner.py` will import the module and call `file_tree(root, ctx)` directly. The `name` attribute is at module level; the `Analyser` Protocol is satisfied structurally.

Alternatively, define a module-level callable class. Either is acceptable as long as `mypy --strict` accepts it as an `Analyser`.

### Computation

For each path in `ctx.file_paths`:

**Extension stats**:
- Extract `path.suffix.lower()` (e.g. `.py`, `.js`). If no suffix, use `"(no extension)"`.
- Accumulate `file_count` and `byte_total` per extension using a `dict[str, ExtensionStats]`.
- Binary files (checked via `is_binary(path)`) and large files (`path.stat().st_size > LARGE_FILE_THRESHOLD_BYTES`) still contribute to extension stats — their content is just not read.

**Totals**:
- `total_files`: count of all paths in `ctx.file_paths`.
- `total_bytes`: sum of `path.stat().st_size` for all paths. Catch `OSError` per file; add to `errors`.
- `max_depth`: maximum number of path components relative to `root`. Compute as `len(path.relative_to(root).parts) - 1` (subtract 1 since the filename itself is not a depth level, only the directory nesting).

**Notable files** — categorise paths by matching against the following rules (case-insensitive filename match unless noted):

| Category | Match patterns |
|----------|---------------|
| `entrypoints` | `main.py`, `index.js`, `index.ts`, `app.py`, `app.js`, `app.ts`, `server.py`, `server.js`, `server.ts`, `manage.py` |
| `config_files` | `.env`, `.env.example`, `docker-compose.yml`, `docker-compose.yaml`, `Makefile`, `makefile`, `.editorconfig`, `.prettierrc`, `.eslintrc`, `.eslintrc.js`, `.eslintrc.json`, `babel.config.js`, `webpack.config.js` |
| `ci_configs` | Paths containing `.github/workflows/` (match by relative path prefix), `.gitlab-ci.yml`, `Jenkinsfile`, `.circleci/config.yml`, `azure-pipelines.yml`, `.travis.yml` |
| `docker` | `Dockerfile`, any file matching `Dockerfile.*` or `docker-compose*.yml` / `docker-compose*.yaml` |
| `iac` | Files with extension `.tf` (Terraform), filenames `Pulumi.yaml`, `Pulumi.yml`, `cdk.json`, `cloudformation.yml`, `cloudformation.yaml`, or containing `/cloudformation/` in their relative path |

A single file may appear in multiple categories (e.g. `docker-compose.yml` is both `config_files` and `docker`). Store the full path relative to `root` as a string in each list.

### Error handling

Wrap the entire body in try/except. Catch `OSError` per file when calling `path.stat()`. Add per-file errors to a local `errors: list[ScanError]` list with `source = name`. Return these in `AnalyserOutput.errors`.

## Acceptance Criteria

- [ ] [eng] Given a repo with 5 `.py` files and 3 `.js` files · When the file_tree analyser runs · Then `file_tree.extensions` contains entries for `.py` with `file_count=5` and `.js` with `file_count=3`
- [ ] [eng] Given a repo containing `main.py` at the root · When the file_tree analyser runs · Then `file_tree.notable_files.entrypoints` contains the path for `main.py`
- [ ] [eng] Given a repo containing `.github/workflows/ci.yml` · When the file_tree analyser runs · Then `file_tree.notable_files.ci_configs` contains that path
- [ ] [eng] Given a repo containing a file larger than 10 MB · When the file_tree analyser runs · Then `file_tree.total_files` includes that file and its extension appears in `file_tree.extensions`
- [ ] [eng] Given a repo with files nested 4 directories deep · When the file_tree analyser runs · Then `file_tree.max_depth` equals 4
- [ ] [eng] Given `mypy --strict` runs against `file_tree.py` · When it completes · Then zero type errors are reported
- [ ] [qa] Given a repository with a `.gitignore` excluding `node_modules/` · When the scan completes · Then `node_modules/` files do not appear in `file_tree.extensions` or `file_tree.total_files`

## Notes / Risks

- The `is_binary()` call in the extension stats loop adds per-file I/O overhead. For a 50k-file repo, this is significant. Consider caching binary status in a `dict[Path, bool]` or passing it as part of `ScanInputs` in a later refactor. For v1, correctness over performance.
- `max_depth` counts directory levels below root, not path component count. A file at `root/a/b/c.py` has depth 2 (directories `a` and `b`). Implement as `len(path.relative_to(root).parts) - 1`.
- Notable file matching: the filename-only patterns (e.g. `main.py`) must match `path.name.lower()`. The path-prefix patterns (e.g. `.github/workflows/`) must match against `str(path.relative_to(root))`.
- `docker-compose.yml` should appear in both `config_files` and `docker`. The spec says "a single file may appear in multiple categories" — this is intentional and not a bug.
