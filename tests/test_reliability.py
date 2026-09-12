import tempfile
import threading
import time
import unittest
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.error import URLError

import interview_notify


class NotificationReliabilityTests(unittest.TestCase):
    def setUp(self):
        interview_notify.args = SimpleNamespace(
            topic='test-topic',
            server='https://ntfy.sh/',
            notif_log=None,
            rate_limit=60,
            log_encoding='utf-8',
            mode='red',
            nick='candidate',
            check_bot_nicks=True,
            bot_nicks='Gatekeeper',
            enable_analytics=False,
        )
        interview_notify.db = None
        interview_notify.recent_notifications.clear()

    def test_failed_send_does_not_consume_rate_limit(self):
        with patch('interview_notify.urlopen', side_effect=URLError('offline')):
            self.assertFalse(
                interview_notify.notify('first', notification_type='mention')
            )

        with patch('interview_notify.urlopen') as urlopen:
            self.assertTrue(
                interview_notify.notify('second', notification_type='mention')
            )

        urlopen.assert_called_once()

    def test_failed_send_does_not_clear_a_newer_reservation(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)

        def send(request, timeout):
            if request.data == b'first':
                self.assertTrue(
                    interview_notify.notify('second', notification_type='mention')
                )
                raise URLError('first request failed late')
            return response

        with patch('interview_notify.time', side_effect=[0, 61, 62]), patch(
            'interview_notify.urlopen', side_effect=send
        ):
            self.assertFalse(
                interview_notify.notify('first', notification_type='mention')
            )
            self.assertTrue(interview_notify.should_rate_limit('mention'))

    def test_analytics_failure_does_not_prevent_notification(self):
        interview_notify.args.enable_analytics = True
        interview_notify.db = Mock()
        interview_notify.db.record_interview_start.side_effect = OSError(
            'disk unavailable'
        )
        line = (
            '<Gatekeeper> Currently interviewing: candidate '
            '::: #red-interview-01 ::: 2 remaining in queue.\n'
        )

        with patch('interview_notify.tail', return_value=iter([line])), patch(
            'interview_notify.notify'
        ) as notify:
            interview_notify.log_parse(Path('chat.log'), threading.Event())

        notify.assert_called_once()

    def test_notification_failure_does_not_escape_parser(self):
        line = '<Gatekeeper> Currently interviewing: candidate\n'

        with patch('interview_notify.tail', return_value=iter([line])), patch(
            'interview_notify.urlopen', side_effect=URLError('offline')
        ):
            interview_notify.log_parse(Path('chat.log'), threading.Event())


class FileWatcherReliabilityTests(unittest.TestCase):
    def setUp(self):
        interview_notify.args = SimpleNamespace(log_encoding='utf-8')

    def test_empty_directory_is_a_recoverable_state(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(interview_notify.find_latest_log(Path(directory)))

    def test_tail_recovers_after_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'chat.log'
            path.write_text('existing\n', encoding='utf-8')
            stop = threading.Event()
            seen = []

            def collect_lines():
                for line in interview_notify.tail(path, stop):
                    seen.append(line)

            worker = threading.Thread(target=collect_lines)
            worker.start()
            try:
                self.assertTrue(self._wait_for(lambda: self._has_line(seen, 'existing')))
                with path.open('a', encoding='utf-8') as stream:
                    stream.write('before-truncate\n')
                    stream.flush()
                self.assertTrue(
                    self._wait_for(
                        lambda: self._has_line(seen, 'before-truncate')
                    )
                )

                path.write_text('after-truncate\n', encoding='utf-8')
                self.assertTrue(
                    self._wait_for(lambda: self._has_line(seen, 'after-truncate'))
                )
            finally:
                stop.set()
                worker.join(timeout=2)

            self.assertFalse(worker.is_alive())

    def test_tail_releases_file_for_rename_and_follows_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'chat.log'
            rotated_path = Path(directory) / 'chat.log.1'
            path.write_text('existing\n', encoding='utf-8')
            stop = threading.Event()
            seen = []

            def collect_lines():
                for line in interview_notify.tail(path, stop):
                    seen.append(line)

            worker = threading.Thread(target=collect_lines)
            worker.start()
            try:
                self.assertTrue(self._wait_for(lambda: self._has_line(seen, 'existing')))
                os.replace(path, rotated_path)
                path.write_text('after-replacement\n', encoding='utf-8')
                self.assertTrue(
                    self._wait_for(lambda: self._has_line(seen, 'after-replacement'))
                )
            finally:
                stop.set()
                worker.join(timeout=2)

            self.assertFalse(worker.is_alive())

    def test_directory_scanner_restarts_a_dead_parser(self):
        log_path = Path('logs')
        current_log = log_path / 'chat.log'
        parsers = [Mock(), Mock()]
        for parser in parsers:
            parser.is_alive.return_value = False

        with patch(
            'interview_notify.find_latest_log', return_value=current_log
        ), patch(
            'interview_notify.spawn_parser',
            side_effect=[
                (parsers[0], threading.Event()),
                (parsers[1], threading.Event()),
            ],
        ) as spawn_parser, patch(
            'interview_notify.sleep', side_effect=[None, RuntimeError('stop test')]
        ), self.assertRaisesRegex(RuntimeError, 'stop test'):
            interview_notify.log_scan(log_path)

        self.assertEqual(spawn_parser.call_count, 2)

    @staticmethod
    def _wait_for(predicate, timeout=1.5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.02)
        return predicate()

    @staticmethod
    def _has_line(lines, expected):
        return expected in (line.strip() for line in lines)


if __name__ == '__main__':
    unittest.main()