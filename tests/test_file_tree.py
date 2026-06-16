"""Tests for spelunk/analysers/file_tree.py — TASK-006.

Each test is traceable to a [eng] acceptance criterion in tasks/TASK-006.md.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: bytes | str = "x") -> None:
    """Create parent dirs and write a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content)


def _make_ctx(root: Path, paths: list[Path]) -> object:
    """Build a ScanInputs from an explicit list of paths."""
    from spelunk.interfaces import ScanInputs

    return ScanInputs(root=root, file_paths=paths)


def _run(root: Path, paths: list[Path]) -> object:
    """Call the file_tree analyser and return the AnalyserOutput."""
    from spelunk.analysers.file_tree import file_tree

    ctx = _make_ctx(root, paths)
    return file_tree(root, ctx)


def _ext_map(output: object) -> dict[str, object]:
    """Return a dict of extension -> ExtensionStats from the payload."""
    payload = output.payload  # type: ignore[attr-defined]
    return {e.extension: e for e in payload.extensions}


# ---------------------------------------------------------------------------
# AC1: Extension stats — file counts per extension
# ---------------------------------------------------------------------------


def test_extension_stats_file_counts(tmp_path: Path) -> None:
    """AC1: 5 .py + 3 .js files → extensions has correct file_count per ext."""
    py_files = [tmp_path / f"mod{i}.py" for i in range(5)]
    js_files = [tmp_path / f"script{i}.js" for i in range(3)]
    all_files = py_files + js_files
    for f in all_files:
        _write(f)

    output = _run(tmp_path, all_files)
    ext = _ext_map(output)

    assert ".py" in ext, "Expected .py in extensions"
    assert ext[".py"].file_count == 5
    assert ".js" in ext, "Expected .js in extensions"
    assert ext[".js"].file_count == 3


def test_extension_byte_totals(tmp_path: Path) -> None:
    """Extension byte_total accumulates correctly for all files of that extension."""
    f1 = tmp_path / "a.py"
    f2 = tmp_path / "b.py"
    _write(f1, "x" * 100)
    _write(f2, "y" * 200)

    output = _run(tmp_path, [f1, f2])
    ext = _ext_map(output)

    assert ".py" in ext
    # byte_total should be at least 300 (exact if no encoding overhead)
    assert ext[".py"].byte_total >= 300


def test_extension_no_suffix(tmp_path: Path) -> None:
    """Files with no extension are grouped under '(no extension)'."""
    f = tmp_path / "Makefile"
    _write(f)

    output = _run(tmp_path, [f])
    ext = _ext_map(output)

    assert "(no extension)" in ext
    assert ext["(no extension)"].file_count == 1


def test_large_file_counted_in_extension_stats(tmp_path: Path) -> None:
    """AC4: A file > 10 MB appears in total_files and its extension is in extensions."""
    from spelunk.utils import LARGE_FILE_THRESHOLD_BYTES

    big = tmp_path / "data.bin"
    # Write just over 10 MB
    _write(big, b"x" * (LARGE_FILE_THRESHOLD_BYTES + 1))

    output = _run(tmp_path, [big])
    payload = output.payload  # type: ignore[attr-defined]

    assert payload.total_files == 1, "Large file must be counted in total_files"
    ext = _ext_map(output)
    assert ".bin" in ext, "Large file extension must appear in extensions"
    assert ext[".bin"].file_count == 1


# ---------------------------------------------------------------------------
# AC2: Notable files — entrypoints
# ---------------------------------------------------------------------------


def test_notable_entrypoints_main_py(tmp_path: Path) -> None:
    """AC2: main.py at repo root → notable_files.entrypoints contains its path."""
    f = tmp_path / "main.py"
    _write(f)

    output = _run(tmp_path, [f])
    payload = output.payload  # type: ignore[attr-defined]

    assert "main.py" in payload.notable_files.entrypoints


def test_notable_entrypoints_all_patterns(tmp_path: Path) -> None:
    """All documented entrypoint filenames are detected."""
    names = [
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
    ]
    files = [tmp_path / n for n in names]
    for f in files:
        _write(f)

    output = _run(tmp_path, files)
    payload = output.payload  # type: ignore[attr-defined]

    for name in names:
        assert name in payload.notable_files.entrypoints, f"Expected {name} in entrypoints"


def test_notable_entrypoints_nested(tmp_path: Path) -> None:
    """main.py nested inside a subdirectory is also detected."""
    f = tmp_path / "src" / "main.py"
    _write(f)

    output = _run(tmp_path, [f])
    payload = output.payload  # type: ignore[attr-defined]

    relative = str(f.relative_to(tmp_path))
    assert relative in payload.notable_files.entrypoints


# ---------------------------------------------------------------------------
# AC3: Notable files — ci_configs
# ---------------------------------------------------------------------------


def test_notable_ci_configs_github_workflows(tmp_path: Path) -> None:
    """AC3: .github/workflows/ci.yml → notable_files.ci_configs contains it."""
    f = tmp_path / ".github" / "workflows" / "ci.yml"
    _write(f)

    output = _run(tmp_path, [f])
    payload = output.payload  # type: ignore[attr-defined]

    relative = str(f.relative_to(tmp_path))
    assert relative in payload.notable_files.ci_configs


