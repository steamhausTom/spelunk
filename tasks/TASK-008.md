# TASK-008: Implement __main__.py CLI entry point

**Status**: Pending
**Wave**: 2
**Assignee**: tc-backend-engineer
**Effort**: S — thin Click wrapper over scan(); no business logic lives here
**Base Branch**: main
**Dependencies**: TASK-007

## Description

Implement `spelunk/__main__.py` — the CLI entry point invoked by `python -m spelunk <path> [--output file.json]`.

This module is a thin Click wrapper. All business logic lives in `scan()`. The CLI's only responsibilities are:
1. Accept and validate the `path` argument and `--output` option.
2. Call `scan(path)`.
3. Serialise the result to JSON.
4. Write to a file or stdout.
5. Exit 0 on success; exit 1 on unrecoverable errors (file write failure, etc.).

**Note**: `scan()` never raises — so the CLI does not need to handle exceptions from it. If `scan()` returns a result with `meta.errors`, that is still a successful scan and exits 0.

### Implementation

```python
import sys
import json
import click
from pathlib import Path
from spelunk import scan

@click.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Write JSON output to this file instead of stdout.")
def main(path: str, output: str | None) -> None:
    result = scan(path)
    json_output = json.dumps(result.to_dict(), indent=2)

    if output:
        try:
            Path(output).write_text(json_output, encoding="utf-8")
        except OSError as exc:
            click.echo(f"Error writing output: {exc}", err=True)
            sys.exit(1)
    else:
        click.echo(json_output)


if __name__ == "__main__":
    main()
```

The `click.Path(exists=True, file_okay=False)` validator on `path` means Click reports a user-friendly error if the path does not exist or is not a directory — before `scan()` is even called.

### `pyproject.toml` entry point

Ensure `[project.scripts]` in `pyproject.toml` contains:
```
spelunk = "spelunk.__main__:main"
```
This was scaffolded in TASK-001 but confirm it points to the `main` function in this module.

## Acceptance Criteria

- [ ] [eng] Given a valid directory path · When `python -m spelunk <path>` runs · Then a JSON document is printed to stdout and the process exits 0
- [ ] [eng] Given a valid directory path and `--output result.json` · When `python -m spelunk <path> --output result.json` runs · Then `result.json` is created with JSON content, nothing is printed to stdout, and the process exits 0
- [ ] [eng] Given a non-existent path · When `python -m spelunk /nonexistent` runs · Then Click prints a user-friendly error to stderr and the process exits with a non-zero code
- [ ] [eng] Given the JSON output printed to stdout · When parsed with `json.loads()` · Then it contains `schema_version` equal to `"1.0.0"`
- [ ] [eng] Given `mypy --strict` runs against `__main__.py` · When it completes · Then zero type errors are reported
- [ ] [qa] Given `python -m spelunk <path>` · When run against a real repository · Then the output is valid JSON and the process exits 0

## Notes / Risks

- `click.Path(exists=True, file_okay=False, resolve_path=True)` handles path resolution and existence validation. The `resolve_path=True` flag means `path` arrives in `main()` as an absolute string — no need to call `.resolve()` again before passing to `scan()`.
- Do NOT write to stderr on normal scan completion even if `meta.errors` is non-empty. A scan with errors is still a successful scan — the caller can inspect `meta.errors` in the JSON. Only write to stderr and exit 1 on infrastructure failures (file write failure).
- JSON output uses `indent=2` for human readability. This is not configurable in v1.
- The `if __name__ == "__main__": main()` guard at the bottom is required for `python -m spelunk` invocation.
