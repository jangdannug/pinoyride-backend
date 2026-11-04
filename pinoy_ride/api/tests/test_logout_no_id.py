"""Logout with no user id is a harmless no-op (200), so a logged-out
1.1.2 app tapping Update isn't stuck on a 400."""
from types import SimpleNamespace
from django.test import SimpleTestCase
from api.views.rider_view import RiderViewSet
from api.views.customer_view import CustomerViewSet


def call(viewset, data):
    return viewset.logout(SimpleNamespace(), SimpleNamespace(data=data))


class LogoutNoIdTests(SimpleTestCase):
    def test_rider_logout_without_id_is_ok(self):
        for data in ({}, {"rider_id": ""}, {"rider_id": None}):
            self.assertEqual(call(RiderViewSet, data).status_code, 200)

    def test_customer_logout_without_id_is_ok(self):
        for data in ({}, {"customer_id": ""}, {"customer_id": None}):
            self.assertEqual(call(CustomerViewSet, data).status_code, 200)
