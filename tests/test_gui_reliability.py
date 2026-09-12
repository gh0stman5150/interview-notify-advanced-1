import io
import json
import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import interview_notify_gui
from interview_notify_gui import InterviewNotifyGUI


class GuiReliabilityTests(unittest.TestCase):
    def test_output_reader_stays_bound_to_its_process(self):
        gui = object.__new__(InterviewNotifyGUI)
        gui.log_queue = queue.Queue()
        old_process = Mock(stdout=io.StringIO('old-process\n'))
        gui.process = Mock(stdout=io.StringIO('new-process\n'))

        gui.read_output(old_process)

        self.assertEqual(gui.log_queue.get_nowait(), 'old-process')

    def test_load_config_rejects_invalid_log_directory_shape(self):
        gui = object.__new__(InterviewNotifyGUI)
        gui.log_dirs = ['existing.log']
        for attribute in (
            'topic_var',
            'server_var',
            'nick_var',
            'mode_var',
            'bot_nicks_var',
            'rate_limit_var',
            'check_bot_nicks_var',
            'enable_notif_log_var',
            'notif_log_var',
            'log_dir_listbox',
        ):
            setattr(gui, attribute, Mock())
        gui.toggle_notif_log = Mock()

        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / 'config.json'
            config_path.write_text(
                json.dumps({'log_dirs': 'not-a-list'}), encoding='utf-8'
            )
            with patch.object(interview_notify_gui, 'CONFIG_FILE', config_path), patch(
                'interview_notify_gui.messagebox.showerror'
            ) as showerror:
                gui.load_config()

        self.assertEqual(gui.log_dirs, ['existing.log'])
        showerror.assert_called_once()


if __name__ == '__main__':
    unittest.main()