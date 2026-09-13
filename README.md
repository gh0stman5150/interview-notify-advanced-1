# interview-notify

`interview-notify` watches local IRC log files, recognizes Red and Orpheus
(OPS) interview events, and sends push notifications to an
[ntfy](https://ntfy.sh/) server. It includes a command-line notifier, an
optional Tk GUI, notification history, and optional SQLite analytics.

The application does not connect to IRC. It polls files written by an IRC
client and has no third-party Python runtime dependencies.

## Capabilities

- Notify when any Red interview starts or when the configured user's interview
  starts.
- Notify when the OPS interview queue opens or Hermes sends an interview-room
  invitation.
- Detect mentions, disconnects, netsplits, and kicks in watched logs.
- Watch one or more individual log files or directories. For a directory, the
  notifier follows the most recently modified file and switches when a newer
  file appears. Watchers wait through temporary file or directory gaps and
  recover from truncation or replacement.
- Rate-limit repeated non-critical notification types. Notifications for the
  configured user's interview, disconnects, and kicks always bypass the limit.
- Append sent notifications to an optional plaintext history file.
- Store optional interview and queue analytics in SQLite and report them from
  the command line.
- Configure and supervise the notifier through an optional Tk GUI.

## How It Works

```text
IRC client -> local log file -> scanner/tailer -> mode parser
                                             -> rate limiter -> ntfy HTTP POST
                                             -> optional SQLite analytics

Tk GUI -> notifier subprocess
SQLite database -> statistics command
```

`interview_modes.py` contains the side-effect-free Red and OPS parsers.
`interview_notify.py` selects and tails logs, recognizes general IRC events,
applies rate limits, records analytics, and sends notifications. The GUI starts
that notifier as a subprocess; `view_stats.py` reads the analytics database.

When a parser starts or restarts, it processes the last existing line before
following new lines. Delivery at that boundary is therefore at least once: a
process restart can repeat the final notification. Rate-limit history is held
in memory and also resets when the process restarts.

## Requirements

- Python 3.9 or newer
- An IRC client configured to write channel or private-message logs locally
- An ntfy server and topic subscribed on the devices that should receive alerts
- Tkinter only when using the GUI

There is no Bash, PowerShell, systemd, Docker Compose, or other service wrapper
in this repository.

## Installation

Clone the repository, then install its three commands from the repository root.

Windows:

```powershell
py -3 -m pip install .
```

macOS or Linux:

```bash
python3 -m pip install .
```

This installs `interview-notify`, `interview-notify-gui`, and
`interview-notify-stats`. To run directly from a clone, replace the commands
with `py -3 interview_notify.py`, `py -3 interview_notify_gui.py`, or
`py -3 view_stats.py` on Windows. Use `python3` instead of `py -3` on macOS or
Linux.

### Tkinter

Tkinter is normally included with Windows Python installers. On other systems,
install the package matching the active Python version:

```bash
# Debian or Ubuntu
sudo apt-get install python3-tk

# Fedora or RHEL
sudo dnf install python3-tkinter

# Homebrew Python; match the suffix to the installed Python version
brew install python-tk@3.13
```

## Configure ntfy

Subscribe to a hard-to-guess topic in the ntfy web or mobile client, then pass
the same topic to `--topic`. The notifier sends an HTTP `POST` to
`SERVER/TOPIC`; the default server is `https://ntfy.sh/`.

The client does not implement ntfy access tokens, basic authentication, or
custom authentication headers. Use only a server/topic combination that is
safe to access without those credentials. Topic names are stored in the GUI
configuration and may appear in process arguments, so do not treat them as
secrets.

## Command-Line Usage

Minimal Red configuration:

```bash
interview-notify \
  --topic unique-topic-name \
  --log-dir /path/to/irc/logs \
  --nick your_nick
```

On PowerShell, write the command on one line or use PowerShell backticks in
place of the Bash continuations shown above.

Important options:

| Option | Behavior |
| --- | --- |
| `--topic TOPIC` | Required ntfy topic. |
| `--server URL` | ntfy base URL; defaults to `https://ntfy.sh/`. |
| `--log-dir PATH` | Required log file or directory; repeat for multiple paths. Repeated paths and aliases to the same filesystem object are monitored once. |
| `--log-encoding ENCODING` | `utf-8` (default), `ascii`, or `latin-1`. |
| `--nick NICK` | Required IRC nickname used for personal alerts. |
| `--mode MODE` | `red` (default), `ops`, or legacy alias `orp`. |
| `--bot-nicks NICKS` | Comma-separated bot names; defaults to `Gatekeeper` for Red and `Hermes` for OPS. |
| `--no-check-bot-nicks` | Parse supported phrases when the log format omits sender prefixes. |
| `--rate-limit SECONDS` | Minimum interval between notifications of the same non-critical type; defaults to 60. |
| `--notification-log PATH` | Append each successfully sent notification to a plaintext file. |
| `--enable-analytics` | Record supported interview events in SQLite. |
| `--analytics-db PATH` | Analytics database path; defaults to `~/.interview-notify-history.db`. |
| `-v` | Increase logging from the default INFO level to DEBUG; additional repetitions lower the numeric threshold further. |

Run `interview-notify --help` for the authoritative option list.

### Modes and Log Formats

Red mode recognizes `Currently interviewing: USERNAME` messages. OPS mode
recognizes `The queue is now open.` and Hermes invitations of the form
`You have been invited to take your interview in #channel.` Matching of these
phrases and configured bot names is case-insensitive.

By default, a supported sender prefix must appear before the phrase. Supported
formats include `<Gatekeeper>`, `Gatekeeper>`, and `-Hermes-`, including common
HTML-escaped wrappers. Use `--no-check-bot-nicks` only when the IRC client omits
the sender, because it increases the chance of false positives.

For OPS, watch both the recruitment-channel log and Hermes private-message log,
or watch a directory containing them:

```bash
interview-notify \
  --mode ops \
  --topic unique-topic-name \
  --log-dir /path/to/recruitment.log \
  --log-dir /path/to/hermes.log \
  --nick your_nick
```

Prefer explicit files when a directory also contains unrelated server or
network logs. A directory watcher follows only its newest file at a time.

## GUI Usage

Start the GUI with:

```bash
interview-notify-gui
```

The GUI supports Red and OPS modes, multiple log paths, custom bot names, rate
limiting, notification history, configuration save/load, and a live subprocess
log. It does not expose analytics settings; use the CLI for analytics.

Saved GUI configuration is plaintext at
`~/.interview-notify-config.json`. It includes the ntfy topic, IRC nickname,
server, and local paths. The GUI rejects malformed field types, unsupported
modes, and invalid rate limits without replacing the active form values.

## Analytics

Enable analytics and optionally select the database:

```bash
interview-notify \
  --topic unique-topic-name \
  --log-dir /path/to/logs \
  --nick your_nick \
  --enable-analytics \
  --analytics-db /path/to/interview-history.db
```

View the default database for the last 30 days:

```bash
interview-notify-stats
```

Other reporting examples:

```bash
interview-notify-stats --days 7
interview-notify-stats --channel red-invites
interview-notify-stats --db /path/to/interview-history.db
```

The report includes starts, outcomes, pass rate, average queue length, busiest
hours, and recent events. Red kick messages can produce passed, failed, or
missed outcomes. The current application does not automatically call its
90-day cleanup method; manage retention of the database explicitly.

## Security and Privacy

- The notifier reads local logs but sends matched log lines to the configured
  ntfy server. Those lines can contain nicknames, channel names, and message
  text.
- Each notifier start also sends telemetry to the public ntfy service. The
  payload contains a stable SHA-256-derived identifier based on the configured
  nickname, the canonical mode, and application version. There is currently no
  opt-out setting.
- Notification history, GUI configuration, and SQLite analytics are plaintext
  local files. Restrict their filesystem permissions, back them up only when
  appropriate, and remove them according to local data-retention policy.
- Use a hard-to-guess topic and HTTPS. This client has no support for ntfy
  authentication credentials.
- Do not share real IRC logs, nicknames, topics, configuration files, history
  files, or analytics databases in issues or commits.

## Troubleshooting

**No new log messages appear:** run with `-v -v -v`, verify the selected path,
and confirm the IRC client is appending to that file. For a directory, check
that the intended log is its most recently modified file. A temporarily empty
or unavailable directory is retried until a readable log appears.

**Interview messages are ignored:** verify `--mode` and `--bot-nicks`. If the
log does not identify the sender, retry with `--no-check-bot-nicks` and review
the debug output for false positives.

**Notifications do not arrive:** confirm that the device subscribes to exactly
the configured topic, the ntfy URL is reachable, and HTTPS traffic is allowed.
HTTP requests time out after 30 seconds. Failed requests are logged, are not
retried, do not consume the non-critical rate-limit interval, and do not stop
log processing.

**Text cannot be decoded:** select the IRC client's actual encoding with
`--log-encoding`.

**GUI does not start:** install Tkinter for the same Python interpreter used to
install or run the project.

## Testing

The test suite uses `unittest`, synthetic IRC lines, temporary directories, and
mocked HTTP calls. It does not contact ntfy or read user data.

```powershell
py -3 -m unittest tests.test_interview_modes
py -3 -m unittest discover -s tests
```

Use `python3 -m unittest ...` on macOS or Linux. Build a wheel after changing
packaging metadata or entry points:

```powershell
py -3 -m pip wheel . --no-deps --wheel-dir dist
```

There is currently no configured CI workflow, formatter, linter, static type
checker, or dedicated database/GUI test suite.

## Contributing and Support

Read [AGENTS.md](AGENTS.md) before changing code or documentation. Keep parser
logic pure and mode-specific, preserve import safety and critical-notification
behavior, add focused tests for behavior changes, and run the full suite before
opening a pull request. Do not edit generated files under `build/` or
`interview_notify.egg-info/`.

Use the repository's GitHub issue tracker for reproducible defects and support
requests. Redact all user data and include the Python version, operating system,
invocation with sensitive values replaced, relevant synthetic log format, and
error output. Ownership is represented by the repository maintainers; no
separate support SLA or escalation channel is defined in this repository.
