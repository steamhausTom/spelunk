# TASK-004: Implement interfaces.py Analyser Protocol

**Status**: Pending
**Wave**: 1
**Assignee**: tc-backend-engineer
**Effort**: S — Protocol definition plus supporting input/output types; no runtime logic
**Base Branch**: main
**Dependencies**: None

## Description

Implement `spelunk/interfaces.py` — the formal structural contract that every analyser must satisfy. This module uses `typing.Protocol` to define the `Analyser` interface and the `AnalyserOutput` envelope dataclass. All other `spelunk` modules may import from `interfaces.py`, but `interfaces.py` must never import from `scanner.py`.

### Types to define

**`ScanInputs`** — immutable context passed to every analyser call. Define as a `dataclasses.dataclass` (or `typing.NamedTuple`) with:
```
root: Path          # resolved absolute path to the repo root
file_paths: list[Path]   # pre-walked list of non-ignored, non-binary-skipped paths from utils.py
```

`ScanInputs` may be extended in future to pass pre-computed data (e.g., parsed dependency output to `languages.py`). Design it as a dataclass so fields can be added without breaking callers.

**`AnalyserOutput`** — the envelope every analyser returns. Define as a `dataclasses.dataclass`:
```
payload: Any        # the typed analyser result (e.g. GitInfo, FileTreeInfo)
errors: list[ScanError]   # expected per-item errors collected during analysis
warnings: list[str]       # non-fatal notices
source: str         # set by the analyser; matches the error source string e.g. "analysers.git_meta"
```

Import `ScanError` from `models.py`. `payload` is typed `Any` because each analyser returns a different payload type; the orchestrator in `scanner.py` knows the concrete type and assigns it to the correct field.

**`Analyser`** — the Protocol:
```python
@runtime_checkable
class Analyser(Protocol):
    name: str

    def __call__(self, root: Path, ctx: ScanInputs) -> AnalyserOutput:
        ...
```

The `name` attribute is used by the orchestrator as the `source` string in error records. `@runtime_checkable` is optional but recommended so `isinstance(obj, Analyser)` works in tests.

### Import constraints

`interfaces.py` may import from:
- `pathlib` (stdlib)
- `typing` (stdlib)
- `dataclasses` (stdlib)
- `spelunk.models` (for `ScanError`)

`interfaces.py` must NOT import from:
- `spelunk.scanner`
- `spelunk.utils`
- Any analyser module

## Acceptance Criteria

- [ ] [eng] Given a function with signature `(root: Path, ctx: ScanInputs) -> AnalyserOutput` and a `name: str` attribute · When `mypy --strict` checks it against the `Analyser` Protocol · Then it type-checks as a valid `Analyser` with zero errors
- [ ] [eng] Given a function that returns `str` instead of `AnalyserOutput` · When `mypy --strict` checks it against the `Analyser` Protocol · Then mypy reports a type error
- [ ] [eng] Given `interfaces.py` · When its import graph is inspected (e.g. `import ast; ast.parse(open(...).read())`) · Then `scanner` does not appear in any import statement
- [ ] [eng] Given an `AnalyserOutput` with a non-empty `errors` list · When `to_dict()` is called on the embedded `ScanError` objects · Then each error dict has `source` and `message` keys
- [ ] [eng] Given `mypy --strict` runs against `interfaces.py` · When it completes · Then zero type errors are reported

## Notes / Risks

- The `payload: Any` typing on `AnalyserOutput` is intentional. Using a generic `AnalyserOutput[T]` is possible but adds complexity under `mypy --strict` (especially with `dataclasses` and `Protocol`). Start with `Any` and tighten if needed in a later task.
- `ScanInputs.file_paths` is the pre-walked path list produced by `utils.py`. Passing it in `ScanInputs` means analysers do not re-walk the filesystem — they receive the filtered list. This is the key no-global-state mechanism.
- `@runtime_checkable` on `Protocol` only validates attribute and method presence at runtime, not type correctness — mypy is the authoritative checker.
- Architect decision (F1): rejected duck-typing convention with `# type: ignore` and ABC. Do not introduce either alternative.
