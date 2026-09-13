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

    def test_start_failure_terminates_created_process(self):
        gui = object.__new__(InterviewNotifyGUI)
        gui.validate_config = Mock(return_value=True)
        gui.log_dirs = ['chat.log']
        gui.log_message = Mock()
        gui.process = None
        for attribute, value in (
            ('topic_var', 'topic'),
            ('server_var', 'https://ntfy.sh/'),
            ('nick_var', 'candidate'),
            ('bot_nicks_var', 'Gatekeeper'),
            ('mode_var', 'red'),
            ('rate_limit_var', '60'),
            ('notif_log_var', ''),
        ):
            variable = Mock()
            variable.get.return_value = value
            setattr(gui, attribute, variable)
        gui.check_bot_nicks_var = Mock()
        gui.check_bot_nicks_var.get.return_value = True
        gui.enable_notif_log_var = Mock()
        gui.enable_notif_log_var.get.return_value = False
        process = Mock()

        with patch('interview_notify_gui.subprocess.Popen', return_value=process), patch(
            'interview_notify_gui.threading.Thread'
        ) as thread, patch('interview_notify_gui.messagebox.showerror'):
            thread.return_value.start.side_effect = RuntimeError('thread unavailable')
            gui.start_monitoring()

        process.terminate.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=5)
        self.assertIsNone(gui.process)

    def test_stop_monitoring_joins_output_reader(self):
        gui = object.__new__(InterviewNotifyGUI)
        gui.process = Mock()
        gui.output_thread = Mock()
        gui.start_button = Mock()
        gui.stop_button = Mock()
        gui.status_label = Mock()
        gui.log_message = Mock()

        gui.stop_monitoring()

        gui.output_thread.join.assert_called_once_with(timeout=1)
        self.assertIsNone(gui.process)

    def test_failed_config_save_preserves_existing_file(self):
        gui = object.__new__(InterviewNotifyGUI)
        gui.log_dirs = ['chat.log']
        for attribute, value in (
            ('topic_var', 'topic'),
            ('server_var', 'https://ntfy.sh/'),
            ('nick_var', 'candidate'),
            ('bot_nicks_var', 'Gatekeeper'),
            ('mode_var', 'red'),
            ('rate_limit_var', '60'),
            ('notif_log_var', ''),
        ):
            variable = Mock()
            variable.get.return_value = value
            setattr(gui, attribute, variable)
        gui.check_bot_nicks_var = Mock()
        gui.check_bot_nicks_var.get.return_value = True
        gui.enable_notif_log_var = Mock()
        gui.enable_notif_log_var.get.return_value = False

        def fail_after_partial_write(_config, stream, indent):
            stream.write('partial')
            raise OSError('disk full')

        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / 'config.json'
            config_path.write_text('existing', encoding='utf-8')
            with patch.object(interview_notify_gui, 'CONFIG_FILE', config_path), patch(
                'interview_notify_gui.json.dump', side_effect=fail_after_partial_write
            ), patch('interview_notify_gui.messagebox.showerror') as showerror:
                gui.save_config()

            self.assertEqual(config_path.read_text(encoding='utf-8'), 'existing')
            self.assertEqual(list(config_path.parent.glob('*.tmp')), [])
            showerror.assert_called_once()


if __name__ == '__main__':
    unittest.main()