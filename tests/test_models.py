"""Tests for spelunk/models.py — TASK-002."""

from __future__ import annotations

import json

import pytest


def test_import_only_stdlib() -> None:
    """models.py must import only from the standard library."""
    import ast
    import pathlib

    source = pathlib.Path(__file__).parent.parent / "spelunk" / "models.py"
    tree = ast.parse(source.read_text())
    stdlib_prefixes = {"__future__", "dataclasses", "typing"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top not in {"spelunk"}, f"Non-stdlib import found: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                assert top not in {"spelunk"}, f"Non-stdlib import found: {node.module}"


def test_no_from_dict_method() -> None:
    """models.py must not define from_dict()."""
    import ast
    import pathlib

    source = pathlib.Path(__file__).parent.parent / "spelunk" / "models.py"
    tree = ast.parse(source.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            assert node.name != "from_dict", "from_dict() must not be defined in models.py"


def test_scan_error_to_dict() -> None:
    """ScanError.to_dict() must return a dict with 'source' and 'message'."""
    from spelunk.models import ScanError

    err = ScanError(source="analysers.git_meta", message="git not found")
    d = err.to_dict()
    assert d["source"] == "analysers.git_meta"
    assert d["message"] == "git not found"


def test_repo_scan_result_json_serialisable() -> None:
    """json.dumps(result.to_dict()) must succeed with no custom encoder."""
    from spelunk.models import (
        DependenciesInfo,
        ExtensionStats,
        FileTreeInfo,
        GitInfo,
        LanguageInfo,
        LanguageStats,
        ManifestInfo,
        NotableFiles,
        RepoInfo,
        RepoScanResult,
        ScanError,
        ScanMeta,
        TestingInfo,
        Dependency,
    )

    result = RepoScanResult(
        schema_version="1.0.0",
        scanned_at="2026-06-16T12:00:00Z",
        repo=RepoInfo(
            name="spelunk",
            description="A static analysis tool",
            version="0.1.0",
            license="MIT",
            root_path="/some/path",
        ),
        git=GitInfo(
            present=True,
            remote_url="https://github.com/example/spelunk.git",
            default_branch="main",
            last_commit="abc1234",
            contributor_count=3,
            tags=["v0.1.0"],
        ),
        languages=LanguageInfo(
            primary="Python",
            languages=[LanguageStats(name="Python", file_count=10, byte_total=5000)],
        ),
        frameworks=["FastAPI"],
        file_tree=FileTreeInfo(
            total_files=10,
            total_bytes=5000,
            max_depth=3,
            extensions=[ExtensionStats(extension=".py", file_count=10, byte_total=5000)],
            notable_files=NotableFiles(
                entrypoints=["main.py"],
                config_files=[".env"],
                ci_configs=[".github/workflows/ci.yml"],
                docker=["Dockerfile"],
                iac=["main.tf"],
            ),
        ),
        dependencies=DependenciesInfo(
            manifests=[ManifestInfo(path="pyproject.toml", ecosystem="python")],
            runtime=[Dependency(name="click", version=">=8.0", ecosystem="python", dev=False)],
            dev=[Dependency(name="pytest", version=None, ecosystem="python", dev=True)],
        ),
        testing=TestingInfo(
            frameworks=["pytest"],
            test_directories=["tests/"],
            test_file_count=5,
        ),
        meta=ScanMeta(
            scanner_version="0.1.0",
            errors=[ScanError(source="analysers.git_meta", message="example error")],
            warnings=["Large file skipped: big.bin"],
        ),
    )

    serialised = json.dumps(result.to_dict())
    assert isinstance(serialised, str)
    parsed = json.loads(serialised)
    assert parsed["schema_version"] == "1.0.0"


def test_git_info_present_false_to_dict() -> None:
    """GitInfo with present=False must serialise correctly with git key present."""
    from spelunk.models import GitInfo

    git = GitInfo(
        present=False,
        remote_url=None,
        default_branch=None,
        last_commit=None,
        contributor_count=None,
        tags=[],
    )
    d = git.to_dict()
    assert d["present"] is False
    assert d["remote_url"] is None
    assert d["tags"] == []


def test_no_business_logic_in_models() -> None:
    """models.py must not contain conditionals or data transformations (no if/for at module scope)."""
    import ast
    import pathlib

    source = pathlib.Path(__file__).parent.parent / "spelunk" / "models.py"
    tree = ast.parse(source.read_text())

    # Check that no function body (outside to_dict) contains complex logic
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "to_dict":
            # to_dict must be a simple return statement
            body = node.body
            # Allow a single return statement only (possibly preceded by docstring)
            non_docstring = [
                stmt for stmt in body
                if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant))
            ]
            assert len(non_docstring) == 1, "to_dict() must contain only a return statement"
            assert isinstance(non_docstring[0], ast.Return), "to_dict() must return a value"
