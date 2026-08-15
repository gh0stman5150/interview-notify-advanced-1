import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import interview_notify


class PortabilityTests(unittest.TestCase):
    def test_cli_import_has_no_startup_side_effects(self):
        self.assertIsNone(interview_notify.args)

    def test_cli_version_runs_outside_project_directory(self):
        script = Path(interview_notify.__file__).resolve()

        with tempfile.TemporaryDirectory() as working_directory:
            result = subprocess.run(
                [sys.executable, str(script), '--version'],
                cwd=working_directory,
                capture_output=True,
                text=True,
                encoding='utf-8',
                check=True,
            )

        self.assertEqual(result.stdout.strip(), 'interview-notify v1.5.0')

    def test_notifications_use_standard_library_http(self):
        interview_notify.args = SimpleNamespace(
            topic='portable-topic',
            server='https://ntfy.sh/',
            notif_log=None,
            rate_limit=60,
        )
        interview_notify.recent_notifications.clear()

        with patch('interview_notify.urlopen') as urlopen:
            interview_notify.notify('hello', title='Portable', priority=3)

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, 'https://ntfy.sh/portable-topic')
        self.assertEqual(request.data, b'hello')
        self.assertEqual(request.method, 'POST')
        self.assertEqual(urlopen.call_args.kwargs['timeout'], 30)


if __name__ == '__main__':
    unittest.main()