def test_notable_ci_configs_all_patterns(tmp_path: Path) -> None:
    """All documented CI config filenames / patterns are detected."""
    files_and_relatives: list[tuple[Path, str]] = [
        (tmp_path / ".github" / "workflows" / "build.yml", ".github/workflows/build.yml"),
        (tmp_path / ".gitlab-ci.yml", ".gitlab-ci.yml"),
        (tmp_path / "Jenkinsfile", "Jenkinsfile"),
        (tmp_path / ".circleci" / "config.yml", ".circleci/config.yml"),
        (tmp_path / "azure-pipelines.yml", "azure-pipelines.yml"),
        (tmp_path / ".travis.yml", ".travis.yml"),
    ]
    paths = [p for p, _ in files_and_relatives]
    for f in paths:
        _write(f)

    output = _run(tmp_path, paths)
    payload = output.payload  # type: ignore[attr-defined]

    for _, relative in files_and_relatives:
        assert relative in payload.notable_files.ci_configs, (
            f"Expected {relative} in ci_configs"
        )


# ---------------------------------------------------------------------------
# AC4: Large file handling (also covered by test_large_file_counted_in_extension_stats)
# ---------------------------------------------------------------------------


def test_large_file_total_files(tmp_path: Path) -> None:
    """AC4 (second angle): total_files includes large files."""
    from spelunk.utils import LARGE_FILE_THRESHOLD_BYTES

    big = tmp_path / "huge.dat"
    small = tmp_path / "small.py"
    _write(big, b"x" * (LARGE_FILE_THRESHOLD_BYTES + 1))
    _write(small)

    output = _run(tmp_path, [big, small])
    payload = output.payload  # type: ignore[attr-defined]

    assert payload.total_files == 2


# ---------------------------------------------------------------------------
# AC5: max_depth
# ---------------------------------------------------------------------------


def test_max_depth_four_levels(tmp_path: Path) -> None:
    """AC5: file nested 4 directories deep → max_depth == 4."""
    # root/a/b/c/d/file.txt → depth 4
    f = tmp_path / "a" / "b" / "c" / "d" / "file.txt"
    _write(f)

    output = _run(tmp_path, [f])
    payload = output.payload  # type: ignore[attr-defined]

    assert payload.max_depth == 4


def test_max_depth_root_level(tmp_path: Path) -> None:
    """A file directly in the root has depth 0."""
    f = tmp_path / "file.txt"
    _write(f)

    output = _run(tmp_path, [f])
    payload = output.payload  # type: ignore[attr-defined]

    assert payload.max_depth == 0


def test_max_depth_empty(tmp_path: Path) -> None:
    """Empty file list produces max_depth == 0."""
    output = _run(tmp_path, [])
    payload = output.payload  # type: ignore[attr-defined]

    assert payload.max_depth == 0


def test_max_depth_mixed(tmp_path: Path) -> None:
    """max_depth reflects the deepest file across a mixed-depth set."""
    shallow = tmp_path / "readme.md"
    deep = tmp_path / "a" / "b" / "c" / "deep.py"
    _write(shallow)
    _write(deep)

    output = _run(tmp_path, [shallow, deep])
    payload = output.payload  # type: ignore[attr-defined]

    assert payload.max_depth == 3


# ---------------------------------------------------------------------------
# Notable files — docker category
# ---------------------------------------------------------------------------


def test_notable_docker_dockerfile(tmp_path: Path) -> None:
    """Dockerfile is detected in the docker category."""
    f = tmp_path / "Dockerfile"
    _write(f)

    output = _run(tmp_path, [f])
    payload = output.payload  # type: ignore[attr-defined]

    assert "Dockerfile" in payload.notable_files.docker


def test_notable_docker_compose_variants(tmp_path: Path) -> None:
    """docker-compose.yml and docker-compose.yaml are in docker category."""
    f_yml = tmp_path / "docker-compose.yml"
    f_yaml = tmp_path / "docker-compose.yaml"
    _write(f_yml)
    _write(f_yaml)

    output = _run(tmp_path, [f_yml, f_yaml])
    payload = output.payload  # type: ignore[attr-defined]

    assert "docker-compose.yml" in payload.notable_files.docker
    assert "docker-compose.yaml" in payload.notable_files.docker


def test_notable_dockerfile_with_variant(tmp_path: Path) -> None:
    """Dockerfile.production (Dockerfile.* pattern) is in docker category."""
    f = tmp_path / "Dockerfile.production"
    _write(f)

    output = _run(tmp_path, [f])
    payload = output.payload  # type: ignore[attr-defined]

    assert "Dockerfile.production" in payload.notable_files.docker


# ---------------------------------------------------------------------------
# Notable files — config_files category
# ---------------------------------------------------------------------------


def test_notable_config_files_dotenv(tmp_path: Path) -> None:
    """.env is in config_files."""
    f = tmp_path / ".env"
    _write(f)

    output = _run(tmp_path, [f])
    payload = output.payload  # type: ignore[attr-defined]

    assert ".env" in payload.notable_files.config_files


