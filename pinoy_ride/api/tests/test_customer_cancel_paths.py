"""A passenger advance cancel can't skip the fee preview via the regular status endpoint."""
from datetime import timedelta
from unittest.mock import patch

from django.test import override_settings
from rest_framework.test import APIClient

from api.models.booking_model import Booking
from api.models.booking_payment_model import BookingPayment
from api.models.pinoy_ride_wallet_history_model import PinoyRideWalletHistory
from api.models.wallet_history_model import WalletHistory
from api.services import advance_booking_service as svc_mod
from api.tests.test_advance_booking_eta import Base, _eta

STATUS_URL = '/api/booking/update_status_for_customer/'


@override_settings(CANCEL_FREE_GRACE_MINUTES=5, CANCEL_PENALTY_WINDOW_MINUTES=120)
@patch('api.services.google_maps_service.GoogleMapsService.get_eta', _eta)
class CustomerCancelPathTests(Base):
    def _b203(self):
        """Accepted advance booking, cancelled 5m22s after acceptance, pickup 1h59m away, quote 104.10."""
        b = self.svc.accept(self.rider, self._booking(hours=3, total=104.10).id)
        payment = BookingPayment.objects.get(booking=b)
        payment.all_payment_details = {'estimated_total_amount': 104.10}
        payment.save(update_fields=['all_payment_details'])
        now = b.accepted_at + timedelta(minutes=5, seconds=22)
        Booking.objects.filter(id=b.id).update(scheduled_pickup_at=now + timedelta(hours=1, minutes=59))
        return b, now

    def _status_cancel(self, b, now=None):
        body = {'booking_id': b.id, 'customer_id': self.customer.id, 'status': '4'}
        if now is None:
            return APIClient().post(STATUS_URL, body, format='json')
        with patch.object(svc_mod, '_now', return_value=now):
            return APIClient().post(STATUS_URL, body, format='json')

    def _penalty_rows(self):
        return (WalletHistory.objects.filter(tran_type='cancel_penalty').count(),
                PinoyRideWalletHistory.objects.filter(tran_type='cancel_penalty').count())

    def test_cancel_advance_endpoint_preview_then_cancel_charges_20_percent(self):
        b, now = self._b203()
        c = APIClient()
        with patch.object(svc_mod, '_now', return_value=now):
            r = c.post('/api/booking/cancel_advance/', {
                'booking_id': b.id, 'customer_id': self.customer.id, 'preview': True}, format='json')
            self.assertEqual(r.status_code, 200, r.content)
            data = r.json()['data']
            self.assertEqual((data['penalty_applies'], data['penalty_amount'], data['violation_added']),
                             (True, 20.82, 1))
            r = c.post('/api/booking/cancel_advance/', {
                'booking_id': b.id, 'customer_id': self.customer.id}, format='json')
            self.assertEqual(r.status_code, 200, r.content)
        b.refresh_from_db()
        self.assertEqual((b.status, b.cancelled_by), (4, 'customer'))
        debits = WalletHistory.objects.filter(tran_type='cancel_penalty', type='debit', wallet__user_type='customer')
        self.assertEqual([d.debit_amount for d in debits], [20.82])
        credits = PinoyRideWalletHistory.objects.filter(tran_type='cancel_penalty', type='credit')
        self.assertEqual([x.credit_amount for x in credits], [20.82])
        self.assertEqual(self.svc.violation_count('customer', self.customer.id), 1)

    def test_fee_due_advance_via_status_endpoint_is_rejected_and_unchanged(self):
        b, now = self._b203()
        r = self._status_cancel(b, now)
        self.assertEqual(r.status_code, 409, r.content)
        body = r.json()
        self.assertEqual((body['status'], body['code']), ('error', 409))
        self.assertIn('booking/cancel_advance', body['message'])
        self.assertEqual(body['data']['error_code'], 'use_cancel_advance')
        self.assertEqual(body['data']['endpoint'], 'booking/cancel_advance/')
        self.assertEqual(body['data']['booking_id'], b.id)
        self.assertEqual((body['data']['penalty_applies'], body['data']['penalty_amount']), (True, 20.82))
        b.refresh_from_db()
        self.assertEqual((b.status, b.cancelled_by, b.cancelled_at), (5, None, None))
        self.assertEqual(self._penalty_rows(), (0, 0))
        self.assertEqual(self.svc.violation_count('customer', self.customer.id), 0)

    def test_free_advance_via_status_endpoint_cancels_like_cancel_advance(self):
        cases = {
            'unaccepted': lambda: (self._booking(hours=3), None),
            'within 5:00 grace': lambda: (lambda b: (b, b.accepted_at + timedelta(minutes=4)))(
                self.svc.accept(self.rider, self._booking(hours=3).id)),
        }
        for label, make in cases.items():
            with self.subTest(label):
                b, now = make()
                r = self._status_cancel(b, now)
                self.assertEqual(r.status_code, 200, r.content)
                self.assertEqual(r.json()['data']['id'], b.id)
                b.refresh_from_db()
                self.assertEqual((b.status, b.cancelled_by), (4, 'customer'))
                self.assertIsNotNone(b.cancelled_at)
        self.assertEqual(self._penalty_rows(), (0, 0))
        self.assertEqual(self.svc.violation_count('customer', self.customer.id), 0)

    def test_free_when_pickup_two_hours_or_more_away(self):
        b = self.svc.accept(self.rider, self._booking(hours=3).id)
        r = self._status_cancel(b, b.accepted_at + timedelta(minutes=10))
        self.assertEqual(r.status_code, 200, r.content)
        b.refresh_from_db()
        self.assertEqual((b.status, b.cancelled_by), (4, 'customer'))
        self.assertEqual(self._penalty_rows(), (0, 0))

    def test_regular_non_advance_cancel_unchanged(self):
        b = self._booking(status=1, advance=False)
        Booking.objects.filter(id=b.id).update(rider=self.rider)
        r = self._status_cancel(b)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['message'], 'Booking updated successfully')
        b.refresh_from_db()
        self.assertEqual((b.status, b.cancelled_by, b.cancelled_at, b.updated_by_user), (4, None, None, 'customer'))
        self.assertEqual(self._penalty_rows(), (0, 0))
