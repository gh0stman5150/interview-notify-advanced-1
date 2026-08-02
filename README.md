# interview-notify
Push notifications from IRC for your private tracker interviews

<img src="https://i.imgur.com/ZLFyxgY.png">

## features

this script parses log files from your irc client and attempts to be client-agnostic.

it sends push notifications when:
- interviews are happening
- YOUR interview is happening!
- someone mentions you
- you get disconnected from IRC
- you lose your spot in the queue due to a netsplit
- you get kicked

**new in v1.5.0:**
- **Orpheus (OPS) support** – get notified when the interview queue opens and receive a critical alert when your interview room is ready

**new in v1.4.0:**
- **GUI application** – optional graphical interface for easy configuration (use `python3 interview_notify_gui.py`)
- **interview analytics** – track interview statistics, success rates, queue lengths, and trends (enable with `--enable-analytics`)
- **rate limiting** – prevents notification spam during mass events like netsplits (configurable with `--rate-limit`)
- **notification history** – logs all notifications to a file for review (enable with `--notification-log`)
- **multi-channel support** – watch multiple IRC channels simultaneously (specify `--log-dir` multiple times)

## installing

- install python3. i suggest homebrew, winget, or just use the installer: https://www.python.org/downloads/
  - _this script might require python3.11_
- install the `requests` module with `pip3 install requests` (or use `pipenv install` to automatically install dependencies)
- clone this repo
  - `git clone https://github.com/ftc2/interview-notify.git`
- `python3 interview_notify.py`

### for GUI users

**IMPORTANT:** The GUI requires tkinter. You must install the version that matches your Python installation.

**Step 1:** Check your Python version:
```bash
python3 --version
```

**Step 2:** Install the matching python-tk package:

- **macOS (Homebrew Python)**:
  - For Python 3.13: `brew install python-tk@3.13`
  - For Python 3.14: `brew install python-tk@3.14`
  - Match the version to what you saw in Step 1!

- **macOS (alternative)**: use system Python `/usr/bin/python3 interview_notify_gui.py`
  - Note: You may see a deprecation warning, but it will work

- **Linux (Debian/Ubuntu)**: `sudo apt-get install python3-tk`

- **Linux (Fedora/RHEL)**: `sudo dnf install python3-tkinter`

- **Windows**: tkinter is usually included, if not reinstall Python with tcl/tk option

## using

### GUI (recommended for beginners)
<img src="https://i.imgur.com/NeeANqE.png">

for a user-friendly graphical interface:

```bash
python3 interview_notify_gui.py
```

the GUI provides:
- easy configuration with forms instead of command-line arguments
- start/stop monitoring with buttons
- live log viewer
- save/load configuration
- multi-channel support with add/remove buttons

### command line

for advanced users and automation, use the CLI:

pretty self explanatory if you read the help:

```
./interview_notify.py -h

usage: interview_notify.py [-h] --topic TOPIC [--server SERVER] --log-dir PATH --nick NICK [--check-bot-nicks | --no-check-bot-nicks] [--bot-nicks NICKS] [--mode {red,ops,orp}] [-v] [--version]

IRC Interview Notifier v1.5.0
https://github.com/ftc2/interview-notify

options:
  -h, --help            show this help message and exit
  --topic TOPIC         ntfy topic name to POST notifications to
  --server SERVER       ntfy server to POST notifications to – default: https://ntfy.sh
  --log-dir PATH        path to IRC logs (continuously checks for newest file to parse)
  --nick NICK           your IRC nick
  --check-bot-nicks, --no-check-bot-nicks
                        attempt to parse bot's nick. disable if your log files are not like '<nick> message' – default: enabled
  --bot-nicks NICKS     comma-separated list of bot nicks to watch – default: Gatekeeper for red, Hermes for ops
  --mode {red,ops,orp}  interview mode (orp is a legacy alias for ops) – default: red
  -v                    verbose (invoke multiple times for more verbosity)
  --version             show program's version number and exit

Sends a push notification with https://ntfy.sh/ when it's your turn to interview.
They have a web client and mobile clients. You can have multiple clients subscribed to this.
Wherever you want notifications: open the client, 'Subscribe to topic', pick a unique topic
  name for this script, and use that everywhere.
On mobile, I suggest enabling the 'Instant delivery' feature as well as 'Keep alerting for
  highest priority'. These will enable fastest and most reliable delivery of the
  notification, and your phone will continuously alarm when your interview is ready.
```

