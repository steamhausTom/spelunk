# TASK-012: Implement dependencies.py — Go, Rust, Ruby, Java/Kotlin, PHP ecosystem parsers

**Status**: Pending
**Wave**: 3
**Assignee**: tc-backend-engineer
**Effort**: M — five ecosystems with heterogeneous manifest formats (XML, Gradle DSL, plain text variants); wire analyser into orchestrator
**Base Branch**: main
**Dependencies**: TASK-011

## Description

Extend `spelunk/analysers/dependencies.py` (created in TASK-011) with parsers for the remaining five ecosystems: Go, Rust, Ruby, Java/Kotlin, and PHP.

After this task is complete, wire the `dependencies` analyser into the orchestrator (`scanner.py`) and assign its payload to `RepoScanResult.dependencies`.

### Manifest files to handle

| Ecosystem | Files |
|-----------|-------|
| Go | `go.mod` |
| Rust | `Cargo.toml` |
| Ruby | `Gemfile` |
| Java/Kotlin | `pom.xml`, `build.gradle` |
| PHP | `composer.json` |

### Go — `go.mod`

Parse line by line. The format is:
```
module github.com/owner/repo

go 1.21

require (
    github.com/gin-gonic/gin v1.9.1
    github.com/stretchr/testify v1.8.4 // indirect
)
```

Extract each `require` block entry. Lines ending with `// indirect` are transitive dependencies — still include them but mark in version string. All entries are `dev=False` (Go does not distinguish dev deps in `go.mod`). Ecosystem: `"go"`.

### Rust — `Cargo.toml`

Use the tomllib/tomli guard to parse as TOML. Extract:
- `[dependencies]` → `dev=False`
- `[dev-dependencies]` → `dev=True`
- `[build-dependencies]` → `dev=True` (build-time only)

Each entry may be a string version (`requests = "0.11"`) or a table (`requests = { version = "0.11", features = [...] }`). Extract `name` and `version` string in both cases. Ecosystem: `"rust"`.

### Ruby — `Gemfile`

Parse line by line. Match lines starting with `gem "name"` or `gem 'name'`. Extract the gem name and optional version constraint. Lines inside a `group :development, :test do ... end` block are `dev=True`; otherwise `dev=False`. Track `in_dev_group: bool` state while parsing. Ecosystem: `"ruby"`.

### Java/Kotlin — `pom.xml`

Parse using `xml.etree.ElementTree` (stdlib). Navigate to `<project><dependencies><dependency>` elements. Extract `<groupId>`, `<artifactId>`, and `<version>`. Concatenate as `name = "groupId:artifactId"`.

Scope mapping:
- `<scope>test</scope>` → `dev=True`
- `<scope>provided</scope>` → `dev=False`
- No `<scope>` element → `dev=False`

Ecosystem: `"java"`.

### Java/Kotlin — `build.gradle`

Groovy DSL parsing with regex (do NOT import Groovy or execute the file). Use conservative regex to match dependency declaration patterns:

```
implementation 'com.example:lib:1.0'
testImplementation 'org.junit:junit:5.9'
api "com.google.guava:guava:31.0"
```

Pattern: `(implementation|api|compileOnly|runtimeOnly|testImplementation|testRuntimeOnly|annotationProcessor)\s+['"]([^'"]+)['"]`

Configurations starting with `test` → `dev=True`; all others → `dev=False`.

Emit a warning if the file appears to use Kotlin DSL (`build.gradle.kts`) as the regex may not parse it reliably: `"build.gradle.kts: Kotlin DSL detected, dependency extraction may be incomplete"`.

Ecosystem: `"java"`.

### PHP — `composer.json`

Parse as JSON. Extract:
- `require` → `dev=False` (skip the `php` and `ext-*` entries — they are platform requirements, not packages)
- `require-dev` → `dev=True`

Ecosystem: `"php"`.

### Wire into orchestrator

After adding the five parsers, in `scanner.py`:
1. Import `dependencies` from `spelunk.analysers.dependencies`.
2. Uncomment `dependencies` in `_ANALYSERS`.
3. Assign `output.payload` to `RepoScanResult.dependencies`.

## Acceptance Criteria

- [ ] [eng] Given a `go.mod` with `require github.com/gin-gonic/gin v1.9.1` · When parsed · Then `runtime` contains `{name: "github.com/gin-gonic/gin", version: "v1.9.1", ecosystem: "go", dev: False}`
- [ ] [eng] Given a `Cargo.toml` with `[dev-dependencies]` containing `serde_json = "1.0"` · When parsed · Then `dev` contains `{name: "serde_json", ecosystem: "rust", dev: True}`
- [ ] [eng] Given a `Gemfile` with `gem "rails"` outside a dev group and `gem "rspec"` inside `group :development, :test` · When parsed · Then `rails` is `dev=False` and `rspec` is `dev=True`
- [ ] [eng] Given a `pom.xml` with a `<dependency>` having `<scope>test</scope>` · When parsed · Then that dependency appears in `dev` with `dev=True`
- [ ] [eng] Given a `composer.json` with `require-dev` containing `phpunit/phpunit` · When parsed · Then `phpunit/phpunit` appears in `dev` with `dev=True`
- [ ] [eng] Given each of the seven ecosystems (Python/Node handled in TASK-011, plus Go/Rust/Ruby/Java/PHP added here) · When the corresponding manifest is present in a scanned repo · Then at least one dependency entry appears with the correct `name`, `version` (or `None`), and `ecosystem` fields
- [ ] [eng] Given `mypy --strict` runs against the complete `dependencies.py` · When it completes · Then zero type errors are reported
- [ ] [qa] Given a monorepo with `pom.xml` files in two subdirectories · When the scan completes · Then all Java dependencies are merged and `meta.warnings[]` names both manifest paths

## Notes / Risks

- `xml.etree.ElementTree` is stdlib but does NOT protect against XML external entity (XXE) attacks. This is acceptable for a local file scanner (the "attacker" is the repo being scanned, not a remote). Document this explicitly: the scanner only processes local files on the operator's own machine.
- `build.gradle` regex is fragile against multi-line dependency declarations and string interpolation. Emit a warning when the file is found but the regex yields zero deps: `"build.gradle: no dependencies extracted — file may use unsupported DSL patterns"`.
- `Gemfile` group tracking: `group :development do ... end`, `group :development, :test do ... end`, and nested groups all use `end` as the terminator. The parser must track nesting depth if groups can be nested, or treat the first `end` after a dev group start as its close. For v1, treat the first unindented `end` as the group close — document the limitation.
- PHP `require` often includes `"php": ">=8.0"` and `"ext-json": "*"` — filter these by checking if the key starts with `"php"` or `"ext-"`.
- `build.gradle.kts` (Kotlin script): emit a warning rather than failing silently. The filename is `build.gradle.kts` — detect by `path.name == "build.gradle.kts"`.
