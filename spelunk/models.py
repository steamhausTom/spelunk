"""Data layer for spelunk output types.

All types in this module are pure dataclasses with no business logic.
The only method permitted on each class is to_dict(), which delegates to
dataclasses.asdict(). No from_dict() is implemented — see architect decision F5.

All paths are stored as str (not pathlib.Path) to ensure json.dumps compatibility
without a custom encoder.
"""

from __future__ import annotations

import dataclasses
import json


@dataclasses.dataclass
class ScanError:
    """A non-fatal error recorded during a scan."""

    source: str  # e.g. "analysers.git_meta"
    message: str

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return dataclasses.asdict(self)


@dataclasses.dataclass
class ScanMeta:
    """Scanner run metadata, including errors and warnings."""

    scanner_version: str
    errors: list[ScanError] = dataclasses.field(default_factory=list)
    warnings: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return dataclasses.asdict(self)


@dataclasses.dataclass
class RepoInfo:
    """Identity metadata for the scanned repository."""

    name: str
    description: str | None
    version: str | None
    license: str | None
    root_path: str  # stored as str, not Path

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return dataclasses.asdict(self)


@dataclasses.dataclass
class GitInfo:
    """Git repository metadata."""

    present: bool
    remote_url: str | None
    default_branch: str | None
    last_commit: str | None  # ISO 8601 or short SHA
    contributor_count: int | None
    tags: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return dataclasses.asdict(self)


@dataclasses.dataclass
class LanguageStats:
    """Per-language file count and byte total."""

    name: str
    file_count: int
    byte_total: int

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return dataclasses.asdict(self)


@dataclasses.dataclass
class LanguageInfo:
    """Detected language distribution."""

    primary: str | None
    languages: list[LanguageStats] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return dataclasses.asdict(self)


@dataclasses.dataclass
class ExtensionStats:
    """Per-extension file count and byte total."""

    extension: str
    file_count: int
    byte_total: int

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return dataclasses.asdict(self)


@dataclasses.dataclass
class NotableFiles:
    """Categorised notable files discovered in the repository."""

    entrypoints: list[str] = dataclasses.field(default_factory=list)
    config_files: list[str] = dataclasses.field(default_factory=list)
    ci_configs: list[str] = dataclasses.field(default_factory=list)
    docker: list[str] = dataclasses.field(default_factory=list)
    iac: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return dataclasses.asdict(self)


@dataclasses.dataclass
class FileTreeInfo:
    """File tree statistics for the scanned repository."""

    total_files: int
    total_bytes: int
    max_depth: int
    extensions: list[ExtensionStats] = dataclasses.field(default_factory=list)
    notable_files: NotableFiles = dataclasses.field(default_factory=NotableFiles)

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return dataclasses.asdict(self)


@dataclasses.dataclass
class Dependency:
    """A single resolved dependency entry."""

    name: str
    version: str | None
    ecosystem: str
    dev: bool

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return dataclasses.asdict(self)


@dataclasses.dataclass
class ManifestInfo:
    """A discovered dependency manifest file."""

    path: str
    ecosystem: str

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return dataclasses.asdict(self)


@dataclasses.dataclass
class DependenciesInfo:
    """All dependency information extracted from the repository."""

    manifests: list[ManifestInfo] = dataclasses.field(default_factory=list)
    runtime: list[Dependency] = dataclasses.field(default_factory=list)
    dev: list[Dependency] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return dataclasses.asdict(self)


@dataclasses.dataclass
class TestingInfo:
    """Test framework and file detection results."""

    frameworks: list[str] = dataclasses.field(default_factory=list)
    test_directories: list[str] = dataclasses.field(default_factory=list)
    test_file_count: int = 0

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return dataclasses.asdict(self)


@dataclasses.dataclass
class RepoScanResult:
    """Top-level output document produced by a scan."""

    schema_version: str
    scanned_at: str  # ISO 8601 string
    repo: RepoInfo
    git: GitInfo
    languages: LanguageInfo
    frameworks: list[str]
    file_tree: FileTreeInfo
    dependencies: DependenciesInfo
    testing: TestingInfo
    meta: ScanMeta

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return dataclasses.asdict(self)
