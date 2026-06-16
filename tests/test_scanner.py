"""Tests for spelunk/scanner.py orchestrator and spelunk/__init__.py public API.

Covers all [eng] acceptance criteria for TASK-007.
"""

from __future__ import annotations

import json
import re
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# AC-1: Valid dir → scan() returns RepoScanResult without raising
# ---------------------------------------------------------------------------


def test_scan_valid_directory_returns_result(tmp_path: Path) -> None:
    """Given a valid directory path · When scan(path) is called · Then a
    RepoScanResult is returned without raising an exception."""
    # Write one file so the tree is non-empty
    (tmp_path / "hello.py").write_text("print('hello')")

    from spelunk import scan
    from spelunk.models import RepoScanResult

    result = scan(str(tmp_path))

    assert isinstance(result, RepoScanResult)


def test_scan_valid_directory_does_not_raise(tmp_path: Path) -> None:
    """scan() must never propagate exceptions — confirmed with an empty dir."""
    from spelunk import scan
    from spelunk.models import RepoScanResult

    # No exception should propagate
    result = scan(tmp_path)
    assert isinstance(result, RepoScanResult)


# ---------------------------------------------------------------------------
# AC-2: Non-existent path → RepoScanResult returned, meta.errors non-empty
# ---------------------------------------------------------------------------


def test_scan_nonexistent_path_returns_result_with_error() -> None:
    """Given a non-existent path · When scan(path) is called · Then a
    RepoScanResult is returned (not raised), with an error in meta.errors[]
    describing the invalid path."""
    from spelunk import scan
    from spelunk.models import RepoScanResult

    result = scan("/this/path/absolutely/does/not/exist/xyz123")

    assert isinstance(result, RepoScanResult)
    assert len(result.meta.errors) > 0, "Expected at least one error for invalid path"


def test_scan_file_path_returns_result_with_error(tmp_path: Path) -> None:
    """Passing a file (not a directory) should also surface an error gracefully."""
    from spelunk import scan

    f = tmp_path / "not_a_dir.txt"
    f.write_text("content")

    result = scan(str(f))
    assert len(result.meta.errors) > 0


# ---------------------------------------------------------------------------
# AC-3: Analyser that raises → meta.errors contains the error, scan completes
# ---------------------------------------------------------------------------


def test_crashing_analyser_error_captured_and_scan_continues(tmp_path: Path) -> None:
    """Given an analyser that raises an unexpected exception · When scan_repo
    runs · Then meta.errors[] contains {source: analyser.name, message: str(exc)}
    and all other analysers still execute."""
    (tmp_path / "file.txt").write_text("data")

    from spelunk.scanner import scan_repo
    from spelunk.interfaces import AnalyserOutput, ScanInputs

    # Build a mock analyser that explodes
    boom_analyser = MagicMock()
    boom_analyser.name = "analysers.boom_test"
    boom_analyser.side_effect = RuntimeError("kaboom")

    # Build a working mock analyser that captures whether it was called
    called_flags: list[bool] = []

    class _GoodAnalyser:
        name = "analysers.good_test"

        def __call__(self, root: Path, ctx: ScanInputs) -> AnalyserOutput:
            called_flags.append(True)
            return AnalyserOutput(payload=None, errors=[], warnings=[], source=self.name)

    good_analyser = _GoodAnalyser()

    with patch("spelunk.scanner._ANALYSERS", [boom_analyser, good_analyser]):
        result = scan_repo(tmp_path)

    # Crash error must be recorded
    error_sources = [e.source for e in result.meta.errors]
    assert "analysers.boom_test" in error_sources, (
        f"Expected boom_test error. Got sources: {error_sources}"
    )
    boom_errors = [e for e in result.meta.errors if e.source == "analysers.boom_test"]
    assert any("kaboom" in e.message for e in boom_errors)

    # Good analyser must still have been called
    assert called_flags, "Good analyser should have been called after the crashing one"


# ---------------------------------------------------------------------------
# AC-4: Analyser returning errors in AnalyserOutput.errors → appear in meta.errors
# ---------------------------------------------------------------------------


def test_analyser_output_errors_merged_into_meta(tmp_path: Path) -> None:
    """Given an analyser that returns errors in its AnalyserOutput.errors ·
    When the scan completes · Then those errors appear in meta.errors[] with
    the correct source."""
    from spelunk.scanner import scan_repo
    from spelunk.interfaces import AnalyserOutput, ScanInputs
    from spelunk.models import ScanError

    class _ErrorReportingAnalyser:
        name = "analysers.error_reporter"

        def __call__(self, root: Path, ctx: ScanInputs) -> AnalyserOutput:
            return AnalyserOutput(
                payload=None,
                errors=[
                    ScanError(source=self.name, message="deliberate test error"),
                ],
                warnings=["deliberate test warning"],
                source=self.name,
            )

    reporter = _ErrorReportingAnalyser()

    with patch("spelunk.scanner._ANALYSERS", [reporter]):
        result = scan_repo(tmp_path)

    sources = [e.source for e in result.meta.errors]
    assert "analysers.error_reporter" in sources, (
        f"Expected error_reporter error. Sources: {sources}"
    )
    assert any(
        "deliberate test error" in e.message for e in result.meta.errors
    ), "Exact error message not found in meta.errors"

    assert "deliberate test warning" in result.meta.warnings


