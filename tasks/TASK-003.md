# TASK-003: Implement schema.py with SCHEMA_VERSION and JSON Schema dict

**Status**: Pending
**Wave**: 1
**Assignee**: tc-backend-engineer
**Effort**: S — constant definition and JSON Schema transcription; no runtime logic
**Base Branch**: main
**Dependencies**: None

## Description

Implement `spelunk/schema.py`. This module has two responsibilities:

1. **Declare the version constant**: `SCHEMA_VERSION = "1.0.0"` — this is the externally-consumed contract version. Any breaking change to the output shape (rename, remove, or retype an existing key) requires a version bump. Additive changes (new optional keys) are non-breaking.

2. **Define the authoritative JSON Schema dict**: A module-level `OUTPUT_SCHEMA` dict that describes the complete output structure conforming to JSON Schema draft-07 (compatible with the `jsonschema` library if installed). This dict is used exclusively in the schema drift test (TASK-015); it is NOT evaluated on the scan hot path.

### Schema dict requirements

The `OUTPUT_SCHEMA` dict must:
- Be `type: "object"` at the top level with `"additionalProperties": false`.
- Enumerate all required top-level keys: `schema_version`, `scanned_at`, `repo`, `git`, `languages`, `frameworks`, `file_tree`, `dependencies`, `testing`, `meta`.
- For each top-level key, define at minimum: `type` and (for objects) `properties` with their types. Full recursive depth is not required for nested objects in v1 — depth-1 key presence is sufficient for the drift test.
- Include `"required": [<all top-level keys>]` so that the drift test detects removed keys.

### What NOT to do

- Do NOT call `jsonschema.validate()` or any schema validation function anywhere in `schema.py` — validation is a test-only concern (TASK-015).
- Do NOT import from `models.py` — this module must have zero intra-package dependencies so it can be imported safely in any context.
- Do NOT derive the schema dict programmatically from the dataclasses — it must be a static, human-readable declaration.

### SCHEMA_VERSION versioning rule (document as a comment)

Add a comment block above `SCHEMA_VERSION` documenting the versioning rule:
- Additive changes (new optional fields): non-breaking, no version bump required.
- Renames, removals, or type changes to existing fields: breaking, bump the minor or major component.

## Acceptance Criteria

- [ ] [eng] Given `schema.py` is imported · When `SCHEMA_VERSION` is accessed · Then its value is the string `"1.0.0"`
- [ ] [eng] Given `OUTPUT_SCHEMA` · When inspected · Then it is a `dict` containing `"required"` with all ten top-level output keys listed
- [ ] [eng] Given `schema.py` · When imported · Then it imports nothing from `spelunk` (zero intra-package imports)
- [ ] [eng] Given `mypy --strict` runs against `schema.py` · When it completes · Then zero type errors are reported

## Notes / Risks

- The `OUTPUT_SCHEMA` dict does not need to be complete to draft-07 depth to serve the drift test. It only needs to enumerate required top-level keys with correct types. This is intentional — the schema is not used for runtime validation, so over-specifying it creates maintenance burden without benefit.
- Future tasks that extend the output shape must also update `OUTPUT_SCHEMA` and assess whether a `SCHEMA_VERSION` bump is required. The schema drift test in TASK-015 will catch the omission.
- `jsonschema` is not a runtime dependency and must not be added as one. If the drift test needs it, it belongs in dev dependencies only (handled in TASK-015).
