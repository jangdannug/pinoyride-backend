from django.test import TestCase, override_settings

from api.services.booking_fare_service import traffic_surcharge_percent


class TrafficSurchargePercentTests(TestCase):
    @override_settings(TRAFFIC_SURCHARGE_ENABLED=True, TRAFFIC_SURCHARGE_MAX_PERCENT=25)
    def test_no_surcharge_when_traffic_matches_baseline(self):
        self.assertEqual(traffic_surcharge_percent(30, 30), 0.0)

    @override_settings(TRAFFIC_SURCHARGE_ENABLED=True, TRAFFIC_SURCHARGE_MAX_PERCENT=25)
    def test_fifteen_percent_slower_trip(self):
        self.assertEqual(traffic_surcharge_percent(100, 115), 15.0)

    @override_settings(TRAFFIC_SURCHARGE_ENABLED=True, TRAFFIC_SURCHARGE_MAX_PERCENT=25)
    def test_capped_at_max(self):
        self.assertEqual(traffic_surcharge_percent(100, 200), 25.0)

    @override_settings(TRAFFIC_SURCHARGE_ENABLED=False)
    def test_disabled(self):
        self.assertEqual(traffic_surcharge_percent(100, 150), 0.0)
