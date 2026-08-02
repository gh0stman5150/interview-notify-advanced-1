#!/usr/bin/env python3

"""Mode-specific IRC interview message parsing."""

import re
from dataclasses import dataclass
from typing import Optional


MODE_ALIASES = {
    'orp': 'ops',
}

DEFAULT_BOT_NICKS = {
    'red': 'Gatekeeper',
    'ops': 'Hermes',
}


@dataclass(frozen=True)
class InterviewEvent:
    """A normalized interview event parsed from an IRC log line."""

    notification_type: str
    title: str
    tags: str
    priority: int = 3
    username: Optional[str] = None
    queue_length: Optional[int] = None
    interview_channel: Optional[str] = None


def normalize_mode(mode):
    """Return the canonical name for a configured interview mode."""
    normalized = (mode or 'red').lower()
    return MODE_ALIASES.get(normalized, normalized)


def default_bot_nicks(mode):
    """Return the default bot nick list for a mode."""
    return DEFAULT_BOT_NICKS[normalize_mode(mode)]


def parse_interview_event(line, mode, nick, check_bot_nicks=True, bot_nicks=None):
    """Parse a mode-specific interview event from an IRC log line."""
    mode = normalize_mode(mode)
    if bot_nicks is None:
        bot_nicks = default_bot_nicks(mode)

    if mode == 'red':
        return _parse_red_event(line, nick, check_bot_nicks, bot_nicks)
    if mode == 'ops':
        return _parse_ops_event(line, nick, check_bot_nicks, bot_nicks)
    raise ValueError('unsupported interview mode: {}'.format(mode))


def _parse_red_event(line, nick, check_bot_nicks, bot_nicks):
    clean_line = _remove_html_tags(line)
    match = re.search(
        r'Currently interviewing:\s+([^\s:]+)'
        r'(?:\s+:::.*?:::\s+(\d+)\s+remaining in queue)?',
        clean_line,
        re.IGNORECASE,
    )
    if not match or not _bot_matches(line, match.group(0), check_bot_nicks, bot_nicks):
        return None

    username = match.group(1).strip()
    queue_length = int(match.group(2)) if match.group(2) is not None else None
    if username.casefold() == nick.casefold():
        return InterviewEvent(
            notification_type='your_interview',
            title='Your interview is happening❗',
            tags='rotating_light',
            priority=5,
            username=username,
            queue_length=queue_length,
        )

    return InterviewEvent(
        notification_type='interview',
        title='Interview detected',
        tags='warning',
        username=username,
        queue_length=queue_length,
    )


def _parse_ops_event(line, nick, check_bot_nicks, bot_nicks):
    clean_line = _remove_html_tags(line)
    queue_open_match = re.search(
        r'The\s+queue\s+is\s+now\s+open\.',
        clean_line,
        re.IGNORECASE,
    )
    if queue_open_match and _bot_matches(
        line,
        queue_open_match.group(0),
        check_bot_nicks,
        bot_nicks,
    ):
        return InterviewEvent(
            notification_type='queue_open',
            title='Orpheus interview queue is open',
            tags='loudspeaker',
            priority=4,
        )

    match = re.search(
        r'You\s+have\s+been\s+(?:have\s+been\s+)*invited'
        r'\s+to\s+take\s+your\s+interview'
        r'\s+in\s+(#[A-Za-z0-9_-]+)\s*[.!]?',
        clean_line,
        re.IGNORECASE,
    )
    if not match or not _bot_matches(line, match.group(0), check_bot_nicks, bot_nicks):
        return None

    return InterviewEvent(
        notification_type='your_interview',
        title='Your Orpheus interview is ready❗',
        tags='rotating_light',
        priority=5,
        username=nick,
        interview_channel=match.group(1),
    )


def _bot_matches(line, trigger, check_bot_nicks, bot_nicks):
    if not check_bot_nicks:
        return True

    trigger_position = line.lower().find(trigger.lower())
    if trigger_position < 0:
        # HTML removal can change offsets, so fall back to checking the whole line.
        prefix = line
    else:
        prefix = line[:trigger_position]

    for bot_nick in bot_nicks.split(','):
        bot_nick = bot_nick.strip()
        if not bot_nick:
            continue
        if re.search(
            r'(?:(?:<|&lt;){bot}(?:>|&gt;)|'
            r'{bot}(?:>|&gt;)|-{bot}-)\s*$'.format(
                bot=re.escape(bot_nick)
            ),
            prefix,
            re.IGNORECASE,
        ):
            return True
    return False


def _remove_html_tags(text):
    return re.sub(r'<.*?>', '', text)
