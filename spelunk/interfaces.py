"""Formal structural contracts for spelunk analysers.

This module defines the Analyser Protocol and the ScanInputs / AnalyserOutput
envelope types. All analyser modules import from here; this module must never
import from spelunk.scanner or any analyser module.

Architect decision (F1): use typing.Protocol instead of ABC or duck-typing
conventions.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from spelunk.models import ScanError


@dataclasses.dataclass
class ScanInputs:
    """Immutable context passed to every analyser call.

    Analysers must not re-walk the filesystem — they receive the pre-filtered
    path list from utils.walk_repo() via this object.

    Fields may be extended in future tasks without breaking callers.
    """

    root: Path  # resolved absolute path to the repo root
    file_paths: list[Path]  # pre-walked, non-gitignored paths.
    # IMPORTANT: binary files and large files (>10 MB) ARE included so that
    # file_tree.py can record their extensions and counts. Every analyser that
    # reads file content MUST guard with:
    #   - is_binary(path) before reading content
    #   - path.stat().st_size <= LARGE_FILE_THRESHOLD_BYTES before reading content


@dataclasses.dataclass
class AnalyserOutput:
    """Envelope returned by every analyser.

    The orchestrator in scanner.py reads the payload and assigns it to the
    correct field on RepoScanResult. It also merges errors and warnings into
    the top-level ScanMeta.

    payload is typed Any because each analyser returns a different concrete
    type (GitInfo, FileTreeInfo, etc.). The orchestrator knows the type.
    """

    payload: Any  # typed result — e.g. GitInfo, FileTreeInfo
    errors: list[ScanError]  # per-item errors collected during analysis
    warnings: list[str]  # non-fatal notices
    source: str  # matches the error source string, e.g. "analysers.git_meta"


@runtime_checkable
class Analyser(Protocol):
    """Structural contract every analyser must satisfy.

    An analyser is any callable object that:
    - exposes a name: str attribute (used as the source string in error records)
    - accepts (root: Path, ctx: ScanInputs) and returns AnalyserOutput

    @runtime_checkable enables isinstance() checks in tests. mypy is the
    authoritative type checker — runtime checks only verify attribute presence,
    not type correctness.
    """

    name: str

    def __call__(self, root: Path, ctx: ScanInputs) -> AnalyserOutput:
        ...
