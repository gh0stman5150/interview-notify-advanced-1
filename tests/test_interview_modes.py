import unittest

from interview_modes import (
    default_bot_nicks,
    normalize_mode,
    parse_interview_event,
)


class ModeConfigurationTests(unittest.TestCase):
    def test_orp_is_a_legacy_alias_for_ops(self):
        self.assertEqual(normalize_mode('orp'), 'ops')

    def test_mode_specific_default_bots(self):
        self.assertEqual(default_bot_nicks('red'), 'Gatekeeper')
        self.assertEqual(default_bot_nicks('ops'), 'Hermes')
        self.assertEqual(default_bot_nicks('orp'), 'Hermes')


class OrpheusParserTests(unittest.TestCase):
    def test_parses_observed_queue_open_announcements(self):
        lines = [
            'Aug 01 22:13:34 <hermes>\tThe queue is now open. '
            'Interviews will start immediately.',
            'Aug 01 22:16:02 <hermes>\tThe queue is now open. '
            'Interviews will start immediately.',
        ]

        for line in lines:
            with self.subTest(line=line):
                event = parse_interview_event(line, 'ops', 'candidate')

                self.assertIsNotNone(event)
                self.assertEqual(event.notification_type, 'queue_open')

    def test_parses_observed_duplicate_wording(self):
        event = parse_interview_event(
            'Jul 22 14:01:02 -hermes-\t'
            'You have been have been invited to take your interview in #interview7.',
            'ops',
            'candidate',
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.notification_type, 'your_interview')
        self.assertEqual(event.priority, 5)
        self.assertEqual(event.username, 'candidate')
        self.assertEqual(event.interview_channel, '#interview7')

    def test_parses_corrected_wording_and_html_log_wrapper(self):
        event = parse_interview_event(
            '<span class="time">12:00</span> &lt;Hermes&gt; '
            'You have been invited to take your interview in #interview-12!',
            'orp',
            'candidate',
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.interview_channel, '#interview-12')

    def test_parsing_is_case_insensitive(self):
        event = parse_interview_event(
            'Hermes> YOU HAVE BEEN INVITED TO TAKE YOUR INTERVIEW IN #Interview_3.',
            'ops',
            'candidate',
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.interview_channel, '#Interview_3')

    def test_requires_configured_bot_when_bot_checking_is_enabled(self):
        event = parse_interview_event(
            '<SomeoneElse> You have been invited to take your interview in #interview7.',
            'ops',
            'candidate',
        )

        self.assertIsNone(event)

    def test_can_parse_client_format_without_bot_prefix_when_check_disabled(self):
        event = parse_interview_event(
            '[notice] You have been invited to take your interview in #interview7.',
            'ops',
            'candidate',
            check_bot_nicks=False,
        )

        self.assertIsNotNone(event)

    def test_ignores_queue_notices_and_generic_invitations(self):
        lines = [
            'Jul 22 13:26:20 -hermes-\t'
            'Successfully added to queue. You are at position 11.',
            'Jul 22 13:43:21 -hermes-\t'
            'You are already in the queue at position 11.',
            'Jul 22 13:45:47 -hermes-\t'
            'The queue has been closed. Please try again another time.',
            '<Hermes> You have been invited to #interview7.',
            '<Hermes> Interviews are now open.',
        ]

        for line in lines:
            with self.subTest(line=line):
                self.assertIsNone(
                    parse_interview_event(line, 'ops', 'candidate')
                )

    def test_does_not_treat_outgoing_hermes_message_as_a_bot_notice(self):
        event = parse_interview_event(
            'Jul 22 14:01:02 >Hermes<\t'
            'You have been invited to take your interview in #interview7.',
            'ops',
            'candidate',
        )

        self.assertIsNone(event)


class RedParserRegressionTests(unittest.TestCase):
    def test_detects_current_users_interview(self):
        event = parse_interview_event(
            '<Gatekeeper> Currently interviewing: Candidate '
            '::: #red-interview-01 ::: 59 remaining in queue.',
            'red',
            'candidate',
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.notification_type, 'your_interview')
        self.assertEqual(event.priority, 5)
        self.assertEqual(event.queue_length, 59)

    def test_detects_another_users_interview(self):
        event = parse_interview_event(
            'Gatekeeper> Currently interviewing: someone_else',
            'red',
            'candidate',
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.notification_type, 'interview')
        self.assertEqual(event.priority, 3)

    def test_red_still_honors_custom_bot_nicks(self):
        event = parse_interview_event(
            '<CustomBot> Currently interviewing: candidate',
            'red',
            'candidate',
            bot_nicks='CustomBot',
        )

        self.assertIsNotNone(event)


if __name__ == '__main__':
    unittest.main()