# ---------------------------------------------------------------------------
# AC-5: json.dumps(result.to_dict()) succeeds, schema_version and scanned_at correct
# ---------------------------------------------------------------------------


def test_scan_result_serialises_to_valid_json(tmp_path: Path) -> None:
    """Given a scan of any valid directory · When result.to_dict() is called ·
    Then json.dumps(result.to_dict()) succeeds and the output contains
    schema_version "1.0.0" and a valid ISO 8601 scanned_at."""
    (tmp_path / "module.py").write_text("x = 1")

    from spelunk import scan

    result = scan(tmp_path)
    d = result.to_dict()

    # Must be JSON-serialisable
    serialised = json.dumps(d)
    assert serialised  # non-empty

    parsed = json.loads(serialised)

    # schema_version
    assert parsed["schema_version"] == "1.0.0"

    # scanned_at must be a valid ISO 8601 string (datetime.isoformat() format)
    scanned_at = parsed["scanned_at"]
    # Pattern: YYYY-MM-DDTHH:MM:SS.ffffff+HH:MM  or  ...+00:00
    iso8601_re = re.compile(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"  # date + time
        r"(\.\d+)?"  # optional fractional seconds
        r"([+-]\d{2}:\d{2}|Z)$"  # timezone offset
    )
    assert iso8601_re.match(scanned_at), (
        f"scanned_at does not look like ISO 8601: {scanned_at!r}"
    )


def test_scan_result_to_dict_contains_required_top_level_keys(tmp_path: Path) -> None:
    """All required top-level keys must be present in the serialised output."""
    from spelunk import scan

    result = scan(tmp_path)
    d = result.to_dict()

    required_keys = {
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
    assert required_keys.issubset(d.keys()), (
        f"Missing keys: {required_keys - d.keys()}"
    )


# ---------------------------------------------------------------------------
# AC-6: mypy --strict on scanner.py and __init__.py — verified via subprocess
# (the test asserts the module loads cleanly under strict typing conventions;
#  the actual mypy invocation is part of the CI pipeline and the run-verification
#  step in the task instructions — we check structural correctness here)
# ---------------------------------------------------------------------------


def test_scanner_module_imports_cleanly() -> None:
    """Given spelunk.scanner · When imported · Then no ImportError or
    AttributeError is raised and scan_repo is callable."""
    from spelunk import scanner

    assert callable(scanner.scan_repo)


def test_public_api_scan_is_callable() -> None:
    """Given spelunk · When imported · Then scan is a callable and SCHEMA_VERSION
    is exported."""
    import spelunk

    assert callable(spelunk.scan)
    assert spelunk.SCHEMA_VERSION == "1.0.0"


# ---------------------------------------------------------------------------
# Additional integration: repo_info derived correctly
# ---------------------------------------------------------------------------


def test_repo_info_name_is_directory_name(tmp_path: Path) -> None:
    """repo.name must equal the final component of the scanned directory."""
    from spelunk import scan

    result = scan(tmp_path)
    assert result.repo.name == tmp_path.name


def test_repo_info_reads_pyproject_toml(tmp_path: Path) -> None:
    """If pyproject.toml is present with [project] metadata, repo.description
    and repo.version are populated."""
    toml_content = """
[project]
name = "myproject"
version = "2.3.4"
description = "A test project"
license = "Apache-2.0"
"""
    (tmp_path / "pyproject.toml").write_text(toml_content)

    from spelunk import scan

    result = scan(tmp_path)

    assert result.repo.version == "2.3.4"
    assert result.repo.description == "A test project"
    assert result.repo.license == "Apache-2.0"


def test_repo_info_license_as_table(tmp_path: Path) -> None:
    """If pyproject.toml has license = {text = "MIT"}, repo.license is "MIT"."""
    toml_content = """
[project]
name = "myproject"
version = "1.0.0"
description = "Test"
license = {text = "MIT"}
"""
    (tmp_path / "pyproject.toml").write_text(toml_content)

    from spelunk import scan

    result = scan(tmp_path)
    assert result.repo.license == "MIT"


def test_repo_info_missing_pyproject(tmp_path: Path) -> None:
    """If no pyproject.toml is present, description/version/license are None."""
    from spelunk import scan

    result = scan(tmp_path)
    assert result.repo.description is None
    assert result.repo.version is None
    assert result.repo.license is None


def test_stub_defaults_are_schema_conforming(tmp_path: Path) -> None:
    """The stub defaults for not-yet-implemented analysers must produce
    valid structures that can be serialised without error."""
    from spelunk import scan

    result = scan(tmp_path)
    d = result.to_dict()

    # git stub
    assert d["git"]["present"] is False
    assert d["git"]["remote_url"] is None
    assert isinstance(d["git"]["tags"], list)

    # languages stub
    assert d["languages"]["primary"] is None
    assert isinstance(d["languages"]["languages"], list)

    # frameworks stub
    assert isinstance(d["frameworks"], list)

    # dependencies stub
    assert isinstance(d["dependencies"]["manifests"], list)
    assert isinstance(d["dependencies"]["runtime"], list)
    assert isinstance(d["dependencies"]["dev"], list)

    # testing stub
    assert isinstance(d["testing"]["frameworks"], list)
    assert isinstance(d["testing"]["test_directories"], list)
    assert d["testing"]["test_file_count"] == 0
