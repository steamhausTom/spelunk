"""Tests for spelunk/interfaces.py — TASK-004."""

from __future__ import annotations

import ast
import pathlib
from pathlib import Path


def test_no_scanner_import() -> None:
    """interfaces.py must not import from spelunk.scanner."""
    source = pathlib.Path(__file__).parent.parent / "spelunk" / "interfaces.py"
    tree = ast.parse(source.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "scanner" not in alias.name, f"scanner import found: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert "scanner" not in node.module, f"scanner import found: {node.module}"


def test_analyser_output_error_to_dict() -> None:
    """AnalyserOutput errors must have dicts with source and message keys."""
    from spelunk.interfaces import AnalyserOutput
    from spelunk.models import ScanError

    output = AnalyserOutput(
        payload={"some": "data"},
        errors=[ScanError(source="analysers.git_meta", message="oops")],
        warnings=[],
        source="analysers.git_meta",
    )
    assert len(output.errors) == 1
    err_dict = output.errors[0].to_dict()
    assert "source" in err_dict
    assert "message" in err_dict


def test_scan_inputs_has_root_and_file_paths() -> None:
    """ScanInputs must have root (Path) and file_paths (list[Path]) fields."""
    from spelunk.interfaces import ScanInputs

    root = Path("/tmp/repo")
    inputs = ScanInputs(root=root, file_paths=[root / "main.py"])
    assert inputs.root == root
    assert inputs.file_paths == [root / "main.py"]


def test_analyser_protocol_valid_callable_passes() -> None:
    """A callable with the correct signature and name attr satisfies Analyser."""
    from spelunk.interfaces import Analyser, AnalyserOutput, ScanInputs

    class MyAnalyser:
        name = "my_analyser"

        def __call__(self, root: Path, ctx: ScanInputs) -> AnalyserOutput:
            return AnalyserOutput(payload=None, errors=[], warnings=[], source=self.name)

    obj = MyAnalyser()
    assert isinstance(obj, Analyser)


def test_analyser_protocol_missing_name_fails_isinstance() -> None:
    """An object missing the name attribute must fail isinstance check against Analyser."""
    from spelunk.interfaces import Analyser, AnalyserOutput, ScanInputs

    class BadAnalyser:
        def __call__(self, root: Path, ctx: ScanInputs) -> AnalyserOutput:
            return AnalyserOutput(payload=None, errors=[], warnings=[], source="bad")

    obj = BadAnalyser()
    assert not isinstance(obj, Analyser)
