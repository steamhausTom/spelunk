# BRIEF-001: Initial Build — spelunk CLI and Library

**Source**: User request (greenfield specification)
**Status**: Draft
**Architect review required**: Yes — greenfield multi-module project with a versioned JSON output contract, a defined analyser interface that all future extensions will depend on, and schema versioning strategy decisions that will constrain downstream consumers if changed incorrectly.

## Problem statement

Developers and automated pipelines currently have no standardised, machine-readable way to extract a structured snapshot of a local codebase without cloning, executing, or building it. `spelunk` fills that gap by performing static analysis and emitting a single, versioned JSON document covering file layout, language detection, dependency manifests, git metadata, and test infrastructure. The initial build establishes the full module structure, public API contract, output schema, and all seven ecosystem dependency parsers in one deliverable.

## User story

As a developer or automated pipeline consumer, I want to run `python -m spelunk <path>` (or call `scan(path)` in Python) and receive a single structured JSON document describing that repository's metadata, so that I can feed that snapshot into portfolio analysis tools or agent workflows without executing the target codebase.

## Acceptance criteria (user-facing)

### CLI — happy path
- [ ] Given a valid local repository path · When the user runs `python -m spelunk <path>` · Then a JSON document conforming to `schema_version: "1.0.0"` is printed to stdout and the process exits 0
- [ ] Given a valid local repository path · When the user runs `python -m spelunk <path> --output result.json` · Then the JSON document is written to `result.json`, nothing is printed to stdout, and the process exits 0

### Library API — happy path
- [ ] Given a valid path string · When `from spelunk import scan; result = scan("/path/to/repo")` is called · Then a `RepoScanResult` object is returned without raising an exception

### Output schema correctness
- [ ] Given a scanned repository · When the JSON output is validated against the published JSON schema in `schema.py` · Then validation passes with zero errors
- [ ] Given a scanned repository · When the JSON output is inspected · Then `scanned_at` is a valid ISO 8601 timestamp and `schema_version` equals `"1.0.0"`

### File tree analyser
- [ ] Given a repository with mixed file types · When the scan completes · Then `file_tree.total_files` matches the actual count of non-ignored, non-symlink-cycle files
- [ ] Given a repository containing files larger than 10 MB · When the scan completes · Then those files appear in `meta.warnings[]` and their content is not reflected in language or dependency output
- [ ] Given a repository containing binary files (detected via null-byte in first 8 KB) · When the scan completes · Then those files are counted and their extension recorded but their content is not analysed

### .gitignore filtering
- [ ] Given a repository with a `.gitignore` that excludes `node_modules/` · When the scan completes · Then no files inside `node_modules/` appear in `file_tree`, `languages`, or `dependencies` output

### Git metadata analyser
- [ ] Given a repository with a `.git` directory · When the scan completes · Then `git.present` is `true` and `git.remote_url`, `git.default_branch`, `git.last_commit`, `git.contributor_count`, and `git.tags` are populated
- [ ] Given a directory with no `.git` directory · When the scan completes · Then `git.present` is `false` and all other `git` fields are `null`

### Language detection
- [ ] Given a mixed-language repository · When the scan completes · Then `languages` lists all detected languages ranked by file count and `languages.primary` equals the language with the highest file count

### Framework detection
- [ ] Given a repository whose `pyproject.toml` or `requirements.txt` lists FastAPI as a dependency · When the scan completes · Then `"FastAPI"` appears in the `frameworks` array
- [ ] Given a repository whose `package.json` lists React as a dependency · When the scan completes · Then `"React"` appears in the `frameworks` array

### Dependency manifest parsing
- [ ] Given a Python repository with a `requirements.txt` · When the scan completes · Then `dependencies.runtime` lists each package with its name, version constraint, and ecosystem `"python"`
- [ ] Given a Node repository with a `package.json` · When the scan completes · Then runtime and dev dependencies are separated correctly using the `dependencies` vs `devDependencies` keys
- [ ] Given a monorepo with multiple `package.json` files · When the scan completes · Then all dependencies are merged into a single list and `meta.warnings[]` names each manifest path
- [ ] Given each supported ecosystem (Python, Node, Go, Rust, Ruby, Java/Kotlin, PHP) · When the corresponding manifest file is present · Then at least one dependency entry appears in the output with correct `name`, `version`, and `ecosystem` fields

### Testing analyser
- [ ] Given a repository containing a `tests/` directory with `test_*.py` files · When the scan completes · Then `testing.test_file_count` is greater than zero and `testing.test_directories` includes the `tests/` path

