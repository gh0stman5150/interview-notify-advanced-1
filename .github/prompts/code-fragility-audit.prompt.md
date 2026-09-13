---
agent: 'agent'
title: 'Interview Notify Code Fragility Audit'
description: 'Audit interview-notify for brittle Python boundaries, concurrency and lifecycle defects, parser regressions, unsafe persistence, privacy risks, packaging drift, and missing tests; report before remediation.'
---

Act as a senior Python code auditor reviewing this repository for concrete
fragility: behavior likely to fail under maintenance, malformed input,
concurrency, filesystem churn, partial I/O failure, or packaging changes.

Read `AGENTS.md` in full before reviewing code. It is authoritative for the
architecture, safety invariants, validation commands, documentation duties, and
prohibited practices. Use the root Python modules, `tests/`, `pyproject.toml`,
and `README.md` as sources of truth. Ignore generated copies under `build/` and
`interview_notify.egg-info/`, except to note stale generated artifacts when
relevant.

Do not run `interview_notify.py`, `interview-notify`, or the GUI as an audit
command. They can start long-running watchers, access local user data, and send
startup telemetry. Do not contact live ntfy endpoints or inspect real IRC logs,
`~/.interview-notify-config.json`, notification logs, or
`~/.interview-notify-history.db`. Use static review, synthetic data, temporary
paths, mocks, and the existing `unittest` suite.

There is no configured formatter, linter, type checker, coverage tool, security
scanner, or CI workflow. Perform manual review where those tools would normally
help, clearly label the limits, and do not introduce tooling during the audit.

## Scope

Audit these authoritative surfaces and follow calls to the code that directly
controls each behavior:

- `interview_modes.py`: mode normalization, immutable event construction,
  case-insensitive bot matching, Red and OPS parsing, and the `orp` alias.
- `interview_notify.py`: argument normalization, watcher and parser threads,
  file truncation/replacement recovery, notification dispatch, critical-event
  rate-limit bypass, notification history, HTTP request construction and
  timeout, analytics isolation, and startup telemetry.
- `interview_database.py`: validation, schema setup, parameterized SQLite
  operations, transaction cleanup, concurrency, query correctness, and the
  explicit retention API.
- `interview_notify_gui.py`: configuration validation and persistence,
  canonical mode handling, subprocess argument construction, output-thread
  ownership, unexpected exits, and bounded terminate/kill/reap shutdown.
- `view_stats.py`: import safety, CLI behavior, database reads, error handling,
  and consistency with the analytics schema.
- `pyproject.toml`, `README.md`, and `tests/`: entry-point and version drift,
  claims that contradict runtime behavior, and gaps in critical-path coverage.
- `file_read_backwards/`: treat this as checked-in upstream compatibility code.
  Review only its integration boundary unless evidence points to a defect in
  the vendored implementation; do not move project-specific behavior into it.

DOM selectors, web routes, authentication flows, and third-party dependency
CVEs are not applicable unless the repository changes to include them. Do not
force findings into categories the implementation does not have.

## Audit Method

1. Build a concise map of the CLI, parser, notification, analytics, statistics,
   and GUI workflows. Distinguish pure parsing from network, filesystem,
   database, subprocess, and Tk side effects.
2. Read the nearest existing tests before judging behavior. A failing test is
   evidence; a missing test is a coverage gap, not proof of a defect.
3. Trace externally derived values from CLI arguments, GUI configuration, and
   IRC lines to their side effects. Check validation at the owning boundary.
4. Examine shared mutable state and blocking operations for ownership, locking,
   termination, bounded waits, stale-thread or stale-process interference, and
   failure cleanup.
5. Check public behavior across CLI choices, GUI choices/defaults, parser mode
   defaults, entry points, version constants, tests, and README examples.
6. Group symptoms under their shared root cause. Prefer the smallest
   repository-aligned correction over rewrites or new abstractions.

## Required Fragility Checks

### Architecture and maintainability

- Keep mode-specific recognition in `interview_modes.py`; flag duplicated or
  diverging parsing in CLI, GUI, analytics, or reporting code.
- Identify globals, broad exception handling, implicit initialization order,
  hidden coupling, unreachable branches, duplicate implementations, and stale
  compatibility paths only when they create a concrete maintenance risk.
- Verify every CLI module remains import-safe: no argument parsing, monitoring,
  network request, user-file creation, or GUI startup during import.
- Check that `main()` owns runtime setup and execution remains behind an
  `if __name__ == '__main__'` guard.

### Parsing and compatibility

- Reason against representative synthetic IRC lines, malformed input, casing
  differences, special-character nicknames, optional bot-nick checks, custom
  bot lists, Red, canonical `ops`, and legacy `orp`.
