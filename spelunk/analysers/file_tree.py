"""File tree analyser for spelunk.

Computes extension statistics, totals, max depth, and notable file
categorisation from the pre-walked ctx.file_paths list. Does not re-walk
the filesystem.

Notable file categories
-----------------------
entrypoints   — well-known application entry-point filenames
config_files  — project configuration files
ci_configs    — continuous integration pipeline definitions
docker        — Dockerfile variants and docker-compose files
iac           — infrastructure-as-code files (.tf, Pulumi, CDK, CloudFormation)

A single file may appear in more than one category (e.g. docker-compose.yml
appears in both config_files and docker).
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

from spelunk.interfaces import AnalyserOutput, ScanInputs
from spelunk.models import ExtensionStats, FileTreeInfo, NotableFiles, ScanError

# ---------------------------------------------------------------------------
# Notable file pattern tables (all filename comparisons are lower-cased)
# ---------------------------------------------------------------------------

_ENTRYPOINT_NAMES: frozenset[str] = frozenset(
    {
        "main.py",
        "index.js",
        "index.ts",
        "app.py",
        "app.js",
        "app.ts",
        "server.py",
        "server.js",
        "server.ts",
        "manage.py",
    }
)

_CONFIG_NAMES: frozenset[str] = frozenset(
    {
        ".env",
        ".env.example",
        "docker-compose.yml",
        "docker-compose.yaml",
        "makefile",
        ".editorconfig",
        ".prettierrc",
        ".eslintrc",
        ".eslintrc.js",
        ".eslintrc.json",
        "babel.config.js",
        "webpack.config.js",
    }
)

# CI config exact filename matches (lowercased)
_CI_NAMES: frozenset[str] = frozenset(
    {
        ".gitlab-ci.yml",
        "jenkinsfile",
        "azure-pipelines.yml",
        ".travis.yml",
    }
)

# CI config exact relative-path substrings (lowercased)
_CI_PATH_SUBSTRINGS: tuple[str, ...] = (
    ".github/workflows/",
    ".circleci/config.yml",
)

# Docker exact filenames (lowercased)
_DOCKER_NAMES: frozenset[str] = frozenset({"dockerfile"})

# IAC exact filenames (lowercased)
_IAC_NAMES: frozenset[str] = frozenset(
    {
        "pulumi.yaml",
        "pulumi.yml",
        "cdk.json",
        "cloudformation.yml",
        "cloudformation.yaml",
    }
)

# IAC relative-path substrings (lowercased)
_IAC_PATH_SUBSTRINGS: tuple[str, ...] = ("/cloudformation/",)


# ---------------------------------------------------------------------------
# Analyser
# ---------------------------------------------------------------------------


class _FileTreeAnalyser:
    """Stateless callable that satisfies the Analyser Protocol."""

    name: str = "analysers.file_tree"

    def __call__(self, root: Path, ctx: ScanInputs) -> AnalyserOutput:
        errors: list[ScanError] = []
        warnings: list[str] = []

        try:
            result = self._analyse(root, ctx, errors, warnings)
        except Exception as exc:
            errors.append(ScanError(source=self.name, message=str(exc)))
            result = FileTreeInfo(
                total_files=0,
                total_bytes=0,
                max_depth=0,
            )

        return AnalyserOutput(
            payload=result,
            errors=errors,
            warnings=warnings,
            source=self.name,
        )

    # ------------------------------------------------------------------
    # Internal implementation
    # ------------------------------------------------------------------

    def _analyse(
        self,
        root: Path,
        ctx: ScanInputs,
        errors: list[ScanError],
        warnings: list[str],
    ) -> FileTreeInfo:
        # Per-extension accumulators: {extension: [file_count, byte_total]}
        ext_accum: dict[str, list[int]] = {}

        total_bytes = 0
        max_depth = 0

        notable = NotableFiles()

        for path in ctx.file_paths:
            # ---- size -------------------------------------------------------
            try:
                size = path.stat().st_size
            except OSError as exc:
                errors.append(
                    ScanError(source=self.name, message=f"stat failed for {path}: {exc}")
                )
                size = 0

            total_bytes += size

            # ---- extension stats --------------------------------------------
            ext = path.suffix.lower() or "(no extension)"
            if ext not in ext_accum:
                ext_accum[ext] = [0, 0]
            ext_accum[ext][0] += 1
            ext_accum[ext][1] += size

            # ---- depth ------------------------------------------------------
            try:
                parts = path.relative_to(root).parts
                # depth = number of directory components = parts - 1 (filename)
                depth = len(parts) - 1
                if depth > max_depth:
                    max_depth = depth
            except ValueError:
                # path not relative to root — should not happen in normal usage
                pass

            # ---- notable files ----------------------------------------------
            # Use POSIX-style relative path for substring matching
            try:
                rel_posix = path.relative_to(root).as_posix()
            except ValueError:
                rel_posix = path.name

            self._categorise(path, rel_posix, notable)

        # Build extension list (sorted for determinism)
        extensions = [
            ExtensionStats(extension=ext, file_count=counts[0], byte_total=counts[1])
            for ext, counts in sorted(ext_accum.items())
        ]

        return FileTreeInfo(
            total_files=len(ctx.file_paths),
            total_bytes=total_bytes,
            max_depth=max_depth,
            extensions=extensions,
            notable_files=notable,
        )

    def _categorise(self, path: Path, rel_posix: str, notable: NotableFiles) -> None:
        """Classify a file into zero or more notable file categories.

        rel_posix is the POSIX-style path relative to root (e.g. '.github/workflows/ci.yml').
        """
        name_lower = path.name.lower()
        rel_lower = rel_posix.lower()

        # ---- entrypoints ----------------------------------------------------
        if name_lower in _ENTRYPOINT_NAMES:
            notable.entrypoints.append(rel_posix)

        # ---- config_files ---------------------------------------------------
        if name_lower in _CONFIG_NAMES:
            notable.config_files.append(rel_posix)

        # ---- ci_configs -----------------------------------------------------
        ci_match = False
        if name_lower in _CI_NAMES:
            ci_match = True
        if not ci_match:
            for substr in _CI_PATH_SUBSTRINGS:
                if substr in rel_lower:
                    ci_match = True
                    break
        if ci_match:
            notable.ci_configs.append(rel_posix)

        # ---- docker ---------------------------------------------------------
        docker_match = False
        if name_lower in _DOCKER_NAMES:
            # bare "Dockerfile"
            docker_match = True
        elif fnmatch.fnmatch(name_lower, "dockerfile.*"):
            # Dockerfile.production, Dockerfile.dev, etc.
            docker_match = True
        elif fnmatch.fnmatch(name_lower, "docker-compose*.yml") or fnmatch.fnmatch(
            name_lower, "docker-compose*.yaml"
        ):
            docker_match = True
        if docker_match:
            notable.docker.append(rel_posix)

        # ---- iac ------------------------------------------------------------
        iac_match = False
        if path.suffix.lower() == ".tf":
            iac_match = True
        elif name_lower in _IAC_NAMES:
            iac_match = True
        else:
            for substr in _IAC_PATH_SUBSTRINGS:
                if substr in rel_lower:
                    iac_match = True
                    break
        if iac_match:
            notable.iac.append(rel_posix)


# Module-level singleton — satisfies the Analyser Protocol structurally.
file_tree = _FileTreeAnalyser()
