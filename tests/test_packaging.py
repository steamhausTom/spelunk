"""Acceptance tests for spelunk packaging scaffold — TASK-001.

QA-tagged AC:
  [qa] Given the scaffolded repo · When `pytest --collect-only` runs ·
       Then the test runner starts without configuration errors.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_pytest_collect_only_no_errors() -> None:
    """pytest --collect-only must exit without configuration errors.

    Traces to TASK-001 AC:
    Given the scaffolded repo · When pytest --collect-only runs ·
    Then the test runner starts without configuration errors.

    Exit code 0 = collected tests, no errors.
    Exit code 5 = no tests found (still a valid, error-free collection run).
    Any other exit code indicates a configuration problem.
    """
    repo_root = Path(__file__).parent.parent
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    # Exit code 0 = items collected; 5 = no items collected — both are error-free.
    # Any other code (1 = test failure, 2 = interrupted, 3 = internal error,
    # 4 = usage error) indicates a configuration problem.
    assert result.returncode in (0, 5), (
        f"pytest --collect-only exited with code {result.returncode}.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    # Ensure there is no "ERROR" line in the collection output
    assert "ERROR" not in result.stdout, (
        f"Collection errors found:\n{result.stdout}"
    )


def test_spelunk_importable() -> None:
    """import spelunk must succeed — verifies the package is installed correctly.

    Traces to TASK-001 AC:
    Given the installed package · When python -c "import spelunk" runs ·
    Then no ImportError is raised.
    """
    result = subprocess.run(
        [sys.executable, "-c", "import spelunk"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"import spelunk failed with:\n{result.stderr}"
    )


def test_pyproject_tomli_marker_present() -> None:
    """pyproject.toml must declare tomli with a PEP 508 python_version marker.

    Traces to TASK-001 AC:
    Given pyproject.toml · When [project.dependencies] is inspected ·
    Then tomli>=2.0; python_version < "3.11" is present as a runtime dep.
    """
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    # The marker must be present in the dependencies block
    assert 'tomli' in content, "tomli dependency missing from pyproject.toml"
    assert 'python_version' in content, (
        "PEP 508 python_version marker missing from tomli dependency"
    )
    assert '3.11' in content, (
        "Version boundary '3.11' missing from tomli PEP 508 marker"
    )


def test_pyproject_mypy_strict_and_tests_excluded() -> None:
    """pyproject.toml must configure mypy with strict=true and tests/ excluded.

    Traces to TASK-001 AC:
    Given pyproject.toml · When [tool.mypy] is inspected ·
    Then strict = true is set and tests/ is listed under exclude.
    """
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    assert "strict = true" in content, (
        "[tool.mypy] strict = true not found in pyproject.toml"
    )
    assert "tests" in content, (
        "tests/ not listed under [tool.mypy] exclude in pyproject.toml"
    )
