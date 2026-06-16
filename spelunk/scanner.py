"""Orchestrator for the spelunk scanner.

Calls each registered analyser in sequence, assembles the final RepoScanResult,
and handles two layers of error containment:

Layer 1 (expected errors): errors collected internally by each analyser and
returned in AnalyserOutput.errors. The orchestrator merges these into the
top-level meta.errors list.

Layer 2 (backstop): each analyser call is wrapped in try/except Exception. If
an analyser itself crashes unexpectedly the exception is recorded as a ScanError
and the next analyser still runs. The scan always completes.
"""

from __future__ import annotations

import importlib.metadata
from datetime import datetime, timezone
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

from spelunk.analysers.file_tree import file_tree
from spelunk.interfaces import Analyser, AnalyserOutput, ScanInputs
from spelunk.models import (
    DependenciesInfo,
    FileTreeInfo,
    GitInfo,
    LanguageInfo,
    NotableFiles,
    RepoInfo,
    RepoScanResult,
    ScanError,
    ScanMeta,
    TestingInfo,
)
from spelunk.schema import SCHEMA_VERSION
from spelunk import utils

# ---------------------------------------------------------------------------
# Registered analysers — uncomment as each TASK lands
# ---------------------------------------------------------------------------

_ANALYSERS: list[Analyser] = [
    file_tree,
    # git_meta,       # wired in TASK-010
    # dependencies,   # wired in TASK-011/012
    # languages,      # wired in TASK-013
    # testing,        # wired in TASK-014
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_repo_info(root: Path, errors: list[ScanError]) -> RepoInfo:
    """Derive RepoInfo from the scan root.

    Attempts to read description, version, and license from pyproject.toml
    (in the [project] table). Falls back to None for any field that cannot be
    found or if the file is absent / unreadable.
    """
    name = root.name
    description: str | None = None
    version: str | None = None
    license_: str | None = None

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            with open(pyproject, "rb") as fh:
                data = tomllib.load(fh)
            project: object = data.get("project", {})
            if isinstance(project, dict):
                raw_desc = project.get("description")
                if isinstance(raw_desc, str):
                    description = raw_desc

                raw_ver = project.get("version")
                if isinstance(raw_ver, str):
                    version = raw_ver

                raw_license = project.get("license")
                if isinstance(raw_license, str):
                    license_ = raw_license
                elif isinstance(raw_license, dict):
                    # PEP 639 / legacy table form: {text = "MIT"} or {file = "LICENSE"}
                    text_val = raw_license.get("text")
                    if isinstance(text_val, str):
                        license_ = text_val
        except Exception as exc:
            errors.append(
                ScanError(
                    source="scanner._get_repo_info",
                    message=f"Failed to read pyproject.toml: {exc}",
                )
            )

    return RepoInfo(
        name=name,
        description=description,
        version=version,
        license=license_,
        root_path=str(root),
    )


def _get_scanner_version() -> str:
    """Return the installed spelunk package version, falling back to '0.1.0'."""
    try:
        return importlib.metadata.version("spelunk")
    except Exception:
        return "0.1.0"


# ---------------------------------------------------------------------------
# Public orchestrator
# ---------------------------------------------------------------------------


def scan_repo(root: Path) -> RepoScanResult:
    """Scan the repository rooted at *root* and return a RepoScanResult.

    Raises ValueError if *root* does not exist or is not a directory. The
    public scan() function in __init__.py catches this and converts it to a
    safe error result so it never propagates to the caller.
    """
    root = Path(root).resolve()
    if not root.exists():
        raise ValueError(f"Path does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"Path is not a directory: {root}")

    # Walk the filesystem — returns pre-filtered path list
    file_paths, walk_errors, walk_warnings = utils.walk_repo(root)

    ctx = ScanInputs(root=root, file_paths=file_paths)

    all_errors: list[ScanError] = [
        ScanError(source="utils.walk_repo", message=e) for e in walk_errors
    ]
    all_warnings: list[str] = list(walk_warnings)

    # Derive RepoInfo (may append to all_errors internally)
    repo_info = _get_repo_info(root, all_errors)

    # ---------------------------------------------------------------------------
    # Run each registered analyser (two-layer error containment)
    # ---------------------------------------------------------------------------

    # Accumulator for the file_tree result; populated if the analyser succeeds.
    file_tree_result: FileTreeInfo = FileTreeInfo(
        total_files=0,
        total_bytes=0,
        max_depth=0,
        extensions=[],
        notable_files=NotableFiles(),
    )

    for analyser in _ANALYSERS:
        try:
            output: AnalyserOutput = analyser(root, ctx)
        except Exception as exc:
            # Layer 2 backstop — unexpected analyser crash
            source = getattr(analyser, "name", str(analyser))
            all_errors.append(ScanError(source=source, message=str(exc)))
            continue

        # Layer 1 — merge per-item errors and warnings from the analyser
        all_errors.extend(output.errors)
        all_warnings.extend(output.warnings)

        # Route the payload to the correct result field based on analyser name
        analyser_name = getattr(analyser, "name", "")
        if analyser_name == "analysers.file_tree" and isinstance(
            output.payload, FileTreeInfo
        ):
            file_tree_result = output.payload

    # ---------------------------------------------------------------------------
    # Stub defaults for not-yet-wired analysers
    # ---------------------------------------------------------------------------

    git = GitInfo(
        present=False,
        remote_url=None,
        default_branch=None,
        last_commit=None,
        contributor_count=None,
        tags=[],
    )
    languages = LanguageInfo(primary=None, languages=[])
    frameworks: list[str] = []
    dependencies = DependenciesInfo(manifests=[], runtime=[], dev=[])
    testing = TestingInfo(frameworks=[], test_directories=[], test_file_count=0)

    scanner_version = _get_scanner_version()

    return RepoScanResult(
        schema_version=SCHEMA_VERSION,
        scanned_at=datetime.now(timezone.utc).isoformat(),
        repo=repo_info,
        git=git,
        languages=languages,
        frameworks=frameworks,
        file_tree=file_tree_result,
        dependencies=dependencies,
        testing=testing,
        meta=ScanMeta(
            scanner_version=scanner_version,
            errors=all_errors,
            warnings=all_warnings,
        ),
    )
