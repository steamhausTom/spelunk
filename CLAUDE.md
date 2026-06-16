# spelunk

## Overview

`spelunk` is a Python CLI utility and importable module that performs static analysis on a local code repository. It extracts structured metadata — file tree statistics, language and framework detection, dependency manifests, git history, and project identity — and emits a single JSON document for use in downstream portfolio analysis pipelines and agent workflows.

Primary users are developers and automated pipelines that need a machine-readable snapshot of a codebase without cloning or executing it.

---

## Module Structure

```
spelunk/
├── __init__.py          # Public API: exposes scan(path) -> RepoScanResult
├── __main__.py          # CLI entry point: python -m spelunk <path> [--output file.json]
├── scanner.py           # Orchestrator: calls each analyser in sequence, assembles final result
├── analysers/
│   ├── file_tree.py     # Recursive directory walk, extension stats, notable file detection
│   ├── git_meta.py      # Git metadata extraction (remote, branch, commits, contributors, tags)
│   ├── languages.py     # Language and framework detection from extension distribution + manifests
│   ├── dependencies.py  # Manifest parsers for Python, Node, Go, Rust, Ruby, Java/Kotlin, PHP
│   └── testing.py       # Test framework detection and test file enumeration
├── models.py            # Dataclasses / TypedDicts representing the output JSON schema
├── utils.py             # .gitignore filtering (pathspec), symlink cycle detection, path helpers
└── schema.py            # JSON schema definition and SCHEMA_VERSION constant
```

Each analyser is independently callable. `scanner.py` imports all of them and assembles the top-level `RepoScanResult`. Errors in any single analyser are caught, logged to `meta.errors[]`, and do not abort the scan.

---

## Tech Stack

- **Language**: Python 3.10+
- **CLI framework**: `click >= 8.0`
- **`.gitignore` parsing**: `pathspec >= 0.12`
- **Git metadata**: `gitpython >= 3.1` (subprocess `git` as fallback)
- **TOML parsing**: `tomllib` (stdlib, Python 3.11+) with `tomli >= 2.0` as a conditional fallback for 3.10
- **Testing**: `pytest`, `pytest-cov`
- **Type checking**: `mypy`
- **Package management**: `pyproject.toml` (PEP 517/518)

### Entry Points

| Mode | Invocation |
|------|-----------|
| CLI | `python -m spelunk <path> [--output file.json]` |
| Library | `from spelunk import scan; result = scan("/path/to/repo")` |

---

## Output JSON Schema

The scanner emits a single JSON object conforming to `schema_version: "1.0.0"`. Top-level keys:

| Key | Description |
|-----|-------------|
| `schema_version` | Always `"1.0.0"` — bump when the shape changes |
| `scanned_at` | ISO 8601 timestamp of when the scan ran |
| `repo` | Name, description, version, license, root path |
| `git` | Present flag, remote URL, default branch, last commit, contributor count, tags |
| `languages` | Primary language, per-language file counts and byte totals |
| `frameworks` | Array of detected framework strings (e.g. `"FastAPI"`, `"React"`) |
| `file_tree` | Total files, total bytes, max depth, per-extension stats, notable files |
| `dependencies` | Manifest files found, runtime deps, dev deps — each with name, version, ecosystem |
| `testing` | Detected test frameworks, test directories, test file count |
| `meta` | `scanner_version`, `errors[]`, `warnings[]` |

Full schema with field types is defined in `spelunk/schema.py` and validated by `models.py`.

### Notable file categories (within `file_tree.notable_files`)

