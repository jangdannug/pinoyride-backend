from unittest.mock import patch

from django.test import TestCase

from api.models.booking_model import Booking
from api.models.customer_model import Customer
from api.models.rider_model import Rider
from api.models.rider_vehicle_details_model import RiderVehicleDetails
from api.repositories.booking_repository import BookingRepository
from api.repositories.rider_vehicle_details_repository import RiderVehicleDetailsRepository
from api.serializers.booking_serializer import BookingSerializer
from api.services.booking_service import BookingService
from api.services.rider_vehicle_details_service import RiderVehicleDetailsService
from api.utils.custom_error import ValidationError

LAT = "14.53507"
LNG = "120.98216"


def _mock_eta(*args, **kwargs):
    return {"duration_minutes": 5, "duration_in_traffic_minutes": 5}


class BookingVehicleSnapshotTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            fname="Test",
            lname="Customer",
            mobile="9170000999",
        )
        self.rider = Rider.objects.create(
            first_name="Test",
            last_name="Rider",
            mobile_no="9170000888",
        )

    def _vehicle(self, v_type, plate, is_current=False):
        return RiderVehicleDetails.objects.create(
            rider=self.rider,
            v_type=str(v_type),
            v_brand="Brand",
            v_model="Model",
            v_color="Color",
            v_plate_number=plate,
            status=1,
            is_current=is_current,
        )

    def _pending_booking(self, booking_type):
        return Booking.objects.create(
            customer=self.customer,
            booking_type=str(booking_type),
            pickup_location="A",
            dropoff_location="B",
            pickup_lat=LAT,
            pickup_long=LNG,
            dropoff_lat=LAT,
            dropoff_long=LNG,
            payment_type="wallet",
            status=0,
        )

    @patch("api.services.google_maps_service.GoogleMapsService.get_eta", _mock_eta)
    def test_get_pending_filters_by_current_vehicle_type(self):
        moto = self._vehicle("1", "MOTO 1", is_current=True)
        self._vehicle("2", "CAR 1")
        self._pending_booking("1")
        self._pending_booking("2")

        resolved = RiderVehicleDetailsRepository.require_booking_vehicle(
            self.rider.id, booking_type="2"
        )
        self.assertEqual(resolved.id, moto.id)
        result = BookingRepository.pending_list(
            LAT, LNG, str(resolved.v_type), rider_id=self.rider.id
        )
        types = {b["booking_type"] for b in result["bookings"]}
        self.assertEqual(types, {"1"})

    @patch("api.services.google_maps_service.GoogleMapsService.get_eta", _mock_eta)
    def test_auto_book_random_pending_respects_vehicle_type(self):
        self._vehicle("1", "MOTO 2", is_current=True)
        self._pending_booking("1")
        car_booking = self._pending_booking("2")

        random_booking = BookingRepository.random_pending(LAT, LNG, "1")
        self.assertTrue(random_booking)
        self.assertNotEqual(random_booking["id"], car_booking.id)

    def test_accept_mismatch_stays_pending(self):
        self._vehicle("1", "MOTO 3", is_current=True)
        booking = self._pending_booking("2")

        with self.assertRaises(ValidationError):
            BookingRepository.accept_booking(booking_instance=booking, rider_instance=self.rider)

        booking.refresh_from_db()
        self.assertEqual(booking.status, 0)
        self.assertIsNone(booking.rider_id)

    def test_accept_match_saves_snapshot(self):
        vehicle = self._vehicle("1", "MOTO 4", is_current=True)
        booking = self._pending_booking("1")

        accepted = BookingRepository.accept_booking(
            booking_instance=booking, rider_instance=self.rider
        )
        self.assertIsNotNone(accepted)
        accepted.refresh_from_db()
        self.assertEqual(accepted.rider_vehicle_id, vehicle.id)
        self.assertEqual(accepted.vehicle_plate_number, vehicle.v_plate_number)

        data = BookingSerializer(accepted).data
        self.assertEqual(data["vehicle"]["type"], "1")
        self.assertEqual(data["vehicle"]["plate_number"], vehicle.v_plate_number)

    def test_single_type_fallback_when_no_current(self):
        vehicle = self._vehicle("2", "CAR 2", is_current=False)
        resolved = RiderVehicleDetailsRepository.resolve_booking_vehicle(
            self.rider.id, booking_type="2"
        )
        self.assertEqual(resolved.id, vehicle.id)

    def test_multiple_matches_no_current_raises(self):
        self._vehicle("2", "CAR 3", is_current=False)
        self._vehicle("2", "CAR 4", is_current=False)
        with self.assertRaises(ValidationError) as ctx:
            RiderVehicleDetailsRepository.require_booking_vehicle(self.rider.id, "2")
        self.assertIn("Set your current vehicle", str(ctx.exception))

    def test_no_vehicles_raises_add_first(self):
        with self.assertRaises(ValidationError) as ctx:
            RiderVehicleDetailsRepository.require_booking_vehicle(self.rider.id, "1")
        self.assertIn("Add a vehicle first", str(ctx.exception))

    def test_edit_delete_locked_on_open_booking(self):
        vehicle = self._vehicle("1", "MOTO 5", is_current=True)
        booking = self._pending_booking("1")
        BookingRepository.accept_booking(booking_instance=booking, rider_instance=self.rider)

        service = RiderVehicleDetailsService()
        with self.assertRaises(ValidationError):
            service.update_vehicle_by_id(
                self.rider.id,
                vehicle.id,
                {"type": "1", "brand": "X", "model": "Y", "color": "Z", "plate_number": "NEW 1"},
            )
        with self.assertRaises(ValidationError):
            service.delete_vehicle(self.rider.id, vehicle.id)

    def test_delete_allowed_after_completed_trip(self):
        vehicle = self._vehicle("1", "MOTO 6", is_current=True)
        booking = self._pending_booking("1")
        accepted = BookingRepository.accept_booking(
            booking_instance=booking, rider_instance=self.rider
        )
        accepted.status = 3
        accepted.save(update_fields=["status"])

        service = RiderVehicleDetailsService()
        self.assertTrue(service.delete_vehicle(self.rider.id, vehicle.id))

    def test_snapshot_unchanged_after_vehicle_edit(self):
        vehicle = self._vehicle("1", "MOTO 7", is_current=True)
        booking = self._pending_booking("1")
        accepted = BookingRepository.accept_booking(
            booking_instance=booking, rider_instance=self.rider
        )
        accepted.status = 3
        accepted.save(update_fields=["status"])

        vehicle.v_brand = "Changed Brand"
        vehicle.save(update_fields=["v_brand"])

        accepted.refresh_from_db()
        self.assertEqual(accepted.vehicle_brand, "Brand")

    def test_old_booking_vehicle_null_in_serializer(self):
        booking = self._pending_booking("1")
        booking.status = 3
        booking.rider = self.rider
        booking.save()
        data = BookingSerializer(booking).data
        self.assertIsNone(data["vehicle"])

    def test_set_current_vehicle_warnings_empty_without_status_five(self):
        self._vehicle("1", "MOTO 8", is_current=False)
        vehicle = self._vehicle("2", "CAR 8", is_current=False)
        service = RiderVehicleDetailsService()
        updated, warnings = service.set_current_vehicle(self.rider.id, vehicle.id)
        self.assertTrue(updated.is_current)
        self.assertEqual(warnings, [])