- Preserve Red's `Gatekeeper` default and OPS's `Hermes` default unless a user
  supplies bot nicks.
- Distinguish parser false positives, false negatives, and analytics-only
  mismatches; identify the exact input that exposes a problem.

### Concurrency, lifecycle, and failure isolation

- Review scanner/parser restart, empty and unreadable directories, temporary
  file disappearance, truncation, replacement, rotation, and switching to the
  newest file.
- Check notification reservations under overlapping sends and failures.
  `your_interview`, disconnect, and kick must always bypass rate limiting.
- Verify notification-log and analytics failures cannot terminate parsing or
  suppress an otherwise valid notification.
- Review GUI start/stop/restart, late output-reader completion, unexpected
  child exit, configuration write failure, and terminate/wait/kill/reap order.
- Flag unbounded resource growth, duplicate processing, replay after restart,
  or shutdown hangs only when supported by a reachable code path.

### Network, privacy, and security

- Confirm notification transport uses standard-library HTTP `POST`, safe URL
  construction, and a bounded timeout. Do not claim retry or ntfy
  authentication support.
- Treat IRC logs, nicknames, ntfy topics, notification logs, GUI configuration,
  analytics databases, and telemetry identifiers as user data. Flag leakage in
  logs, exceptions, tests, examples, or subprocess output.
- Preserve and verify documentation of startup telemetry: a stable
  SHA-256-derived nickname identifier, canonical mode, and version sent to the
  documented ntfy telemetry topic, with no current opt-out.
- Inspect for embedded secrets or unsafe subprocess construction. Do not propose
  authentication, encryption, or telemetry controls merely to satisfy the
  audit; record absent features as known gaps when appropriate.

### SQLite and filesystem integrity

- Confirm log- or CLI-derived SQLite values are bounded, validated, and passed
  through parameterized placeholders.
- Keep writes within `InterviewDatabase.get_connection()` and verify commit,
  rollback, WAL setup, and connection cleanup on success and failure.
- Check repeatable schema initialization, concurrent access, query aggregation,
  timestamp handling, unavailable or malformed databases, and retention
  boundaries using temporary databases only.
- Do not describe `clear_old_data(days=90)` as automatic retention unless a
  tested caller exists. Do not broaden its deletion criteria as a casual fix.
- Check explicit encodings, `pathlib.Path` usage, atomicity expectations, and
  failure behavior for configuration and notification-log files.

### Tests, packaging, and documentation drift

- Identify missing tests by naming the exact behavior and assertion that would
  falsify it. Prefer deterministic `unittest`, `tempfile`, and `unittest.mock`
  coverage; do not add sleeps to hide races.
- Check versions across `pyproject.toml`, CLI and GUI constants, documented
  output, and assertions. Check all three console entry points against their
  actual `main()` functions.
- Compare README claims with implementation for installation, modes, defaults,
  paths, telemetry, HTTP behavior, analytics, retention, authentication,
  retries, and directory-watcher behavior.
- Treat missing CI, coverage, formatting, linting, typing, dedicated database
  tests, or dedicated GUI integration tests as explicit gaps, not evidence that
  an undocumented tool or check exists.

## Validation

Run the narrowest relevant existing test module when a suspected defect can be
checked without changing files. Then run the full suite if needed:

```powershell
py -3 -m unittest tests.test_interview_modes
py -3 -m unittest discover -s tests
```

Do not build a wheel unless packaging metadata or entry points are under direct
investigation. Never use live services or default user-data paths. Record the
exact command, result, and any environmental limitation; do not claim checks
that did not run.

## Findings Standard

Report findings first, ordered by severity. For each finding include:

- severity (`critical`, `high`, `medium`, or `low`) and confidence;
- dimension, root file, and symbol or precise location;
- triggering input, state, race, failure, or maintenance change;
- user-visible and operational consequence;
- evidence from code, tests, or command output;
- existing coverage or the exact missing regression test;
- smallest repository-aligned remediation;
- privacy, telemetry, SQLite, platform, or compatibility implications.

Do not inflate style preferences, speculative threats, intentionally documented
limitations, or absent optional features into defects. Keep verified defects,
test gaps, documentation drift, and known operational limitations separate. If
no defects are found, say so and state the residual risks.

## Stop Before Remediation

Complete and present the audit before editing source, tests, packaging, or
documentation. Wait for explicit approval before remediation. After approval,
fix one root cause at a time, add a focused regression test, run that test, and
then run the full suite. Build a wheel only for packaging or entry-point
changes.

## Deliverable

Return:

1. a short workflow and state-ownership map;
2. prioritized findings with evidence;
3. separate test, documentation, tooling, and operational gaps;
4. a staged minimal remediation plan, proposed but not executed;
5. validation commands run and their results.
