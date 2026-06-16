# TASK-011: Implement dependencies.py — Python and Node ecosystem parsers

**Status**: Pending
**Wave**: 3
**Assignee**: tc-backend-engineer
**Effort**: M — four Python manifest formats (including static AST setup.py per F8) and three Node formats; monorepo merging logic
**Base Branch**: main
**Dependencies**: TASK-002, TASK-004, TASK-007

## Description

Implement the Python and Node.js sections of `spelunk/analysers/dependencies.py`. This is split from TASK-012 (Go/Rust/Ruby/Java/PHP) so the two can be parallelised after TASK-011 proves the module structure and monorepo merge logic.

TASK-011 establishes:
- The module's `name` attribute and `__call__` signature.
- The manifest discovery loop (scan `ctx.file_paths` for known manifest filenames).
- The monorepo merge logic.
- The Python parsers: `requirements.txt`, `pyproject.toml`, `Pipfile`, `setup.py` (static AST).
- The Node.js parsers: `package.json`, `package-lock.json`, `yarn.lock`.

TASK-012 extends the same module by adding the remaining five ecosystems.

At the end of this task, the analyser is not yet wired into the orchestrator (TASK-012 completes the module — wire both together after TASK-012).

### Module-level attributes

```python
name = "analysers.dependencies"
```

### `__call__(root: Path, ctx: ScanInputs) -> AnalyserOutput`

#### Manifest discovery

Iterate `ctx.file_paths`. Identify manifest files by `path.name`:
- Python: `requirements.txt`, `pyproject.toml`, `Pipfile`, `setup.py`
- Node: `package.json`, `package-lock.json`, `yarn.lock`
- (Go/Rust/Ruby/Java/PHP added in TASK-012)

Build a `list[ManifestInfo]` and a `dict[str, list[Path]]` mapping ecosystem → list of manifest paths found.

#### Monorepo detection and merge

If more than one manifest of the same filename/type is found (e.g. multiple `package.json`):
- Merge their dependency lists into a single list.
- Append a warning for each: `f"Multiple {filename} found: {', '.join(str(p) for p in paths)}"`.

#### Python parsers

**`requirements.txt`**

Parse line by line. Skip blank lines and comment lines (`#`). For each dependency line, strip extras (`[...]`) and version specifiers to extract the package name. Preserve the full version string if present (e.g. `Django==4.2` → name=`Django`, version=`==4.2`). All entries are `dev=False`.

Edge cases:
- `-r other_requirements.txt` (include lines): skip with a warning.
- URL/VCS requirements (`git+https://...`): extract the egg name if present (`#egg=name`); otherwise emit a warning and skip.

**`pyproject.toml`**

Use the `try: import tomllib / except ModuleNotFoundError: import tomli as tomllib` guard (F6).

Parse `[project.dependencies]` for runtime deps. Parse `[project.optional-dependencies]` entries — mark all optional extras as `dev=True` (conservative approximation; exact dev/runtime classification is not always determinable from extras).

Parse `[tool.poetry.dependencies]` and `[tool.poetry.dev-dependencies]` if present.

**`Pipfile`**

Parse `[packages]` section as runtime deps and `[dev-packages]` section as dev deps. `Pipfile` uses TOML-like syntax — use the same tomllib/tomli guard.

**`setup.py` — static AST parsing (F8 — SECURITY CRITICAL)**

Never `import`, `exec`, or `runpy` the file. Use `ast.parse()` to extract `install_requires` from `setup()` call arguments.

Strategy:
1. `ast.parse(path.read_text())` — catch `SyntaxError` and emit a warning.
2. Walk the AST looking for a `Call` node where the function name is `setup` (or `setuptools.setup`).
3. Find the `install_requires` keyword argument.
4. If the argument is a `Constant` list literal, extract each string element as a dependency.
5. If the argument is a `Name` or any non-literal form (dynamically built), emit a warning: `f"setup.py: could not statically resolve install_requires in {path}"` — return no deps from this file.

All deps from `setup.py` are `dev=False`.

