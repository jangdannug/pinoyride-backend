import json
from unittest.mock import patch
from django.http import JsonResponse
from django.test import SimpleTestCase, RequestFactory, override_settings
from api.middlewares.apikeymiddleware import ApiKeyAuthenticationMiddleware


class ApiKeyAuthenticationMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = ApiKeyAuthenticationMiddleware(
            lambda req: JsonResponse({'status': 'ok'}, status=200)
        )

    @override_settings(ENV='development', CUSTOM_API_KEY='secret-key')
    @patch.dict('os.environ', {'MIN_RIDER_APP_VERSION': '1.1.0', 'MIN_CUSTOMER_APP_VERSION': '1.1.0'})
    def test_dev_env_skips_api_key_but_enforces_426_version_check(self):
        # Rider route with outdated app_version (no X-API-KEY needed in development)
        req = self.factory.post(
            '/api/riders/login/',
            data=json.dumps({'mobile_no': '9171234567', 'app_version': '1.0.16'}),
            content_type='application/json',
        )
        res = self.middleware(req)
        self.assertEqual(res.status_code, 426)
        payload = json.loads(res.content)
        self.assertEqual(payload['code'], 426)
        self.assertTrue(payload['data']['update_required'])
        self.assertEqual(payload['data']['current_version'], '1.0.16')
        self.assertEqual(payload['data']['minimum_version'], '1.1.0')
        self.assertEqual(payload['data']['user_type'], 'rider')

    @override_settings(ENV='development', CUSTOM_API_KEY='secret-key')
    @patch.dict('os.environ', {'MIN_RIDER_APP_VERSION': '1.1.0', 'MIN_CUSTOMER_APP_VERSION': '1.1.0'})
    def test_dev_env_json_user_type_fallback_enforces_426(self):
        # Shared route (/api/otp/) relies on JSON body user_type
        req = self.factory.post(
            '/api/otp/generate-login/',
            data=json.dumps({'mobile_no': '9171234567', 'app_version': '1.0.24', 'user_type': 'rider'}),
            content_type='application/json',
        )
        res = self.middleware(req)
        self.assertEqual(res.status_code, 426)
        payload = json.loads(res.content)
        self.assertEqual(payload['data']['user_type'], 'rider')
        self.assertEqual(payload['data']['minimum_version'], '1.1.0')

    @override_settings(ENV='development', CUSTOM_API_KEY='secret-key')
    @patch.dict('os.environ', {'MIN_RIDER_APP_VERSION': '1.1.0', 'MIN_CUSTOMER_APP_VERSION': '1.1.0'})
    def test_dev_env_allows_matching_or_newer_version(self):
        req = self.factory.post(
            '/api/riders/login/',
            data=json.dumps({'mobile_no': '9171234567', 'app_version': '1.1.0'}),
            content_type='application/json',
        )
        res = self.middleware(req)
        self.assertEqual(res.status_code, 200)

    @override_settings(ENV='development', CUSTOM_API_KEY='secret-key')
    @patch.dict('os.environ', {'MIN_RIDER_APP_VERSION': '1.1.0', 'MIN_CUSTOMER_APP_VERSION': '1.1.0'})
    def test_logout_endpoints_bypass_426_version_check(self):
        for path in ('/api/riders/logout/', '/api/customers/logout/'):
            req = self.factory.post(
                path,
                data=json.dumps({'app_version': '1.0.0'}),
                content_type='application/json',
            )
            res = self.middleware(req)
            self.assertEqual(res.status_code, 200, f'{path} should bypass 426 version check')

    @override_settings(ENV='production', CUSTOM_API_KEY='secret-key')
    @patch.dict('os.environ', {'MIN_RIDER_APP_VERSION': '1.1.0'})
    def test_non_dev_env_still_enforces_api_key(self):
        req = self.factory.post(
            '/api/riders/login/',
            data=json.dumps({'mobile_no': '9171234567', 'app_version': '1.1.0'}),
            content_type='application/json',
        )
        res = self.middleware(req)
        self.assertEqual(res.status_code, 403)
