# TASK-013: Implement languages.py — language detection and framework rule table

**Status**: Pending
**Wave**: 4
**Assignee**: tc-backend-engineer
**Effort**: M — two distinct concerns (language detection from extension stats, framework detection from dependency data) plus the rule table maintenance
**Base Branch**: main
**Dependencies**: TASK-002, TASK-004, TASK-011, TASK-012

## Description

Implement `spelunk/analysers/languages.py`. This analyser has two distinct responsibilities:

1. **Language detection**: derive language distribution from the file extension stats already computed by `file_tree.py`. Because this data is in `ScanInputs`, it must be available before this analyser runs.
2. **Framework detection**: consume the parsed `DependenciesInfo` payload from the `dependencies` analyser to identify known frameworks via a bounded rule table (F3).

Both responsibilities consume previously-computed data rather than re-reading the filesystem. The `ScanInputs` dataclass (defined in `interfaces.py`) needs to be extended to carry the dependency payload. See the Notes section for how to pass this data.

At the end of this task, wire `languages` into `scanner.py`'s `_ANALYSERS` list and assign its payload to `RepoScanResult.languages` and `RepoScanResult.frameworks`.

### Module-level attributes

```python
name = "analysers.languages"
```

### Part 1 — Language detection

#### Extension-to-language map

Define a module-level `dict[str, str]` mapping lowercase file extensions to language names:

```python
_EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".c": "C",
    ".h": "C",
    ".hpp": "C++",
    ".swift": "Swift",
    ".scala": "Scala",
    ".r": "R",
    ".R": "R",
    ".m": "Objective-C",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "CSS",
    ".sass": "CSS",
    ".sql": "SQL",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".xml": "XML",
    ".toml": "TOML",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".dart": "Dart",
    ".lua": "Lua",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".hrl": "Erlang",
    ".clj": "Clojure",
    ".cljs": "ClojureScript",
    ".hs": "Haskell",
    ".lhs": "Haskell",
    ".fs": "F#",
    ".fsx": "F#",
    ".ml": "OCaml",
    ".mli": "OCaml",
    ".tf": "HCL",
    ".hcl": "HCL",
}
```

#### Detection logic

Group `ctx.file_paths` by language using the map. Skip extensions not in the map. For each language, sum `file_count` and `byte_total`. Sort results by `file_count` descending. The language with the highest `file_count` is `primary`. If no recognized extensions are found, `primary = None` and `languages = []`.

### Part 2 — Framework detection rule table (F3)

Define a module-level rule table mapping `(ecosystem, normalised_dep_name)` to a framework label. The ecosystem strings match those used in `DependenciesInfo.runtime[*].ecosystem`.

```python
_FRAMEWORK_RULES: dict[tuple[str, str], str] = {
    ("python", "fastapi"): "FastAPI",
    ("python", "django"): "Django",
    ("python", "flask"): "Flask",
    ("javascript", "react"): "React",      # package.json ecosystem = "node"
    ("node", "react"): "React",
    ("node", "vue"): "Vue",
    ("node", "next"): "Next.js",
    ("node", "@angular/core"): "Angular",
    ("node", "svelte"): "Svelte",
    ("node", "express"): "Express",
    ("rust", "actix-web"): "Actix",
    ("rust", "axum"): "Axum",
    ("ruby", "rails"): "Rails",
    ("php", "laravel/framework"): "Laravel",
    ("java", "org.springframework.boot:spring-boot-starter"): "Spring Boot",
    ("java", "org.springframework.boot:spring-boot-starter-web"): "Spring Boot",
}
```

Normalise dependency names before lookup:
- Python: lowercase and replace `-` with `-` (already normalised).
- Node: lowercase the package name.
- Rust: exact match.
- Ruby: exact match.
- Java: exact match on `groupId:artifactId`.
- PHP: exact match.

#### Detection logic

