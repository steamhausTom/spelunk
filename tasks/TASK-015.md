# TASK-015: Write schema drift test and top-level key pin test

**Status**: Pending
**Wave**: 5
**Assignee**: tc-qa-test-engineer
**Effort**: S — two focused test functions; requires jsonschema as a dev dependency
**Base Branch**: main
**Dependencies**: TASK-003, TASK-007, TASK-013, TASK-014

## Description

Implement the schema drift guard described in architect finding F4. This is a CI-only test (dev dependency; not a runtime concern) that validates a reference scan output against the authoritative JSON Schema dict in `schema.py` and pins the set of required top-level keys.

The test must fail if:
- The scan output fails JSON Schema validation.
- A required top-level key is removed from `models.py` (the drift test pins the key set).
- `schema_version` is not `"1.0.0"`.
- `scanned_at` is not a valid ISO 8601 timestamp.

### Add `jsonschema` to dev dependencies

Add `jsonschema>=4.0` to the `dev` optional-dependencies in `pyproject.toml`. This is a test-only concern — it must NOT be a runtime dependency.

### Test file: `tests/test_schema_drift.py`

#### Test 1 — `test_output_validates_against_schema`

```python
def test_output_validates_against_schema(build_repo, tmp_path):
    root = build_repo({
        "main.py": "print('hello')",
        "requirements.txt": "flask==3.0.0\npytest==7.4.0",
        "package.json": '{"dependencies": {"react": "^18.0.0"}}',
    }, git_init=True)

    result = scan(str(root))
    output = result.to_dict()

    import jsonschema
    from spelunk.schema import OUTPUT_SCHEMA
    jsonschema.validate(instance=output, schema=OUTPUT_SCHEMA)
    # If validation raises jsonschema.ValidationError, the test fails
```

This test exercises a realistic (though minimal) repo to produce a real scan output and validates it against `OUTPUT_SCHEMA`.

#### Test 2 — `test_required_top_level_keys_present`

```python
REQUIRED_TOP_LEVEL_KEYS = {
    "schema_version",
    "scanned_at",
    "repo",
    "git",
    "languages",
    "frameworks",
    "file_tree",
    "dependencies",
    "testing",
    "meta",
}

def test_required_top_level_keys_present(build_repo):
    root = build_repo({"a.py": "x = 1"})
    result = scan(str(root))
    output = result.to_dict()
    missing = REQUIRED_TOP_LEVEL_KEYS - set(output.keys())
    assert not missing, f"Missing top-level keys: {missing}"
```

This test will fail immediately if a key is removed from `RepoScanResult` in `models.py`, catching accidental structural drift before it reaches consumers.

#### Test 3 — `test_schema_version_and_scanned_at`

```python
def test_schema_version_and_scanned_at(build_repo):
    root = build_repo({"a.py": "x = 1"})
    result = scan(str(root))
    output = result.to_dict()

    from spelunk.schema import SCHEMA_VERSION
    assert output["schema_version"] == SCHEMA_VERSION
    assert output["schema_version"] == "1.0.0"

    # Validate ISO 8601 format
    from datetime import datetime
    datetime.fromisoformat(output["scanned_at"])  # raises ValueError if invalid
```

## Acceptance Criteria

- [ ] [qa] Given a reference scan output produced by `scan()` · When validated against `OUTPUT_SCHEMA` using `jsonschema.validate()` · Then validation passes with zero errors
- [ ] [qa] Given a `RepoScanResult` with all required fields populated · When `to_dict()` is called · Then all ten required top-level keys are present
- [ ] [qa] Given `schema_version` is removed from `RepoScanResult` in models.py · When the drift test runs · Then it fails with a clear assertion error naming the missing key
- [ ] [qa] Given any scan output · When `schema_version` is inspected · Then it equals `"1.0.0"` and `scanned_at` parses as a valid ISO 8601 datetime

## Notes / Risks

- `jsonschema` is a dev/test-only dependency. Do NOT add it to `[project.dependencies]` — add it to `[project.optional-dependencies.dev]` in `pyproject.toml`.
- The drift test is not marked `@pytest.mark.slow` — it should always run in CI as a fast guard.
- `jsonschema.validate()` with `OUTPUT_SCHEMA` defined to `draft-07` semantics requires the schema dict to include `"$schema": "http://json-schema.org/draft-07/schema#"` if strict draft validation is desired. Without it, `jsonschema` defaults to draft-07 but does not enforce the `$schema` meta-check.
- If `OUTPUT_SCHEMA` only specifies the top-level required key set (not recursive nested schemas), the validation test will pass for any output that contains the required keys — even if nested structures are wrong. This is acceptable for v1. Future tasks may extend the schema for deeper validation.
- This test must pass on a clean checkout with only the `file_tree` analyser running — stub values for other analysers must still be schema-conforming (ensured by TASK-007's stub defaults).
