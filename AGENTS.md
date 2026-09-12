# AGENTS.md

## Scope

This directory is both the VS Code workspace root and the root of the only Git
repository in the workspace. This file therefore provides both workspace and
repository guidance; do not create a parent `AGENTS.md` solely to add another
level.

## Purpose

`interview-notify` watches local IRC log files, recognizes private-tracker
interview events, and sends push notifications to an ntfy server. It also
offers a Tk GUI and optional SQLite-backed interview analytics. The runtime
supports Python 3.9 and newer and intentionally has no third-party dependencies.

## Architecture and Workflows

- CLI workflow: `main()` parses and normalizes configuration, validates every
  log path, starts one scanner thread per path, and sends startup telemetry.
- File workflow: an explicit file is tailed directly; a directory scanner tails
  only its most recently modified file and switches when a newer file appears.
- Event workflow: `interview_modes.py` parses mode-specific interview events;
  `interview_notify.py` handles mentions and IRC connection events, applies
  per-notification-type rate limits, then sends an HTTP `POST` to ntfy.
- Analytics workflow: when enabled, recognized interview starts, queue lengths,
  and supported Red outcome messages are written to SQLite. `view_stats.py`
  reads this database; it does not run retention cleanup.
- GUI workflow: `interview_notify_gui.py` stores configuration locally and
  starts `interview_notify.py` with the active Python interpreter. Analytics is
  CLI-only.

## Repository Layout

- `interview_notify.py`: CLI, log tailing, notification dispatch, rate limiting,
  notification history, and analytics integration.
- `interview_modes.py`: mode normalization and pure parsing of Red and Orpheus
  (`ops`) interview messages.
- `interview_database.py`: SQLite schema, writes, retention cleanup, and
  analytics queries.
- `interview_notify_gui.py`: Tk GUI, persisted user configuration, and lifecycle
  management for the notifier subprocess.
- `view_stats.py`: command-line reporting for the analytics database.
- `file_read_backwards/`: checked-in upstream compatibility package used to read
  the last existing log line. Keep project-specific behavior out of this code.
- `tests/`: `unittest` parser and portability regression tests.
- `build/` and `interview_notify.egg-info/`: generated packaging artifacts; the
  root modules and `file_read_backwards/` package are authoritative.

## Non-Negotiable Invariants

- Importing a CLI module must not start monitoring, perform network requests,
  create user files, or parse command-line arguments. Keep execution behind its
  `main()` entry point and `if __name__ == '__main__'` guard.
- Preserve `orp` as a legacy alias for canonical mode `ops`. Red defaults to
  `Gatekeeper`; OPS defaults to `Hermes` unless the user supplies bot nicks.
- Critical notifications (`your_interview`, disconnect, and kick) bypass rate
  limiting. Other repeated notification types honor the configured interval.
- Keep notification transport on the Python standard library unless a runtime
  dependency is deliberately approved. Requests use HTTP `POST` and a bounded
  timeout.
- SQLite values derived from logs or CLI input must remain parameterized. Do not
  broaden `clear_old_data()` deletion criteria without explicit review and
  tests using a temporary database.
- Treat IRC logs, nicknames, ntfy topics, notification logs, GUI configuration,
  and analytics databases as user data. Never commit real values or fixtures
  copied from a user's home directory.
- Preserve the startup telemetry disclosure in user documentation. The CLI
  sends a stable SHA-256-derived nickname identifier, canonical mode, and
  version to `https://ntfy.sh/interview-notify-telemetry`; there is currently
  no opt-out option.
- Do not claim ntfy authentication support. The client sends no access token,
  basic-auth credential, or custom authentication header.

## Coding Conventions

- Put mode-specific message recognition in `interview_modes.py` and return an
  immutable `InterviewEvent`; keep network, database, and UI side effects out of
  parser functions.
- Normalize a mode before selecting defaults or persisting it. Matching of IRC
  bot names and fixed phrases is case-insensitive where existing parsers are.
- Use `pathlib.Path` for new filesystem-facing code and explicit encodings for
  text files.
- Keep database writes inside `InterviewDatabase.get_connection()` so commits,
  rollbacks, WAL setup, and connection cleanup stay consistent.
- Validate externally derived database values, retain parameterized value
  placeholders, and bound stored text using the existing limits.
- Use `logging` for CLI and database diagnostics. The GUI relays subprocess
  output through its thread-safe queue; do not write to Tk widgets from worker
  threads.