#### Node.js parsers

**`package.json`**

Parse as JSON. Extract:
- `dependencies` → `dev=False`
- `devDependencies` → `dev=True`
- `peerDependencies` → `dev=False` (treat as runtime)

Skip `package.json` files inside `node_modules/` — they are already filtered by gitignore in most repos, but add an explicit guard: skip any `package.json` whose path contains `node_modules` as a path component.

**`package-lock.json`**

Parse as JSON. Extract the top-level `packages` dict (npm v2/v3 lockfile format) or `dependencies` dict (v1). For each entry, extract `name` and `version`. Do NOT recurse into transitive deps — only top-level entries. Mark all as `dev=False` (lockfile does not reliably distinguish dev).

Emit a warning: `"package-lock.json parsed: dev/runtime classification unavailable from lockfile"`.

**`yarn.lock`**

Parse line by line (Yarn 1 classic format). Extract package name and resolved version from blocks starting with `"<name>@<version>":`. Only top-level entries. Mark all as `dev=False`. Emit a warning.

Yarn Berry (v2+) uses a different format — detect by presence of `__metadata:` at the top. If Yarn Berry format detected, emit a warning: `"yarn.lock: Yarn Berry format detected, parsing skipped"` and return no deps from this file.

#### Return

Return `AnalyserOutput(payload=DependenciesInfo(manifests=[...], runtime=[...], dev=[...]), errors=errors, warnings=warnings, source=name)`.

## Acceptance Criteria

- [ ] [eng] Given a `requirements.txt` with `Flask==2.3.0` and `pytest==7.4.0` · When the parser runs · Then `runtime` contains `{name: "Flask", version: "==2.3.0", ecosystem: "python", dev: False}` and `pytest` appears with the correct version
- [ ] [eng] Given a `pyproject.toml` with `[project.dependencies]` listing `fastapi>=0.100` · When the parser runs · Then `runtime` contains `{name: "fastapi", ecosystem: "python", dev: False}`
- [ ] [eng] Given a `package.json` with `"dependencies": {"react": "^18.0.0"}` and `"devDependencies": {"jest": "^29.0.0"}` · When the parser runs · Then `runtime` contains `react` with `dev=False` and `dev` contains `jest` with `dev=True`
- [ ] [eng] Given a `setup.py` with a literal `install_requires=["requests>=2.28"]` · When parsed · Then `requests` appears in `runtime` without executing the file
- [ ] [eng] Given a `setup.py` with a dynamic `install_requires=get_requirements()` · When parsed · Then a warning is emitted and no deps are extracted from this file
- [ ] [eng] Given two `package.json` files in different subdirectories · When the analyser runs · Then all dependencies from both are merged into the output and `meta.warnings[]` names both paths
- [ ] [eng] Given `mypy --strict` runs against `dependencies.py` (Python/Node sections) · When it completes · Then zero type errors are reported
- [ ] [qa] Given a `setup.py` containing side-effecting code at module level (e.g. `os.system("rm -rf /")`) · When the scan runs · Then that code does not execute

## Notes / Risks

- **F8 is security-critical**: the `setup.py` parser must NEVER call `import`, `exec`, `eval`, `runpy.run_path`, or any equivalent. The AST-only path is non-negotiable. Add a comment to this effect above the function.
- The `tomllib`/`tomli` import guard pattern (F6): `try: import tomllib \n except ModuleNotFoundError: import tomli as tomllib`. This must appear in any file that parses TOML — both `dependencies.py` and (if applicable) `scanner.py`.
- Pipfile uses TOML syntax but the file extension is not `.toml`. The tomllib parser can parse any TOML content regardless of filename.
- `package-lock.json` v1 and v2/v3 formats differ in structure. Detect by checking for the presence of a `lockfileVersion` key: v1 uses `dependencies`, v2/v3 use `packages`. Handle both.
- Dependency name normalisation: Python packages should be normalised to lowercase (PEP 503 canonical form). Node packages are case-sensitive — preserve case.
