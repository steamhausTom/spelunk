# TASK-001: Scaffold pyproject.toml and project packaging

**Status**: In Review
**Wave**: 1
**Assignee**: tc-backend-engineer
**Effort**: S — straightforward packaging config with one conditional dependency and dev extras; no logic to implement
**Base Branch**: main
**Dependencies**: None

## Description

Create the `pyproject.toml` that serves as the single source of package metadata, dependency declarations, and tool configuration for `spelunk`. This is the first file that must exist before any other task can run `pip install -e ".[dev]"` or invoke `mypy`/`pytest`.

The file must:
- Use PEP 517/518 with `[build-system]` pointing to `hatchling` or `setuptools>=64` as the build backend.
- Declare `[project]` metadata: `name = "spelunk"`, `version = "0.1.0"`, `requires-python = ">=3.10"`.
- Declare runtime dependencies in `[project.dependencies]`:
  - `click >= 8.0`
  - `pathspec >= 0.12`
  - `gitpython >= 3.1`
  - `tomli >= 2.0; python_version < "3.11"` (PEP 508 environment marker — NOT an optional extra)
- Declare `[project.optional-dependencies]` with a `dev` extra:
  - `pytest`
  - `pytest-cov`
  - `mypy`
  - `ruff`
- Declare `[project.scripts]` entry point: `spelunk = "spelunk.__main__:main"` (the CLI hook).
- Configure `[tool.mypy]` with `strict = true` applying to `spelunk/` only (exclude `tests/`).
- Configure `[tool.pytest.ini_options]` with `testpaths = ["tests"]` and a `slow` marker registered to suppress unknown-mark warnings.
- Create the stub `spelunk/` package directory with an empty `__init__.py` and an empty `tests/` directory with an empty `conftest.py` placeholder so the package is importable immediately after `pip install -e ".[dev]"`.

**tomli conditional dependency note**: The PEP 508 environment marker `; python_version < "3.11"` must appear in `[project.dependencies]`, not in `[project.optional-dependencies]`. This is an unconditional runtime dependency on older Pythons. See F6.

## Acceptance Criteria

- [x] [eng] Given `pyproject.toml` is present · When `pip install -e ".[dev]"` runs on Python 3.10 · Then the package installs without errors and `import spelunk` succeeds
- [x] [eng] Given `pyproject.toml` is present · When `pip install -e ".[dev]"` runs on Python 3.11+ · Then `tomli` is NOT installed and `import spelunk` succeeds
- [x] [eng] Given the installed package · When `python -c "import spelunk"` runs · Then no ImportError is raised
- [x] [eng] Given `pyproject.toml` · When `[project.dependencies]` is inspected · Then `tomli>=2.0; python_version < "3.11"` is present as a runtime dep with a PEP 508 marker
- [x] [eng] Given `pyproject.toml` · When `[tool.mypy]` is inspected · Then `strict = true` is set and `tests/` is listed under `exclude`
- [ ] [qa] Given the scaffolded repo · When `pytest --collect-only` runs · Then the test runner starts without configuration errors

## Notes / Risks

- Choose `hatchling` as the build backend for simplicity; it has no further configuration required for a src-layout-free package.
- Do NOT use `setup.cfg` or a legacy `setup.py` for this package — `pyproject.toml` only, per project constraints.
- The `spelunk/__init__.py` stub created here will be overwritten in TASK-007 when the public `scan()` API is implemented; just an empty file is sufficient now.
- The `tests/conftest.py` placeholder created here will be populated in TASK-009.
- Stub out `spelunk/__main__.py` as a minimal `if __name__ == "__main__": pass` so `python -m spelunk` does not error during Wave 2 development.
