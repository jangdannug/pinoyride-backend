from django.test import SimpleTestCase
from api.utils.login_session import is_stale_session


class StaleSessionTests(SimpleTestCase):
    def test_not_logged_in_is_never_stale(self):
        self.assertFalse(is_stale_session(0, '1.1.0', '1.1.1'))

    def test_newer_version_marks_session_stale(self):
        self.assertTrue(is_stale_session(1, '1.1.0', '1.1.1'))

    def test_same_version_keeps_single_device_block(self):
        self.assertFalse(is_stale_session(1, '1.1.1', '1.1.1'))

    def test_older_version_keeps_block(self):
        self.assertFalse(is_stale_session(1, '1.1.1', '1.1.0'))

    def test_unknown_stored_version_is_stale(self):
        # Accounts logged in before last_app_version existed
        self.assertTrue(is_stale_session(1, None, '1.1.1'))
        self.assertTrue(is_stale_session(1, '', '1.1.1'))

    def test_missing_incoming_version_keeps_block(self):
        self.assertFalse(is_stale_session(1, '1.1.0', ''))
        self.assertFalse(is_stale_session(1, '1.1.0', None))

    def test_garbage_version_keeps_block(self):
        self.assertFalse(is_stale_session(1, '1.1.0', 'abc'))

    def test_multi_digit_parts(self):
        self.assertTrue(is_stale_session(1, '1.0.9', '1.0.10'))
