#!/usr/bin/env python3

import argparse, sys, threading, logging, re
from pathlib import Path
from time import sleep, time
from datetime import datetime
from file_read_backwards import FileReadBackwards
from hashlib import sha256
from interview_modes import default_bot_nicks, normalize_mode, parse_interview_event
from urllib.parse import urljoin
from urllib.request import Request, urlopen

try:
    from interview_database import InterviewDatabase
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    logging.warning("Interview database module not available - analytics disabled")

VERSION = '1.5.0'
default_server = 'https://ntfy.sh/'

# Rate limiting and notification history
notification_lock = threading.Lock()
recent_notifications = {}  # {notification_type: timestamp}
notification_log_file = None
db = None  # Global database instance
args = None

def user_path(value):
  return Path(value).expanduser()


parser = argparse.ArgumentParser(prog='interview-notify',
  description='IRC Interview Notifier v{}\nhttps://github.com/ftc2/interview-notify'.format(VERSION),
  epilog='''Sends a push notification with https://ntfy.sh/ when it's your turn to interview.
They have a web client and mobile clients. You can have multiple clients subscribed to this.
Wherever you want notifications: open the client, 'Subscribe to topic', pick a unique topic
  name for this script, and use that everywhere.
On mobile, I suggest enabling the 'Instant delivery' feature as well as 'Keep alerting for
  highest priority'. These will enable fastest and most reliable delivery of the
  notification, and your phone will continuously alarm when your interview is ready.''',
  formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('--topic', required=True, help='ntfy topic name to POST notifications to')
parser.add_argument('--server', default=default_server, help='ntfy server to POST notifications to – default: {}'.format(default_server))
parser.add_argument('--log-dir', required=True, dest='paths', type=user_path, action='append', help='path to an IRC log file or directory (can be specified multiple times)')
parser.add_argument('--log-encoding', choices=['utf-8', 'ascii', 'latin-1'], default='utf-8', help='IRC log file encoding – default: utf-8')
parser.add_argument('--nick', required=True, help='your IRC nick')
parser.add_argument('--check-bot-nicks', default=True, action=argparse.BooleanOptionalAction, help="attempt to parse bot's nick. disable if your log files are not like '<nick> message' – default: enabled")
parser.add_argument('--bot-nicks', metavar='NICKS', help='comma-separated list of bot nicks to watch – default: Gatekeeper for red, Hermes for ops')
parser.add_argument('--mode', choices=['red', 'ops', 'orp'], default='red', help='interview mode (orp is a legacy alias for ops) – default: red')
parser.add_argument('--notification-log', dest='notif_log', type=user_path, help='path to file for logging all notifications (optional)')
parser.add_argument('--rate-limit', dest='rate_limit', type=int, default=60, help='seconds to wait before sending duplicate notifications – default: 60')
parser.add_argument('--enable-analytics', dest='enable_analytics', action='store_true', help='enable interview statistics tracking and analysis')
parser.add_argument('--analytics-db', dest='analytics_db', type=user_path, help='path to analytics database file (optional, defaults to ~/.interview-notify-history.db)')
parser.add_argument('-v', action='count', default=5, dest='verbose', help='verbose (invoke multiple times for more verbosity)')
parser.add_argument('--version', action='version', version='{} v{}'.format(parser.prog, VERSION))

def log_scan(log_path):
  """Poll dir for most recently modified log file and spawn a parser thread for the log"""
  if log_path.is_file():
    logging.info('scanner: watching log file "{}"'.format(log_path))
    parser, _parser_stop = spawn_parser(log_path)
    parser.start()
    parser.join()
    return

  logging.info('scanner: watching logs in "{}"'.format(log_path))
  curr = find_latest_log(log_path)
  logging.debug('scanner: current log: "{}"'.format(curr.name))
  parser, parser_stop = spawn_parser(curr)
  parser.start()
  while True:
    sleep(0.5) # polling delay for checking for newer logfile
    latest = find_latest_log(log_path)
    if curr != latest:
      curr = latest
      logging.info('scanner: newer log found: "{}"'.format(curr.name))
      parser_stop.set()
      parser.join()
      parser, parser_stop = spawn_parser(curr)
      parser.start()

def find_latest_log(log_path):
  """Find latest log file"""
  files = [f for f in log_path.iterdir() if f.is_file() and f.name not in ['.DS_Store', 'thumbs.db']]
  if len(files) == 0:
    crit_quit('no log files found in "{}"'.format(log_path))
  return max(files, key=lambda f: f.stat().st_mtime)

def spawn_parser(log_path):
  """Spawn new parser thread"""
  logging.debug('spawning new parser')
  parser_stop = threading.Event()
  thread = threading.Thread(target=log_parse, args=(log_path, parser_stop))
  return thread, parser_stop

def log_parse(log_path, parser_stop):
  """Parse log file and notify on triggers (parser thread)"""
  logging.info('parser: using "{}"'.format(log_path.name))

  # Extract channel name more robustly
  # Try to get from parent directory name, fall back to log file name
  try:
    channel = log_path.parent.name
    # If parent is just a generic name, try the log file name
    if not channel or channel in ['.', '..', 'logs', 'Channels']:
      channel = log_path.stem  # File name without extension
  except:
    channel = 'unknown'

  for line in tail(log_path, parser_stop):
    logging.debug(line)
    interview_event = parse_interview_event(
      line,
      args.mode,
      args.nick,
      check_bot_nicks=args.check_bot_nicks,
      bot_nicks=args.bot_nicks,
    )

    # Check for analytics events first (before notifications)
    if db and args.enable_analytics:
      # Check for interview start
      if interview_event and interview_event.username:
        event_channel = interview_event.interview_channel or channel
        db.record_interview_start(
          interview_event.username,
          interview_event.queue_length,
          event_channel,
        )
        if interview_event.queue_length is not None:
          db.record_queue_snapshot(interview_event.queue_length, event_channel)
        logging.debug(
          f'Analytics: Recorded interview start for {interview_event.username}, '
          f'queue: {interview_event.queue_length}'
        )

      # Check for interview outcome
      outcome_data = parse_interview_outcome(line)
      if outcome_data:
        username, outcome, message = outcome_data
        db.record_interview_outcome(username, outcome, message, channel)
        logging.debug(f'Analytics: Recorded {outcome} outcome for {username}')

    # Now check for notifications
    if interview_event:
      if interview_event.notification_type == 'your_interview':
        logging.info('YOUR INTERVIEW IS HAPPENING ❗')
      else:
        logging.info('interview detected ⚠️')
      notify(
        line,
        title=interview_event.title,
        tags=interview_event.tags,
        priority=interview_event.priority,
        notification_type=interview_event.notification_type,
      )
    elif check_trigger(line, '{}:'.format(args.nick), disregard_bot_nicks=True):
      logging.info('mention detected ⚠️')
      notify(line, title="You've been mentioned", tags='wave', notification_type='mention')
    elif 'Disconnected' in line:
      logging.info('IRC disconnect detected ⚠️')
      notify(line, title="You've been disconnected from IRC!", tags='x', priority=5, notification_type='disconnect')
    elif check_netsplit(line):
      logging.info('netsplit detected ⚠️')
      notify(line, title="Netsplit detected – requeue within 10min!", tags='electric_plug', priority=5, notification_type='netsplit')
    elif check_words(line, triggers=['kick'], check_nick=True):
      logging.info('kick detected ⚠️')
      notify(line, title="You've been kicked – rejoin & requeue ASAP!", tags='anger', priority=5, notification_type='kick')

def tail(path, parser_stop):
  """Poll file and yield lines as they appear"""
  with FileReadBackwards(path, encoding=args.log_encoding) as f:
    last_line = f.readline()
    if last_line:
      yield last_line
  with open(path, encoding=args.log_encoding) as f:
    f.seek(0, 2) # os.SEEK_END
    while not parser_stop.is_set():
      line = f.readline()
      if not line:
        sleep(0.1) # polling delay for checking for new lines
        continue
      yield line

def check_trigger(line, trigger, disregard_bot_nicks=False):
  """Check for a trigger in a line"""
  if disregard_bot_nicks or not args.check_bot_nicks:
    return trigger in remove_html_tags(line)
  else:
    triggers = bot_nick_prefix(trigger)
    return any(trigger in line for trigger in triggers)

def check_words(line, triggers, check_nick=False):
  """Check if a trigger & a bot nick & (optionally) user nick all appear in a string"""
  for trigger in triggers:
    for bot in args.bot_nicks.split(','):
      bot = bot.strip()  # Remove whitespace from bot nicks
      if check_nick:
        if args.nick in line and bot in line and trigger.lower() in line.lower():
          return True
      else:
        if bot in line and trigger.lower() in line.lower():
          return True
  return False

def check_netsplit(line):
  """Check if line contains actual IRC netsplit or ping timeout message"""
  if 'left IRC' not in line:
    return False
  # Check for actual netsplit pattern
  if '*.net *.split' in line:
    return True
  # Check for ping timeout with exactly 121 seconds
  if 'Ping timeout: 121 seconds' in line:
    return True
  return False

def parse_interview_start(line):
  """Parse interview start message and return (username, queue_length) or None"""
  # Pattern: <Gatekeeper> Currently interviewing: USERNAME ::: #red-interview-01 ::: 59 remaining in queue.
  # More robust: handle usernames with special chars, optional whitespace
  match = re.search(r'Currently interviewing:\s+([^\s:]+)\s+:::.*?:::\s+(\d+)\s+remaining in queue', line, re.IGNORECASE)
  if match:
    try:
      username = match.group(1).strip()
      queue_length = int(match.group(2))
      return (username, queue_length)
    except (ValueError, AttributeError) as e:
      logging.debug(f"Failed to parse interview start: {e}")
      return None
  return None

def parse_interview_outcome(line):
  """Parse interview outcome (kick message) and return (username, outcome, message) or None"""
  # Check if it's a kick message from Gatekeeper
  # More robust: handle various kick message formats
  kick_match = re.search(r'Gatekeeper kicked\s+([^\s]+)\s+from the channel\s*\((.+?)\)\s*$', line)
  if not kick_match:
    return None

  try:
    username = kick_match.group(1).strip()
    message = kick_match.group(2).strip()

    # Determine outcome based on message content (case insensitive)
    message_lower = message.lower()
    if 'congratulations' in message_lower and 'welcome to' in message_lower:
      return (username, 'passed', message)
    elif 'not passed the interview' in message_lower or 'you have not passed' in message_lower:
      return (username, 'failed', message)
    elif 'missed your interview' in message_lower:
      return (username, 'missed', message)

    # Unknown kick reason - log it
    logging.debug(f"Unknown kick reason for {username}: {message}")
    return None
  except (AttributeError, IndexError) as e:
    logging.debug(f"Failed to parse kick message: {e}")
    return None

def remove_html_tags(text):
  """Remove html tags from a string"""
  clean = re.compile('<.*?>')
  return re.sub(clean, '', text)

def bot_nick_prefix(trigger):
  """Prefix a trigger with bot nick(s) to reduce false positives"""
  nicks = [nick.strip() for nick in args.bot_nicks.split(',')]
  return ['{}> {}'.format(nick, trigger) for nick in nicks]

def notify(data, topic=None, server=None, notification_type=None, **kwargs):
  """Send notification via ntfy with rate limiting and logging"""
  if topic is None: topic=args.topic
  if server is None: server=args.server

  # Rate limiting check
  if notification_type and should_rate_limit(notification_type):
    logging.debug('rate-limited notification type: {}'.format(notification_type))
    return

  # Send notification
  if server[-1] != '/': server += '/'
  target = urljoin(server, topic, allow_fragments=False)
  # Remove notification_type from kwargs as it's not a valid ntfy header
  headers = {k.capitalize(): str(v) for (k, v) in kwargs.items()}
  request = Request(target, data=data.encode('utf-8'), headers=headers, method='POST')
  with urlopen(request, timeout=30):
    pass

  # Log notification if enabled
  log_notification(notification_type, kwargs.get('title', 'Notification'), data, kwargs.get('priority', 3))

def should_rate_limit(notification_type):
  """Check if notification should be rate limited"""
  with notification_lock:
    current_time = time()

    # Always send critical notifications (your interview, disconnect, kick)
    if notification_type in ['your_interview', 'disconnect', 'kick']:
      recent_notifications[notification_type] = current_time
      return False

    # Check if we've sent this notification type recently
    if notification_type in recent_notifications:
      time_since_last = current_time - recent_notifications[notification_type]
      if time_since_last < args.rate_limit:
        return True  # Rate limit this notification

    # Update the timestamp for this notification type
    recent_notifications[notification_type] = current_time
    return False

def log_notification(notification_type, title, message, priority):
  """Log notification to file if enabled"""
  if not args.notif_log:
    return

  try:
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = '[{}] type={} priority={} title={}\n  message: {}\n'.format(
      timestamp, notification_type or 'unknown', priority, title, message.strip()
    )

    with notification_lock:
      with open(args.notif_log, 'a', encoding='utf-8') as f:
        f.write(log_entry)
  except Exception as e:
    logging.error('failed to write notification log: {}'.format(e))

def anon_telemetry():
  """Send anonymous telemetry

  Why? I won't bother working on it if I don't see people using it!
  I can't get your nick or IP or anything.

  sends: anon id based on nick, script mode, script version
  """
  seed = 'H6IhIkah11ee1AxnDKClsujZ6gX9zHf8'
  nick_sha = sha256(args.nick.encode('utf-8')).hexdigest()
  anon_id = sha256('{}{}'.format(nick_sha, seed).encode('utf-8')).hexdigest()
  notify('anon_id={}, mode={}, version={}'.format(anon_id, args.mode, VERSION),
          server=default_server,
          title='Anonymous Telemetry', topic='interview-notify-telemetry', tags='telephone_receiver')

def crit_quit(msg):
  logging.critical(msg)
  sys.exit()

def main():
  global args, db

  args = parser.parse_args()
  args.mode = normalize_mode(args.mode)
  if args.bot_nicks is None:
    args.bot_nicks = default_bot_nicks(args.mode)

  args.verbose = 70 - (10*args.verbose) if args.verbose > 0 else 0
  logging.basicConfig(level=args.verbose, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

  if args.enable_analytics:
    if not DATABASE_AVAILABLE:
      logging.error('Analytics enabled but interview_database module not available')
      crit_quit('Cannot enable analytics without interview_database.py module')
    db = InterviewDatabase(args.analytics_db)
    logging.info(f'Analytics enabled, database: {db.db_path}')
  else:
    logging.debug('Analytics disabled')

  for path in args.paths:
    if not path.is_file() and not path.is_dir():
      crit_quit('log path invalid – "{}"'.format(path))

  for path in args.paths:
    scanner = threading.Thread(target=log_scan, args=(path,))
    scanner.start()
    logging.info('started scanner for "{}"'.format(path))

  anon_telemetry()


if __name__ == '__main__':
  main()
