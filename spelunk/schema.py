"""Schema version constant and authoritative JSON Schema dict for spelunk output.

This module has zero intra-package dependencies and must not call jsonschema.validate()
or any schema validation function — validation is a test-only concern (TASK-015).

Versioning rules
----------------
- Additive changes (new optional fields): non-breaking — no version bump required.
- Renames, removals, or type changes to existing fields: breaking — bump the minor
  or major component of SCHEMA_VERSION.
"""

# The externally-consumed contract version.
# Bump for any breaking change to the output shape.
SCHEMA_VERSION = "1.0.0"

# Authoritative JSON Schema dict (draft-07 compatible).
# Used exclusively in the schema drift test (TASK-015).
# This is a static, human-readable declaration — not derived programmatically.
OUTPUT_SCHEMA: dict = {  # type: ignore[type-arg]
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "SpelunkOutput",
    "type": "object",
    "additionalProperties": False,
    "required": [
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
    ],
    "properties": {
        "schema_version": {"type": "string"},
        "scanned_at": {"type": "string"},
        "repo": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": ["string", "null"]},
                "version": {"type": ["string", "null"]},
                "license": {"type": ["string", "null"]},
                "root_path": {"type": "string"},
            },
        },
        "git": {
            "type": "object",
            "properties": {
                "present": {"type": "boolean"},
                "remote_url": {"type": ["string", "null"]},
                "default_branch": {"type": ["string", "null"]},
                "last_commit": {"type": ["string", "null"]},
                "contributor_count": {"type": ["integer", "null"]},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
        },
        "languages": {
            "type": "object",
            "properties": {
                "primary": {"type": ["string", "null"]},
                "languages": {"type": "array"},
            },
        },
        "frameworks": {
            "type": "array",
            "items": {"type": "string"},
        },
        "file_tree": {
            "type": "object",
            "properties": {
                "total_files": {"type": "integer"},
                "total_bytes": {"type": "integer"},
                "max_depth": {"type": "integer"},
                "extensions": {"type": "array"},
                "notable_files": {"type": "object"},
            },
        },
        "dependencies": {
            "type": "object",
            "properties": {
                "manifests": {"type": "array"},
                "runtime": {"type": "array"},
                "dev": {"type": "array"},
            },
        },
        "testing": {
            "type": "object",
            "properties": {
                "frameworks": {"type": "array", "items": {"type": "string"}},
                "test_directories": {"type": "array", "items": {"type": "string"}},
                "test_file_count": {"type": "integer"},
            },
        },
        "meta": {
            "type": "object",
            "properties": {
                "scanner_version": {"type": "string"},
                "errors": {"type": "array"},
                "warnings": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}
