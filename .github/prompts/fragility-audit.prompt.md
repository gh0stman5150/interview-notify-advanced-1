---
agent: 'agent'
title: 'Notifier Lifecycle Fragility Audit'
description: 'Audit process restarts, GUI child-process lifecycle, log-file churn, and persistent-state recovery in interview-notify, then report findings before making focused fixes.'
---

Act as a senior Python reliability engineer auditing this repository for failures
caused by notifier restarts, GUI start/stop cycles, parser-thread failure, log-file
truncation or replacement, and partial persistent-state failure.

Read `AGENTS.md` in full before reviewing code. It is authoritative for the
architecture, safety invariants, validation commands, and prohibited practices.
Use the root Python modules and `tests/` as implementation sources of truth.
Ignore generated copies under `build/` and `interview_notify.egg-info/`.

Do not run `interview_notify.py`, the `interview-notify` entry point, or the GUI
during the audit. Those paths can start long-running threads, access user data,
and send startup telemetry. Do not use live ntfy endpoints, real IRC logs, the
user's GUI configuration, or the default analytics database. Use code reading,
temporary paths, mocks, and the existing `unittest` suite.

## Goal

Find concrete lifecycle and recovery defects without changing the repository's
architecture or adding service managers, containers, shell wrappers,
authentication, telemetry controls, or automatic retention. Distinguish a
verified defect from an intentional limitation or an untested risk.

## 1. Trace the real lifecycle

Inspect the controlling code paths in:

- `interview_notify.py`: `main`, `log_scan`, `spawn_parser`, `log_parse`,
  `tail`, notification rate limiting, notification logging, telemetry, and
  analytics initialization.
- `interview_notify_gui.py`: configuration load/save, command construction,
  subprocess start, output-reader ownership, unexpected exits, stop escalation,
  and window close.
- `interview_database.py`: initialization, connection handling, transactions,
  schema setup, concurrent access, malformed or unavailable databases, and
  behavior after process restart.
- `interview_modes.py`: only where parser behavior affects replay, duplicate
  handling, or recovery.

Build a concise lifecycle map for direct CLI monitoring and GUI-managed
monitoring. Identify which state is process-local, which is stored in files or
SQLite, and which resources are owned by each scanner, parser thread, or child
process.

## 2. Audit restart and recovery scenarios

Verify each scenario against code and existing tests rather than assuming it
works:

- A direct file watcher or directory watcher loses its parser thread.
- A watched file temporarily disappears, becomes unreadable, is truncated, or
  is replaced/rotated while monitoring continues.
- A directory is empty, later gains a log, or changes which file has the newest
  modification time.
- The notifier process restarts while the last existing log line is still a
  notification or analytics event. Determine whether replay can create a
  duplicate notification, duplicate database row, or missed event; do not
  assume persistent cursor semantics that are not implemented.
- Multiple configured paths resolve to the same file, or scanners switch onto
  the same file, causing duplicate processing.
- A notification request fails, overlaps another send of the same type, or the
  process restarts and loses its in-memory rate-limit history. Preserve the
  rule that `your_interview`, disconnect, and kick bypass rate limiting.
- Notification-log or SQLite writes fail after monitoring has started. Confirm
  failures do not kill parsing or suppress an otherwise valid notification.
- The GUI starts, stops, and starts monitoring again; an old output thread
  finishes late; the child exits unexpectedly; or termination times out.
  Preserve terminate, bounded wait, kill, and reap behavior.
- The GUI configuration file is absent, malformed, partially valid, or cannot
  be written. Confirm failed loads do not leave a partially applied config.
- Importing any CLI module remains free of monitoring, network, argument
  parsing, and user-file side effects.

For blocking loops and shutdown paths, check ownership and liveness explicitly:
who signals, who joins or waits, whether the wait is bounded where needed, and
whether a stale object can affect a newer parser or subprocess.

## 3. Audit persistence boundaries

Treat IRC logs, nicknames, ntfy topics, notification logs, GUI configuration,
and analytics databases as private user data.

Check that:

- filesystem paths use the root implementation's existing `pathlib.Path` and
  explicit-encoding conventions;
- SQLite values remain parameterized and writes stay inside
  `InterviewDatabase.get_connection()`;
- interrupted or failed writes preserve transaction and connection cleanup;
- schema initialization is safe to repeat after restart;
- no finding or proposed test requires real user data;
- documentation does not claim automatic retention, retries, ntfy
  authentication, or durable rate limiting unless the implementation proves it.

## 4. Evaluate existing coverage

Start with `tests/test_reliability.py`, `tests/test_gui_reliability.py`, and
`tests/test_portability.py`. Also inspect parser and database-adjacent coverage
where relevant. For every proposed test, identify the exact behavior it would
falsify and match the existing `unittest`, `tempfile`, and `unittest.mock`
style.

Prefer deterministic tests with injected events or finite mocked loops. Never
add sleeps merely to make a race less likely. Do not launch the real notifier
or contact a live ntfy server.

## 5. Report before editing implementation

Complete the audit before changing source or tests. Report findings first,
ordered by severity. For each finding include:

- severity and confidence;
- the exact root file and symbol;
- the restart or recovery condition that triggers it;
- the user-visible consequence;
- existing test coverage or the specific missing regression test;
- the smallest repository-aligned fix;
- any privacy, telemetry, SQLite, or compatibility implications.

Group symptoms with the same root cause. Do not report unsupported hypotheticals
as defects. List open questions and known operational limitations separately.
If no defects are found, say so and identify residual test gaps.

Wait for explicit approval before editing implementation, tests, or
documentation. After approval, make one focused fix at a time, add or update a
regression test, and run:

```powershell
py -3 -m unittest <focused-test-module>
py -3 -m unittest discover -s tests
```

Only build a wheel if packaging metadata or entry points change. There is no
configured formatter, linter, static type checker, security scanner, or CI
workflow, so do not claim those checks ran or introduce them incidentally.

## Deliverable

Return a concise lifecycle map, prioritized findings, test gaps, and a staged
minimal remediation plan. Keep verified current behavior separate from
documentation gaps and known limitations.