## testing/troubleshooting

first, use `-v` and make sure you can see new messages from IRC showing up:

`interview_notify.py --topic your_topic --log-dir /path/to/logs --nick your_nick -v`

### testing notifications

`interview_notify.py --topic your_topic --log-dir /path/to/logs --nick your_nick --bot-nicks Gatekeeper,your_nick -v`

then type `Currently interviewing: your_nick` in IRC.

if it doesn't work, maybe you have a wonky log file format. try with `--no-check-bot-nicks`:

`interview_notify.py --topic your_topic --log-dir /path/to/logs --nick your_nick --no-check-bot-nicks -v`

### Orpheus (OPS)

Orpheus announces queue openings in the recruitment channel and sends the interview-room
invitation in a private message from Hermes. Point the notifier at both relevant log files
or at a directory containing them:

```bash
interview_notify.py --mode ops --topic your_topic \
  --log-dir '/path/to/irc/logs/#recruitment.log' \
  --nick your_nick
```

In `ops` mode, Hermes is the default bot nick. The legacy mode name `orp` is also
accepted for compatibility. If your IRC client does not include the sender in each
log line, add `--no-check-bot-nicks`. Queue-open notifications use the configured rate
limit; interview-room invitations are critical and are never rate-limited.

The script only reads local IRC logs; it does not connect to the Orpheus IRC network.
Passing a specific log file is recommended when the surrounding directory contains
server and network logs that are updated independently.

## advanced features

### multi-channel support

watch multiple IRC channels simultaneously by specifying `--log-dir` multiple times:

```bash
interview_notify.py --topic your_topic \
  --log-dir /path/to/red/logs \
  --log-dir /path/to/ops/logs \
  --nick your_nick
```

### interview analytics

track interview statistics and analyze patterns:

```bash
# enable analytics tracking
interview_notify.py --topic your_topic --log-dir /path/to/logs --nick your_nick \
  --enable-analytics
```

the script will automatically track:
- interview starts and queue lengths
- interview outcomes (passed/failed/missed)
- busiest hours for interviews
- success rates and trends

**view your statistics:**

```bash
# view stats for the last 30 days
python3 view_stats.py

# view stats for the last 7 days
python3 view_stats.py --days 7

# view stats for a specific channel
python3 view_stats.py --channel "red-invites"
```

**example output:**
```
======================================================================
Interview Statistics (Last 30 days)
======================================================================

📊 Total Interviews:     145
✅ Passed:               87 (60.0%)
❌ Failed:               42
⏰ Missed:               16
📈 Average Queue Length: 45.3

🕐 Busiest Hours (most interviews):
   18:00 - 23 interviews
   19:00 - 21 interviews
   20:00 - 19 interviews
```

database is stored at `~/.interview-notify-history.db` by default. old data (>90 days) is automatically cleaned up.

### running tests

```bash
python3 -m unittest discover -s tests
```

### notification history

log all notifications to a file for review:

```bash
interview_notify.py --topic your_topic --log-dir /path/to/logs --nick your_nick \
  --notification-log ~/interview-notifications.log
```

### rate limiting

prevent notification spam during mass events (like netsplits). default is 60 seconds. critical notifications (your interview, disconnect, kick) are never rate-limited:

```bash
# set rate limit to 120 seconds
interview_notify.py --topic your_topic --log-dir /path/to/logs --nick your_nick \
  --rate-limit 120
```
