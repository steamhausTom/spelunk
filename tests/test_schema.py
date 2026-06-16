"""Tests for spelunk/schema.py — TASK-003."""

from __future__ import annotations

import ast
import pathlib


def test_schema_version_is_1_0_0() -> None:
    """SCHEMA_VERSION must be the string '1.0.0'."""
    from spelunk.schema import SCHEMA_VERSION

    assert SCHEMA_VERSION == "1.0.0"


def test_output_schema_is_dict() -> None:
    """OUTPUT_SCHEMA must be a dict."""
    from spelunk.schema import OUTPUT_SCHEMA

    assert isinstance(OUTPUT_SCHEMA, dict)


def test_output_schema_required_keys() -> None:
    """OUTPUT_SCHEMA must list all ten top-level output keys in 'required'."""
    from spelunk.schema import OUTPUT_SCHEMA

    expected_keys = {
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
    assert "required" in OUTPUT_SCHEMA
    assert expected_keys == set(OUTPUT_SCHEMA["required"])


def test_schema_no_intra_package_imports() -> None:
    """schema.py must not import from spelunk (zero intra-package imports)."""
    source = pathlib.Path(__file__).parent.parent / "spelunk" / "schema.py"
    tree = ast.parse(source.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top != "spelunk", f"spelunk import found: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                assert top != "spelunk", f"spelunk import found: {node.module}"