- `entrypoints` — `main.py`, `index.js`, `app.*`, `server.*`, etc.
- `config_files` — `.env`, `docker-compose.yml`, `Makefile`, etc.
- `ci_configs` — `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, etc.
- `docker` — `Dockerfile`, `docker-compose*.yml`
- `iac` — Terraform `.tf`, Pulumi, CDK, CloudFormation

---

## Architecture & Conventions

- **Non-fatal error handling**: every analyser wraps its logic in a try/except. Exceptions are serialised to `meta.errors[]` with a `source` field (e.g. `"analysers.git_meta"`) and a `message`. The scan always completes and always produces output.
- **`.gitignore` enforcement**: `utils.py` builds a `pathspec.PathSpec` from the repo root's `.gitignore` (and any nested `.gitignore` files encountered during the walk). Files matching any rule are excluded from all analysis.
- **Symlink handling**: follow symlinks during the walk. Maintain a `set` of resolved inodes already visited; skip any symlink whose target resolves to an inode already in the set (cycle detection).
- **Binary file detection**: read the first 8 KB of each file. If a null byte is present, treat as binary — count and record extension, skip content analysis.
- **Large file threshold**: files exceeding 10 MB are counted and their extension recorded, but their content is not read. A warning is appended to `meta.warnings[]`.
- **Monorepo awareness**: collect all manifest files found at any depth. If more than one manifest of the same type is found (e.g. multiple `package.json`), merge their dependency lists and append a warning naming each path.
- **Missing read permissions**: `PermissionError` during file open is caught per-file; the path is added to `meta.errors[]` and the walk continues.
- **Dataclass models**: `models.py` uses `dataclasses.dataclass` with `from __future__ import annotations`. All public fields have type annotations. `to_dict()` / `from_dict()` helpers are provided for JSON serialisation.
- **No global state**: analysers are pure functions or stateless classes. The orchestrator in `scanner.py` constructs fresh state per call.

---

## Dependency Manifest Coverage

| Ecosystem | Files parsed |
|-----------|-------------|
| Python | `requirements.txt`, `pyproject.toml`, `Pipfile`, `setup.py` |
| Node | `package.json`, `package-lock.json`, `yarn.lock` |
| Go | `go.mod` |
| Rust | `Cargo.toml` |
| Ruby | `Gemfile` |
| Java / Kotlin | `pom.xml`, `build.gradle` |
| PHP | `composer.json` |

For each ecosystem, the parser extracts: package name, version constraint, and dev vs. runtime classification (where the manifest format supports it).

---

## Edge Cases & Constraints

| Case | Handling |
|------|---------|
| No `.git` directory | Scan proceeds; `git.present` is `false`, all git fields are `null` |
| Monorepo with multiple manifests | Merge all dependencies; warn with paths in `meta.warnings[]` |
| Symlink cycles | Inode-based cycle detection; cyclic links skipped silently |
| Binary files | Detected via null-byte heuristic; counted, content skipped |
| Files > 10 MB | Counted and extension recorded; content not read; warning emitted |
| Missing read permissions | Per-file `PermissionError` caught; path logged to `meta.errors[]` |
| Mixed-language repos | All detected languages reported; ranked by file count; primary = highest rank |
| Repos up to ~50k files | Walk must complete without hanging; no unbounded in-memory structures |

---

## Key Commands

| Task | Command |
|------|---------|
| Install (dev) | `pip install -e ".[dev]"` |
| Run (CLI) | `python -m spelunk <path>` |
| Test | `pytest` |
| Test with coverage | `pytest --cov=spelunk` |
| Type check | `mypy spelunk` |
| Lint | `ruff check spelunk` *(add ruff to dev deps if desired)* |
| Build | `python -m build` |

> Update the Key Commands table with the real commands once the project is scaffolded.

---

## Development Conventions

- Target **Python 3.10+**. Use `match` statements, `X | Y` union syntax, and `from __future__ import annotations` where needed for forward references.
- All new modules must have a corresponding test file under `tests/` with at least one test per public function.
- Use `mypy` in strict mode for `spelunk/` (exclude `tests/` from strict checking).
- Never raise exceptions from the public `scan()` API. All errors must be non-fatal and surface via `meta.errors[]`.
- Prefer the standard library where possible. Add a dependency only when the stdlib equivalent would require substantially more code (e.g. `pathspec` for gitignore semantics).
- Keep `models.py` free of business logic — it is a pure data layer.
- The `schema_version` constant in `schema.py` must be bumped for any breaking change to the output shape.

---

## ThunderCats Agents

> **Invocation**: when the user types `ThunderCats, Ho!`, invoke the `tc-project-init` **agent** using the Agent tool — do NOT attempt to call it as a skill. It is not a slash command. Use `Agent(tc-project-init)` directly.

> **CRITICAL — pre-implementation gate**: The main conversation MUST NOT write application code, scaffold project files, or invoke engineer agents (`tc-backend-engineer`, `tc-frontend-engineer`, `tc-platform-engineer`) without a `PLAN.md` already existing. Start every new feature, bugfix, or change by invoking `tc-workflow` — it runs the discovery-to-planning sequence and exits once `PLAN.md` is ready. If `PLAN.md` does not exist and you are about to implement something, stop and invoke `tc-workflow` first.

Agents coordinate through **`PLAN.md`** (a slim task index) and individual task files under **`tasks/`**. `tc-project-planner` creates and owns both; all other agents read the index to locate their task, then load `tasks/TASK-XXX.md` for full detail. No agent creates or restructures task files except `tc-project-planner`. Engineer agents may check off AC checkboxes and update the `Status` field in their assigned task file only.

> **Scope note**: remove or annotate any rows below that don't apply to this project (e.g. if there is no UI layer, note that `tc-frontend-engineer` has no scope here).

### Pipeline

```
tc-workflow (mandatory entry gate — invoke when PLAN.md does not exist)
    ↓
tc-product-owner (opt)  →  tc-principal-architect (opt)  →  tc-project-planner
                                                              ↓
                                              backend / frontend / platform
                                              (implement → push → In Review)
                                                              ↓
                                                       tc-qa-test-engineer
                                                    (tests on feature branch)
                                                              ↓
                                             tc-senior-tech-reviewer + tc-security-ops-engineer
                                                              ↓ findings loop
                                                       tc-project-planner → raises PR