Iterate all `Dependency` entries in `DependenciesInfo.runtime` (and `DependenciesInfo.dev` — some frameworks appear in dev deps in testing contexts). Look up `(ecosystem, normalised_name)` in `_FRAMEWORK_RULES`. Collect matching labels into a set (avoid duplicates). Return as a sorted list.

If no frameworks are detected, return `[]` — never `None` (F3 constraint).

### Passing dependency data to the analyser

The `languages` analyser needs access to the `DependenciesInfo` payload produced by the `dependencies` analyser. Two options:

**Option A (recommended)**: Extend `ScanInputs` in `interfaces.py` to include an optional field `dependencies: DependenciesInfo | None = None`. The orchestrator in `scanner.py` populates this after running the `dependencies` analyser, then passes the updated `ctx` to `languages`. This requires `ScanInputs` to be a mutable dataclass or built fresh for the `languages` call.

**Option B**: Pass `DependenciesInfo` as an additional argument by making `languages.__call__` accept it via `ctx`. Same approach, different field name.

Use Option A. Update `interfaces.py` to add `dependencies: DependenciesInfo | None = field(default=None)` to `ScanInputs`. Update `scanner.py` to populate it before calling `languages`.

### Return

Return `AnalyserOutput` with a `payload` of type `tuple[LanguageInfo, list[str]]` (or a small container dataclass). The orchestrator assigns `payload[0]` to `RepoScanResult.languages` and `payload[1]` to `RepoScanResult.frameworks`.

Alternatively, define a `LanguageAnalyserPayload(language_info: LanguageInfo, frameworks: list[str])` dataclass and return that as the payload.

## Acceptance Criteria

- [ ] [eng] Given a repo with 10 `.py` files and 3 `.js` files · When the languages analyser runs · Then `languages.primary` equals `"Python"` and the `languages` list contains both `Python` and `JavaScript` entries ranked by file count
- [ ] [eng] Given `DependenciesInfo` containing a runtime dep `{name: "fastapi", ecosystem: "python"}` · When the languages analyser runs · Then `"FastAPI"` appears in the returned frameworks list
- [ ] [eng] Given `DependenciesInfo` containing `{name: "react", ecosystem: "node"}` · When the languages analyser runs · Then `"React"` appears in the returned frameworks list
- [ ] [eng] Given a repo with no recognised framework dependencies · When the languages analyser runs · Then the frameworks list is `[]` (not `null`)
- [ ] [eng] Given a repo with only binary files or unknown extensions · When the languages analyser runs · Then `languages.primary` is `None` and `languages.languages` is `[]`
- [ ] [eng] Given the `languages` analyser runs · When `dependencies` data has not yet been computed (None) · Then the analyser returns an empty frameworks list and emits no error
- [ ] [eng] Given `mypy --strict` runs against `languages.py` · When it completes · Then zero type errors are reported
- [ ] [qa] Given a repo with `pyproject.toml` listing FastAPI as a dependency · When the full scan completes · Then `"FastAPI"` appears in the `frameworks` array in the JSON output

## Notes / Risks

- The orchestrator must run `dependencies` before `languages` — this is enforced by the `_ANALYSERS` list order in `scanner.py` (F10). Document this constraint with a comment in `scanner.py`.
- `ScanInputs` modification: adding `dependencies: DependenciesInfo | None = None` requires updating `interfaces.py`. This is a non-breaking additive change — existing code that constructs `ScanInputs(root=..., file_paths=...)` still works because the new field has a default.
- Framework deduplication: a repo may have both `fastapi` and `flask` in its deps (perhaps for a migration). Both should appear in `frameworks`. Use a `set` internally to deduplicate and return a `sorted(list(...))` for deterministic output.
- The `_EXTENSION_LANGUAGE_MAP` is not exhaustive. Unknown extensions are silently ignored. Do not emit warnings for unrecognised extensions — this would produce excessive noise on polyglot repos.
- Architect decision (F3): extension-based framework inference is out of scope. Framework detection only uses the dependency manifest data.
