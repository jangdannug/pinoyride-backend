"""ETA for both legs: rider->pickup (status 1) and pickup->drop-off (status 2)."""
from unittest.mock import patch

from django.core.cache import cache
from django.utils import timezone

from api.models.booking_model import Booking
from api.models.rider_model import Rider
from api.tests.test_advance_booking_eta import Base, LNG, _eta

DROP_LAT, DROP_LNG = "14.60", "121.00"


class TripEtaTests(Base):
    def _active(self, status, arrived=False):
        b = self._booking(status=status, advance=False)
        Booking.objects.filter(id=b.id).update(
            rider=self.rider, dropoff_lat=DROP_LAT, dropoff_long=DROP_LNG,
            rider_arrived_at=timezone.now() if arrived else None)
        Rider.objects.filter(id=self.rider.id).update(current_lat="14.55", current_long=LNG,
                                                      current_location_updated_at=timezone.now())
        return b

    def test_pickup_leg_is_labelled(self):
        b = self._active(1)
        with patch("api.services.google_maps_service.GoogleMapsService.get_eta", side_effect=_eta):
            r = self.svc.get_eta(b.id, rider_id=self.rider.id)
        self.assertEqual(r["leg"], "pickup")
        self.assertEqual(r["eta_state"], "en_route")

    def test_started_ride_gives_dropoff_eta(self):
        b = self._active(2, arrived=True)
        with patch("api.services.google_maps_service.GoogleMapsService.get_eta", side_effect=_eta) as m:
            r = self.svc.get_eta(b.id, customer_id=self.customer.id)
        self.assertEqual(r["leg"], "dropoff")
        self.assertEqual(r["eta_state"], "en_route")
        self.assertEqual(r["eta_minutes"], 8)
        self.assertEqual(m.call_args[0][2:4], (float(DROP_LAT), float(DROP_LNG)))

    def test_rider_can_read_dropoff_eta(self):
        b = self._active(2, arrived=True)
        cache.clear()
        with patch("api.services.google_maps_service.GoogleMapsService.get_eta", side_effect=_eta):
            r = self.svc.get_eta(b.id, rider_id=self.rider.id)
        self.assertEqual(r["leg"], "dropoff")

    def test_done_booking_has_no_eta(self):
        b = self._active(3)
        self.assertIsNone(self.svc.get_eta(b.id, rider_id=self.rider.id)["eta_state"])
