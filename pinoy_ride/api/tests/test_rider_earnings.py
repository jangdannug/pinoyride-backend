from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from api.services import rider_earnings_service as svc
from api.utils.custom_error import ValidationError

T = datetime(2026, 10, 22, 12, 0, tzinfo=svc.MANILA)


def _pay(total, net, commission, minimum=50, fee=10):
    return SimpleNamespace(total_amount=total, rider_net_amount=net, commission=commission,
                           minimum_fare=minimum, booking_fee=fee,
                           all_payment_details={"minimum_fare": minimum, "booking_fee": fee,
                                                "base_amount": total - minimum - fee,
                                                "commission": commission, "rider_net_amount": net,
                                                "pretty_eta_pickup_to_dropoff": "5 mins"})


def _b(i, minutes=0):
    return SimpleNamespace(id=i, ref_code=f"R{i}", booking_type="1", vehicle_type="Motorcycle",
                           pickup_location="A", dropoff_location="Santa Rosa City Hall",
                           distance_km="3", completed_at=T + timedelta(minutes=minutes), updated_at=T)


class PeriodTests(SimpleTestCase):
    def test_daily(self):
        s, e = svc.resolve_period("2026-10-22")
        self.assertEqual((s.day, (e - s).days), (22, 1))

    def test_daily_mdy(self):
        self.assertEqual(svc.resolve_period("10-22-2026")[0].month, 10)

    def test_monthly(self):
        s, e = svc.resolve_period(month=2, year=2028)
        self.assertEqual((e - s).days, 29)

    def test_invalid(self):
        for args in [("bad",), (None, 13, 2026), ()]:
            with self.assertRaises(ValidationError):
                svc.resolve_period(*args)


class SummaryTests(SimpleTestCase):
    def setUp(self):
        self.b1, self.b2, self.b3 = _b(1, 10), _b(2, 30), _b(3)
        self.pays = {1: _pay(70, 60, 10), 2: _pay(90, 80, 10), 3: _pay(100, 90, 10)}
        self.pen = SimpleNamespace(id=9, booking_id="3", debit_amount=10.0, description="Cancel penalty|Ref-R3",
                                   created_at=T + timedelta(minutes=60))

    def _run(self):
        return svc.summarize(svc.build_items([self.b1, self.b2], self.pays, [self.pen],
                                             {"1": self.b1, "2": self.b2, "3": self.b3}))

    def test_total_is_net_trip_earnings_without_deductions(self):
        r = self._run()
        self.assertEqual(r["total_earning"], 140.0)   # 60 + 80, penalty not subtracted
        self.assertEqual(r["trip_count"], 2)
        self.assertEqual(r["deduction_total"], 10.0)

    def test_items_newest_first_with_breakdown(self):
        items = self._run()["items"]
        self.assertEqual([i["id"] for i in items], ["w-9", "b-2", "b-1"])
        self.assertEqual(items[0]["kind"], "deduction")
        self.assertEqual(items[0]["total_amount"], 100.0)
        e = items[2]
        self.assertEqual((e["minimum_fare"], e["distance_fare"], e["booking_fee"], e["total_amount"], e["amount"]),
                         (50.0, 10.0, 10.0, 70.0, 60.0))

    def test_missing_net_falls_back_to_total_minus_commission(self):
        p = _pay(70, None, 10)
        p.all_payment_details.pop("rider_net_amount")
        self.assertEqual(svc._fare_lines(p)["rider_net_amount"], 60.0)

    def test_requires_rider(self):
        with self.assertRaises(ValidationError):
            svc.RiderEarningsService().get_earnings(rider_id="", date_str="2026-10-22")
