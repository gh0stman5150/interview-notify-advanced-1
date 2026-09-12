# GitHub Copilot Instructions

This repository is a dependency-free Python 3.9+ application that watches local
IRC logs and sends Red or OPS interview notifications to ntfy. The root
[AGENTS.md](../AGENTS.md) is the authoritative source for repository structure,
architecture, coding standards, safety invariants, testing, documentation, and
change management.

Use these sections for common tasks:

- [Architecture and Workflows](../AGENTS.md#architecture-and-workflows) for CLI,
  parser, database, statistics, and GUI boundaries.
- [Non-Negotiable Invariants](../AGENTS.md#non-negotiable-invariants) for import
  safety, mode compatibility, rate limiting, HTTP, SQLite, privacy, telemetry,
  and authentication constraints.
- [Coding Conventions](../AGENTS.md#coding-conventions) for Python, error
  handling, logging, filesystem, database, and subprocess patterns. This
  repository has no Bash or PowerShell implementation conventions.
- [Change Workflow](../AGENTS.md#change-workflow) and
  [Validation Commands](../AGENTS.md#validation-commands) for tests, releases,
  and pull request expectations.
- [Documentation Standards](../AGENTS.md#documentation-standards) for keeping
  operational guidance synchronized with implementation.
- [Operational Considerations](../AGENTS.md#operational-considerations) and
  [Prohibited Practices](../AGENTS.md#prohibited-practices) for runtime limits,
  local user data, generated artifacts, and unsafe validation practices.

Before proposing or editing code, read the relevant implementation and tests,
then follow `AGENTS.md`. Do not duplicate its rules in this file; update the
source section and preserve these links when repository guidance changes.