```

### Agent roles

| Agent | ThunderCats name | Role |
|-------|-----------------|------|
| `tc-workflow` | **ThunderCats Workflow** | Mandatory entry gate — runs tc-product-owner → tc-principal-architect → tc-project-planner in sequence and exits once PLAN.md is ready; invoke this before any implementation starts |
| `tc-product-owner` | **ThunderCats PO** | Translates GitHub issues and raw feature requests into structured briefs with acceptance criteria for spelunk enhancements |
| `tc-principal-architect` | **ThunderCats Architect** | Reviews architectural decisions such as analyser interface design, schema versioning strategy, and plugin extension points |
| `tc-project-planner` | **ThunderCats Planner** | Decomposes scanner features and bugfixes into sequenced TASK files and maintains the PLAN.md index |
| `tc-backend-engineer` | **ThunderCats Backend** | Implements all scanner analysers, models, CLI, and orchestrator logic in Python |
| `tc-frontend-engineer` | **ThunderCats Frontend** | No scope in this CLI/library-only project unless a web UI or browser-based report viewer is added |
| `tc-platform-engineer` | **ThunderCats Platform** | Manages CI/CD pipelines, PyPI publishing workflows, and any containerised test environments |
| `tc-qa-test-engineer` | **ThunderCats QA** | Writes pytest unit and integration tests for each analyser, covering edge cases defined in the constraints table |
| `tc-security-ops-engineer` | **ThunderCats SecOps** | Reviews path traversal risks, symlink handling, and dependency supply-chain vulnerabilities in the scanner |
| `tc-senior-tech-reviewer` | **ThunderCats Reviewer** | Reviews implementation quality, spots edge-case gaps in the analysers, and challenges assumptions about manifest parsing correctness |

### Per-story tc-workflow (mandatory — every task, every session)

A task is not done until its PR is open and review + security steps have cleared.

-1. **`tc-workflow`** *(mandatory when `PLAN.md` does not exist)* — before starting any new feature, bugfix, or initiative, check whether `PLAN.md` exists. If it does not, invoke `tc-workflow` — it runs steps 0–2 below in sequence and exits once `PLAN.md` is written. Do not invoke any agent at step 0 or below until `tc-workflow` has completed or `PLAN.md` already exists.
0. **`tc-product-owner`** *(optional, run automatically by `tc-workflow`)* — when starting from a GitHub issue or raw feature idea, invoke this agent first to produce a `briefs/BRIEF-NNN.md` with user-facing acceptance criteria and a routing decision (architect needed? yes/no)
1. **`tc-principal-architect`** *(optional, run automatically by `tc-workflow` when routed)* — reviews the brief and emits architectural findings to `tc-project-planner`
2. **`tc-project-planner`** translates the brief/findings into a `tasks/TASK-XXX.md` file with Given/When/Then acceptance criteria, and adds a row to the `PLAN.md` index
3. **Coding agent** (backend / frontend / platform) reads the `PLAN.md` index, opens `tasks/TASK-XXX.md`, creates a `feature/<slug>` branch, implements test-first, checks off AC items in the task file, pushes the branch, updates Status to `In Review` — does not open a PR
4. **`tc-qa-test-engineer`** reads the task file AC lines, writes acceptance tests traceable to them, pushes to the feature branch — does not open a PR
5. **`tc-senior-tech-reviewer`** reviews the completed diff — emits findings to `tc-project-planner` if any
6. **`tc-security-ops-engineer`** reviews for security issues — emits findings to `tc-project-planner` if any
7. **`tc-project-planner`** ingests findings from steps 5 and 6, resolves any blocking findings (Critical / High), then raises the PR once all three review agents have passed

**Execution rules:**
- **No implementation without a plan**: engineer agents (`tc-backend-engineer`, `tc-frontend-engineer`, `tc-platform-engineer`) must never be invoked unless `PLAN.md` exists. Invoke `tc-workflow` to create it.
- After step 3 completes: `tc-project-planner` launches steps 4, 5, and 6 **in parallel** in a single message
- Steps 5 and 6 always run together — never one without the other
- Findings from steps 4, 5, and 6 are ingested by `tc-project-planner`
- Blocking findings (Critical / High) must be resolved before `tc-project-planner` raises the PR
- XS findings (one-line fixes) may be applied inline; anything larger becomes a new `TASK-XXX`

**No engineer opens a PR.** `tc-project-planner` raises the PR after all three review agents pass and blocking findings are cleared. No agent merges its own PR — all PRs wait for human review and approval.

### Findings format

When any agent identifies work to add to the plan, it emits a findings block and routes it to `tc-project-planner` — it does not write to `PLAN.md` or task files directly.

```markdown
## Findings (route to tc-project-planner)

### F1
- **Source**: <agent-name>
- **Type**: Bug | Security finding | Refactor | Coverage gap | Design issue | Scope split required
- **Severity**: Critical | High | Medium | Low | Informational
- **Location**: `file:line` (or `n/a` if cross-cutting)
- **Title**: <short, verb-led>
- **Description**: <what is wrong or needs doing, 1–3 sentences>
- **Proposed acceptance criteria**:
  - [ ] [eng|qa] Given <precondition> · When <action> · Then <observable outcome>
- **Suggested dependencies**: TASK-XXX (or `none`)
- **Effort hint**: XS | S | M | L | XL
```