- Use `subprocess` argument lists rather than shell command strings. Preserve
  explicit UTF-8 subprocess I/O and replacement of undecodable output in the
  GUI.
- Follow the style of the module being changed. The repository has no configured
  formatter, linter, or static type checker; do not claim or introduce one as an
  incidental change.

This is a Python repository. There are no repository-owned Bash, PowerShell,
systemd, Docker Compose, or GitHub Actions implementations from which to infer
additional conventions.

## Change Workflow

1. Add or update focused `unittest` coverage for behavior changes. Parser cases
   should use representative synthetic IRC lines; filesystem/database cases
   should use temporary paths; HTTP calls should be mocked.
2. Keep CLI choices, GUI choices/defaults, entry points, tests, and README usage
   synchronized when changing a public option or mode.
3. Keep the release version synchronized across `pyproject.toml`, CLI and GUI
   `VERSION` constants, documented output, and version assertions when making a
   release change.
4. Run the focused test module, then the full suite. Build a wheel when changing
   packaging metadata or entry points.
5. Keep pull requests focused. Describe user-visible behavior, privacy or
   operational effects, validation performed, and any remaining manual checks.

## Documentation Standards

- Treat root Python modules, tests, and `pyproject.toml` as the implementation
  source of truth. Treat this file as the source of truth for contributor safety
  and process requirements.
- Update `README.md` whenever installation, CLI/GUI options, event semantics,
  storage locations, network behavior, or troubleshooting steps change.
- Keep `.github/copilot-instructions.md` as a compatibility pointer to this
  file. Do not maintain a second copy of repository rules there.
- Use current behavior in operational sections. Preserve historical incidents
  only when they remain useful, label their observation period, and do not
  present them as current verification.
- Prefer concise examples with synthetic nicknames, topics, channels, and paths.
  Verify command names and options against `pyproject.toml` and the relevant
  `argparse` definitions.
- Record known gaps explicitly instead of documenting planned behavior as if it
  exists. Keep terminology consistent: use `Red`, `OPS`, canonical mode `ops`,
  legacy alias `orp`, and `ntfy`.

## Operational Considerations

- The notifier is a long-running polling process. There is no bundled service
  manager, container definition, health check, retry policy, or CI workflow.
- Each directory watcher follows only one file at a time: the file with the
  newest modification time. Recommend explicit files when unrelated logs share
  a directory.
- HTTP requests use the standard library, method `POST`, and a 30-second
  timeout. Notification failures are not retried by the application.
- Notification logs, GUI configuration, and analytics databases are plaintext.
  The application does not configure file permissions, encryption, backup, log
  rotation, or automatic analytics retention.
- `InterviewDatabase.clear_old_data(days=90)` is an explicit API only. Do not
  state that old records are automatically removed unless a tested caller is
  added.
- The GUI configuration path is `~/.interview-notify-config.json`; the default
  analytics path is `~/.interview-notify-history.db`.

## Validation Commands

Run from the repository root:

```powershell
py -3 -m unittest tests.test_interview_modes
py -3 -m unittest discover -s tests
py -3 -m pip wheel . --no-deps --wheel-dir dist
```

The wheel command is required only for packaging or entry-point changes. No lint
command is configured in this repository.

## Prohibited Practices

- Do not edit or test against files under `build/` or
  `interview_notify.egg-info/`; regenerate packaging outputs when needed.
- Do not run `interview_notify.py` or `interview-notify` as a routine validation
  command. It starts long-running watcher threads and `main()` sends anonymous
  telemetry to the default ntfy service in addition to configured notifications.
- Do not make tests depend on live ntfy endpoints, real IRC logs, the user's
  `~/.interview-notify-config.json`, or the default
  `~/.interview-notify-history.db`.
- Do not weaken subprocess shutdown in the GUI: terminate, wait with a timeout,
  then kill and reap only when termination does not complete.
- Do not add shell wrappers, deployment manifests, authentication mechanisms,
  telemetry controls, or retention automation only to make documentation claims
  true; implementation changes require their own design and tests.

## Known Gaps

- There is no configured CI workflow, formatter, linter, type checker, or
  dedicated database/GUI test suite. Treat those as gaps rather than assuming
  undocumented commands or coverage.
- There is no documented support SLA, security contact, code of conduct,
  contribution template, or pull request template.
