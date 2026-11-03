from unittest.mock import patch
from django.test import SimpleTestCase, RequestFactory
from api.middlewares.apikeymiddleware import ApiKeyAuthenticationMiddleware

ENV = {
    'RIDER_APP_DOWNLOAD_LINK': 'https://fallback/rider',
    'RIDER_APP_IOS_DOWNLOAD_LINK': 'https://apps.apple.com/rider',
    'RIDER_APP_ANDROID_DOWNLOAD_LINK': 'https://play.google.com/rider',
    'CUSTOMER_APP_IOS_DOWNLOAD_LINK': 'https://apps.apple.com/customer',
}


class UpdateLinkTests(SimpleTestCase):
    def setUp(self):
        self.mw = ApiKeyAuthenticationMiddleware(lambda r: None)
        self.rf = RequestFactory()

    def req(self, ua):
        return self.rf.post('/api/riders/login/', HTTP_USER_AGENT=ua)

    @patch.dict('os.environ', ENV)
    def test_ios_gets_app_store(self):
        r = self.req('pinoyriderider/9 CFNetwork/1568 Darwin/24.1.0')
        self.assertEqual(self.mw.get_download_link('rider', r), 'https://apps.apple.com/rider')

    @patch.dict('os.environ', ENV)
    def test_android_gets_play_store(self):
        r = self.req('okhttp/4.9.2')
        self.assertEqual(self.mw.get_download_link('rider', r), 'https://play.google.com/rider')

    @patch.dict('os.environ', ENV)
    def test_unknown_platform_falls_back(self):
        r = self.req('curl/8.0')
        self.assertEqual(self.mw.get_download_link('rider', r), 'https://fallback/rider')

    @patch.dict('os.environ', ENV)
    def test_missing_platform_link_falls_back(self):
        r = self.req('okhttp/4.9.2')
        self.assertNotEqual(self.mw.get_download_link('customer', r), '')

    @patch.dict('os.environ', ENV)
    def test_customer_ios(self):
        r = self.req('pinoyride/3 CFNetwork/1568 Darwin/24.1.0')
        self.assertEqual(self.mw.get_download_link('customer', r), 'https://apps.apple.com/customer')

    @patch.dict('os.environ', ENV)
    def test_no_request_keeps_old_behavior(self):
        self.assertEqual(self.mw.get_download_link('rider'), 'https://fallback/rider')