def test_notable_config_files_makefile(tmp_path: Path) -> None:
    """Makefile is in config_files."""
    f = tmp_path / "Makefile"
    _write(f)

    output = _run(tmp_path, [f])
    payload = output.payload  # type: ignore[attr-defined]

    assert "Makefile" in payload.notable_files.config_files


# ---------------------------------------------------------------------------
# Multi-category: docker-compose.yml in both config_files and docker
# ---------------------------------------------------------------------------


def test_docker_compose_in_both_categories(tmp_path: Path) -> None:
    """docker-compose.yml must appear in both config_files and docker."""
    f = tmp_path / "docker-compose.yml"
    _write(f)

    output = _run(tmp_path, [f])
    payload = output.payload  # type: ignore[attr-defined]

    assert "docker-compose.yml" in payload.notable_files.config_files, (
        "docker-compose.yml must be in config_files"
    )
    assert "docker-compose.yml" in payload.notable_files.docker, (
        "docker-compose.yml must be in docker"
    )


# ---------------------------------------------------------------------------
# Notable files — iac category
# ---------------------------------------------------------------------------


def test_notable_iac_terraform(tmp_path: Path) -> None:
    """Files with .tf extension are in the iac category."""
    f = tmp_path / "main.tf"
    _write(f)

    output = _run(tmp_path, [f])
    payload = output.payload  # type: ignore[attr-defined]

    assert "main.tf" in payload.notable_files.iac


def test_notable_iac_cdk_json(tmp_path: Path) -> None:
    """cdk.json is in the iac category."""
    f = tmp_path / "cdk.json"
    _write(f)

    output = _run(tmp_path, [f])
    payload = output.payload  # type: ignore[attr-defined]

    assert "cdk.json" in payload.notable_files.iac


def test_notable_iac_pulumi(tmp_path: Path) -> None:
    """Pulumi.yaml and Pulumi.yml are in the iac category."""
    f_yaml = tmp_path / "Pulumi.yaml"
    f_yml = tmp_path / "Pulumi.yml"
    _write(f_yaml)
    _write(f_yml)

    output = _run(tmp_path, [f_yaml, f_yml])
    payload = output.payload  # type: ignore[attr-defined]

    assert "Pulumi.yaml" in payload.notable_files.iac
    assert "Pulumi.yml" in payload.notable_files.iac


def test_notable_iac_cloudformation_path(tmp_path: Path) -> None:
    """Files with /cloudformation/ in relative path are in iac category."""
    f = tmp_path / "infra" / "cloudformation" / "stack.yml"
    _write(f)

    output = _run(tmp_path, [f])
    payload = output.payload  # type: ignore[attr-defined]

    relative = str(f.relative_to(tmp_path))
    assert relative in payload.notable_files.iac


# ---------------------------------------------------------------------------
# Totals
# ---------------------------------------------------------------------------


def test_total_files_count(tmp_path: Path) -> None:
    """total_files equals the number of paths in ctx.file_paths."""
    files = [tmp_path / f"f{i}.txt" for i in range(7)]
    for f in files:
        _write(f)

    output = _run(tmp_path, files)
    payload = output.payload  # type: ignore[attr-defined]

    assert payload.total_files == 7


def test_total_bytes_sum(tmp_path: Path) -> None:
    """total_bytes is the sum of file sizes."""
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    _write(f1, "a" * 50)
    _write(f2, "b" * 100)

    output = _run(tmp_path, [f1, f2])
    payload = output.payload  # type: ignore[attr-defined]

    assert payload.total_bytes == 150


# ---------------------------------------------------------------------------
# Analyser protocol compliance
# ---------------------------------------------------------------------------


def test_analyser_protocol_compliance() -> None:
    """file_tree satisfies the Analyser Protocol (isinstance check)."""
    from spelunk.analysers.file_tree import file_tree
    from spelunk.interfaces import Analyser

    assert isinstance(file_tree, Analyser)


def test_analyser_has_name() -> None:
    """file_tree.name is 'analysers.file_tree'."""
    from spelunk.analysers.file_tree import file_tree

    assert file_tree.name == "analysers.file_tree"


def test_output_is_analyser_output() -> None:
    """The return value is an AnalyserOutput."""
    from spelunk.analysers.file_tree import file_tree
    from spelunk.interfaces import AnalyserOutput, ScanInputs

    ctx = ScanInputs(root=Path("/tmp"), file_paths=[])
    result = file_tree(Path("/tmp"), ctx)
    assert isinstance(result, AnalyserOutput)


# ---------------------------------------------------------------------------
# AC6: mypy --strict passes
# ---------------------------------------------------------------------------


def test_mypy_strict() -> None:
    """AC6: mypy --strict reports zero errors on file_tree.py."""
    import os

    repo_root = Path(__file__).parent.parent
    target = repo_root / "spelunk" / "analysers" / "file_tree.py"

    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", str(target)],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        env={**os.environ, "PYTHONPATH": str(repo_root)},
    )
    assert result.returncode == 0, (
        f"mypy --strict reported errors:\n{result.stdout}\n{result.stderr}"
    )
