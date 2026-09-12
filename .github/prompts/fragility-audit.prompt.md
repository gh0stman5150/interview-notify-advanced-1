---
name: "Fragility Audit"
description: "Audit interview-notify for lifecycle, restart, file-watching, notification, SQLite, and GUI subprocess fragility, then propose evidence-backed fixes."
argument-hint: "Optional: name a suspected failure mode or module to prioritize"
agent: "agent"
---

Act as a senior reliability engineer reviewing this repository for concrete,
reproducible fragility. Focus on failures caused by routine runtime change:
log rotation or replacement, temporary missing files, partial thread failure,
process restart, ntfy or SQLite errors, malformed local state, and GUI subprocess
exit. If the user supplied a suspected failure mode or module, investigate it
first without excluding tightly related failures.

Before analyzing code, read [AGENTS.md](../../AGENTS.md) in full. It is the
authoritative source for architecture, safety invariants, validation, and
prohibited practices. Use [README.md](../../README.md) as the operational
contract. Precedence: `AGENTS.md` > implementation > `README.md`. If
implementation diverges from an `AGENTS.md` invariant, report it as a finding;
if `README.md` diverges from implementation, report it as a documentation gap,
not a code defect.
Inspect authoritative root modules and tests only; do not analyze or edit
generated copies under `build/` or `interview_notify.egg-info/`.

## Phase 1: Audit Read-Only

Trace the real control flow before reporting a defect. Start at the public
entrypoint or failing behavior, then follow the nearest code that directly
controls it. Prioritize these surfaces:

- `interview_notify.py`: argument normalization, path validation, scanner and
  parser thread lifecycle, directory switching, file tailing, notification
  rate limiting, HTTP failure behavior, notification logging, analytics calls,
  and startup telemetry.
- `interview_modes.py`: canonical `ops`/legacy `orp` behavior and immutable,
  side-effect-free parsing across supported modes.
- `interview_database.py` and `view_stats.py`: initialization, transaction
  rollback, concurrent access, bounded and parameterized values, persistence
  across restarts, query edge cases, and explicit-only retention cleanup.
- `interview_notify_gui.py`: configuration persistence, subprocess argument
  construction, output-thread races, unexpected child exit, repeated
  start/stop, and terminate-wait-kill-reap shutdown.
- `tests/`, `pyproject.toml`, and `README.md`: behavioral coverage, entrypoint
  consistency, and operational claims.

For each suspected weakness, test the actual assumption rather than inferring
failure from code shape alone. Pay particular attention to:

1. A watched file being truncated, renamed, replaced, deleted, or temporarily
   unavailable while `tail()` is running.
2. A watched directory becoming empty, containing unrelated files, changing
   during iteration/stat, or selecting a newer file while the prior parser is
   stopping.
3. One scanner/parser thread failing while other configured paths continue,
   including whether the failure is visible and recoverable.
4. Duplicate or missed notifications around process restart, parser restart,
   and log-file switching; distinguish documented at-least-once behavior from
   defects rather than inventing persistent offsets.
5. HTTP failures, notification-log failures, and analytics failures, including
   whether a failed send incorrectly affects later rate limiting or kills log
   processing.
6. Concurrent SQLite use, interrupted transactions, malformed database paths,
   and restart persistence without broadening `clear_old_data()`.
7. GUI child-process startup failure, natural exit, repeated stop calls, and
   output-reader access to a replaced or cleared process object.
8. Import and `--version` safety from outside the repository, including no
   argument parsing, monitoring, network access, or user-file creation on
   import.

Do not run `interview_notify.py`, the `interview-notify` entrypoint, or the GUI
as an audit shortcut: normal startup creates long-lived threads and sends
telemetry. Do not use live ntfy endpoints, real IRC logs, or files under the
user's home directory. Use static tracing and isolated tests with temporary
paths, mocks, and bounded thread synchronization.

## Phase 1 Deliverable

Report findings before editing implementation or tests. Order findings by
severity. For every finding include:

- evidence with a workspace-relative file and line reference;
- a minimal reproduction or focused test that would fail;
- the user-visible or operational impact;
- the root cause, including the relevant lifecycle/state transition;
- the smallest repository-aligned fix and any tradeoff;
- `BLOCKED BY POLICY` when the only fix would violate `AGENTS.md`, with no patch
  proposed for that finding.

Clearly separate confirmed defects from hypotheses requiring runtime evidence.
Also list important audit surfaces checked with no finding and remaining test
gaps. If there are no confirmed findings, say so and do not manufacture work.
Wait for explicit approval before changing implementation, tests, or docs.

## Phase 2: Approved Fixes

After approval, implement only the approved findings. For each behavior change:

- add or update focused `unittest` coverage in `tests/` using synthetic IRC
  lines, `tempfile` paths, mocked HTTP, and bounded synchronization;
- preserve critical-notification rate-limit bypass, canonical mode `ops` and
  alias `orp`, standard-library HTTP `POST` with a 30-second timeout,
  parameterized SQLite values, telemetry disclosure, and GUI shutdown order;
- keep mode parsing pure and immutable, database writes inside
  `InterviewDatabase.get_connection()`, and Tk updates on the GUI thread;
- update `README.md` only when user-visible behavior or operational guidance
  changes; and
- avoid unrelated refactors, new dependencies, service/container artifacts,
  authentication claims, telemetry controls, or automatic retention behavior.

Run the narrowest relevant test module after the first edit, then run:

```powershell
py -3 -m unittest discover -s tests
```

Build a wheel only if packaging metadata or entrypoints changed. There is no
configured formatter, linter, or static type checker, so do not invent or claim
those checks. Finish with a concise summary of fixes, validation results, and
any unresolved or policy-blocked risks.
