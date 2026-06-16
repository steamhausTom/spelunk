"""spelunk public API.

The single entry point for all consumers: both programmatic callers and the
CLI (__main__.py) use scan() to produce a RepoScanResult.

Contract: scan() NEVER raises. All errors surface via result.meta.errors[].
"""

from __future__ import annotations

from pathlib import Path

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


def scan(path: str | Path) -> RepoScanResult:
    """Scan the repository at *path* and return a RepoScanResult.

    Never raises. If an unexpected exception escapes from scan_repo, the
    exception is captured and returned as an error in meta.errors[].
    """
    try:
        from spelunk.scanner import scan_repo

        return scan_repo(Path(path))
    except Exception as exc:
        from datetime import datetime, timezone

        return RepoScanResult(
            schema_version=SCHEMA_VERSION,
            scanned_at=datetime.now(timezone.utc).isoformat(),
            repo=RepoInfo(
                name="",
                description=None,
                version=None,
                license=None,
                root_path=str(path),
            ),
            git=GitInfo(
                present=False,
                remote_url=None,
                default_branch=None,
                last_commit=None,
                contributor_count=None,
                tags=[],
            ),
            languages=LanguageInfo(primary=None, languages=[]),
            frameworks=[],
            file_tree=FileTreeInfo(
                total_files=0,
                total_bytes=0,
                max_depth=0,
                extensions=[],
                notable_files=NotableFiles(),
            ),
            dependencies=DependenciesInfo(manifests=[], runtime=[], dev=[]),
            testing=TestingInfo(frameworks=[], test_directories=[], test_file_count=0),
            meta=ScanMeta(
                scanner_version="0.1.0",
                errors=[ScanError(source="spelunk.scan", message=str(exc))],
                warnings=[],
            ),
        )


__all__ = ["scan", "RepoScanResult", "SCHEMA_VERSION"]
