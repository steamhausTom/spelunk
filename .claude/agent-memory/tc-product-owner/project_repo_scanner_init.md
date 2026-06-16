---
name: project-repo-scanner-init
description: Initial build of repo-scanner is captured in BRIEF-001; two open architectural questions remain before implementation can begin
metadata:
  type: project
---

BRIEF-001 covers the full greenfield build of `repo-scanner` — a Python CLI/library for static codebase analysis emitting a versioned JSON document.

**Why:** This is a non-trivial multi-module project with an externally-consumed output schema and an analyser interface that will gate all future extensions. Architectural review was required before implementation.

**How to apply:** Any new brief for this project that touches the analyser interface, schema versioning, or dependency manifest parsing should reference BRIEF-001 as the baseline. The two open questions (analyser Protocol vs duck-typing, framework detection matrix) must be resolved by `tc-principal-architect` before BRIEF-001 work can be planned.

Open questions at time of brief:
1. Analyser interface shape — `Protocol` / ABC vs duck-typed convention (affects `scanner.py` and `mypy --strict` compliance)
2. Framework detection matrix — is the initial list bounded to FastAPI + React, or is a fuller matrix expected?

Related: [[project-repo-scanner-schema]]
