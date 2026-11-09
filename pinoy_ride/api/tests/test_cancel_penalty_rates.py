"""Role-specific cancel penalty rates: passenger 20%, rider 10% of the quoted estimated fare."""
from datetime import timedelta
from unittest.mock import patch

from django.test import override_settings

from api.models.booking_payment_model import BookingPayment
from api.models.pinoy_ride_wallet_history_model import PinoyRideWalletHistory
from api.models.pinoy_ride_wallet_model import PinoyRideWallet
from api.models.wallet_history_model import WalletHistory
from api.models.wallet_model import Wallet
from api.services import advance_booking_service as svc_mod
from api.tests.test_advance_booking_eta import Base, _eta

# B203: cancelled 5m22s after acceptance with pickup 1h59m away, quoted fare 104.10.
B203_AFTER_ACCEPT = timedelta(minutes=5, seconds=22)
B203_PICKUP_IN = timedelta(hours=1, minutes=59)


@override_settings(CANCEL_FREE_GRACE_MINUTES=5, CANCEL_PENALTY_WINDOW_MINUTES=120,
                   RIDER_CANCEL_PENALTY_WINDOW_MINUTES=120)
@patch('api.services.google_maps_service.GoogleMapsService.get_eta', _eta)
class CancelPenaltyRateTests(Base):
    def _accepted(self, estimated, total=889.20, after=B203_AFTER_ACCEPT, pickup_in=B203_PICKUP_IN):
        b = self.svc.accept(self.rider, self._booking(hours=3, total=total).id)
        payment = BookingPayment.objects.get(booking=b)
        payment.all_payment_details = {'estimated_total_amount': estimated}
        payment.save(update_fields=['all_payment_details'])
        now = b.accepted_at + after
        b.scheduled_pickup_at = now + pickup_in
        b.save(update_fields=['scheduled_pickup_at'])
        return b, now

    def _debits(self, user_type):
        return WalletHistory.objects.filter(tran_type='cancel_penalty', type='debit', wallet__user_type=user_type)

    def _credits(self):
        return PinoyRideWalletHistory.objects.filter(tran_type='cancel_penalty', type='credit')

    def test_b203_passenger_cancel_charges_20_percent_with_matching_credit(self):
        b, now = self._accepted(104.10)
        with patch.object(svc_mod, '_now', return_value=now):
            preview = self.svc.cancel_by_customer(self.customer.id, b.id, preview=True)
            self.assertEqual((preview['penalty_amount'], preview['violation_added']), (20.82, 1))
            result = self.svc.cancel_by_customer(self.customer.id, b.id, reason='changed plans')
        self.assertEqual((result['penalty_amount'], result['violation_added']), (20.82, 1))
        self.assertEqual([d.debit_amount for d in self._debits('customer')], [20.82])
        self.assertEqual([c.credit_amount for c in self._credits()], [20.82])
        self.assertEqual(str(self._credits().get().booking_id), str(b.id))
        self.assertAlmostEqual(Wallet.objects.get(user_id=self.customer.id, user_type='customer').avail_balance,
                               -20.82, places=2)
        self.assertAlmostEqual(PinoyRideWallet.objects.get(user_id=1).avail_balance, 20.82, places=2)
        self.assertEqual(self.svc.violation_count('customer', self.customer.id), 1)
        self.assertEqual(self._debits('rider').count(), 0)

    def test_b203_rider_cancel_stays_10_percent_with_matching_credit(self):
        b, now = self._accepted(104.10)
        with patch.object(svc_mod, '_now', return_value=now):
            preview = self.svc.cancel_by_rider(self.rider, b.id, preview=True)
            self.assertEqual((preview['penalty_amount'], preview['violation_added']), (10.41, 1))
            self.svc.cancel_by_rider(self.rider, b.id, reason='flat tire')
        self.assertEqual([d.debit_amount for d in self._debits('rider')], [10.41])
        self.assertEqual([c.credit_amount for c in self._credits()], [10.41])
        self.assertAlmostEqual(PinoyRideWallet.objects.get(user_id=1).avail_balance, 10.41, places=2)
        self.assertEqual(self.svc.violation_count('rider', self.rider.id), 1)
        self.assertEqual(self._debits('customer').count(), 0)

    def test_passenger_rate_rounds_half_up_to_cents(self):
        # 104.13 x 20% = 20.826 -> 20.83; 100.025 x 20% = 20.005 is a tie -> 20.01 (not banker's 20.00).
        for estimated, passenger, rider in ((104.13, 20.83, 10.41), (100.025, 20.01, 10.0), (99.10, 19.82, 9.91)):
            with self.subTest(estimated=estimated):
                b, now = self._accepted(estimated)
                with patch.object(svc_mod, '_now', return_value=now):
                    self.assertEqual(self.svc.customer_penalty(b), (passenger, 1))
                    self.assertEqual(self.svc.rider_penalty(b), (rider, 1))

    def test_free_cases_stay_free_for_passenger(self):
        cases = {
            'within 5:00 grace': {'after': timedelta(minutes=5)},
            'pickup 120+ minutes away': {'pickup_in': timedelta(minutes=120)},
        }
        for label, kwargs in cases.items():
            with self.subTest(label):
                b, now = self._accepted(104.10, **kwargs)
                with patch.object(svc_mod, '_now', return_value=now):
                    self.assertEqual(self.svc.customer_penalty(b), (0.0, 0))
                    self.assertEqual(self.svc.rider_penalty(b), (0.0, 0))
        pending = self._booking(hours=1)
        self.assertEqual(self.svc.customer_penalty(pending), (0.0, 0))
        result = self.svc.cancel_by_customer(self.customer.id, pending.id, reason='before acceptance')
        self.assertEqual((result['penalty_amount'], result['violation_added']), (0.0, 0))
        self.assertEqual(self._credits().count(), 0)

    @override_settings(PASSENGER_CANCEL_PENALTY_PERCENT=25, RIDER_CANCEL_PENALTY_PERCENT=15)
    def test_rates_are_configured_per_role(self):
        b, now = self._accepted(100.0)
        with patch.object(svc_mod, '_now', return_value=now):
            self.assertEqual(self.svc.customer_penalty(b), (25.0, 1))
            self.assertEqual(self.svc.rider_penalty(b), (15.0, 1))