### Symlink handling
- [ ] Given a repository containing a symlink cycle · When the scan completes · Then the walk terminates, the cyclic link is silently skipped, and no error is added to `meta.errors[]`

### Non-fatal error handling
- [ ] Given a repository where one file is not readable due to permissions · When the scan completes · Then the unreadable file's path appears in `meta.errors[]`, the scan completes, and all other files are processed normally
- [ ] Given a repository where the git metadata analyser encounters an unexpected error · When the scan completes · Then `meta.errors[]` contains an entry with `source: "analysers.git_meta"` and a `message` field, and the rest of the output is intact

### Performance
- [ ] Given a repository containing approximately 50,000 files · When the scan runs · Then the walk completes without hanging and peak memory usage remains bounded (no unbounded in-memory accumulation of file content)

## Scope

### In scope
- Full module scaffold: `spelunk/__init__.py`, `__main__.py`, `scanner.py`, `models.py`, `utils.py`, `schema.py`
- All five analysers: `file_tree.py`, `git_meta.py`, `languages.py`, `dependencies.py`, `testing.py`
- Dependency manifest parsers for all seven ecosystems: Python (`requirements.txt`, `pyproject.toml`, `Pipfile`, `setup.py`), Node (`package.json`, `package-lock.json`, `yarn.lock`), Go (`go.mod`), Rust (`Cargo.toml`), Ruby (`Gemfile`), Java/Kotlin (`pom.xml`, `build.gradle`), PHP (`composer.json`)
- `pyproject.toml` packaging with `[project.optional-dependencies]` for dev extras (`pytest`, `pytest-cov`, `mypy`)
- Output JSON schema definition at `schema_version: "1.0.0"` in `schema.py`
- All edge-case handling defined in the specification: `.gitignore` enforcement, symlink cycle detection, binary file detection, large file threshold, monorepo manifest merging, permission error handling
- `pytest` test suite under `tests/` with at least one test per public function in each module
- `mypy` strict mode configured for `spelunk/` (tests/ excluded from strict checking)

### Out of scope
- Web UI, browser-based report viewer, or any non-CLI/library interface
- Remote repository scanning (fetching/cloning from URLs)
- Incremental or cached scans (re-scanning only changed files)
- IDE plugins or editor integrations
- Any schema version beyond `1.0.0` — version bumps are a separate change
- Publishing to PyPI (CI/CD publishing pipeline is a separate deliverable)
- Framework detection beyond what is derivable from manifest dependency lists and file extension distribution

## Constraints & context

- **Python version**: 3.10+ required; `match` statements and `X | Y` union syntax are in use. `tomllib` is stdlib from 3.11; `tomli >= 2.0` must be a conditional dependency for 3.10 compatibility.
- **Package management**: `pyproject.toml` only (PEP 517/518). No `setup.cfg` or legacy `setup.py` for the scanner package itself.
- **Dependency philosophy**: stdlib preferred; external dependencies are `click >= 8.0`, `pathspec >= 0.12`, `gitpython >= 3.1`, and (conditionally) `tomli >= 2.0`. No new runtime dependencies without justification.
- **No global state**: analysers must be pure functions or stateless classes to support safe concurrent use.
- **Public API contract**: `scan()` must never raise. All errors surface via `meta.errors[]`.
- **Schema stability**: `schema_version` in `schema.py` is the contract version for downstream consumers. Any breaking change to output shape requires a version bump — this decision has architectural implications for how the schema constant is guarded and tested.
- **Analyser interface**: the pattern by which `scanner.py` calls each analyser will determine how easily new analysers can be added in future. The architect should define the interface contract (function signature, return type, error contract) before implementation begins.

## Open questions

- [ ] Should the analyser interface be formalised as a `Protocol` (or abstract base class) in `models.py` or a separate `interfaces.py`, or is a duck-typed convention sufficient? This affects how future analysers are added and how `mypy --strict` validates them. (Resolve before implementation of `scanner.py`.)
- [ ] For framework detection, the spec describes detection from "extension distribution + manifests" but does not enumerate the full mapping of dependency name to framework string. Is the initial list bounded to the two examples given (FastAPI, React), or should the architect define the detection matrix? (Resolve before implementation of `languages.py`.)

## Routing

**Next step**: Route to `tc-principal-architect`
**Reason**: Greenfield multi-module build with an externally-consumed versioned JSON schema, an analyser interface that will constrain all future extensions, and two open questions (analyser protocol shape, framework detection matrix) that must be resolved architecturally before implementation begins.
