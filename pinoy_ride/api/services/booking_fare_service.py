"""Distance fare + Google traffic surcharge for inquire / fare recompute."""
import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional, Union

from django.utils import timezone
from geopy.distance import geodesic

from api.services.google_maps_service import GoogleMapsService, format_eta_minutes
from api.utils.custom_error import NotFoundError
from api.utils.traffic_fare_settings import traffic_cfg

logger = logging.getLogger("myapp")

# Used when no price_config row exists for booking_type (override via price_config in DB).
BOOKING_TYPE_FALLBACKS = {
    "1": {
        "km_basis": 7.0,
        "minimum_fare": 40.0,
        "pesos_per_km": 10.0,
        "pesos_per_km2": 15.0,
        "booking_fee": 0.0,
        "commission_percentage": 0.15,
    },
    "2": {
        "km_basis": 7.0,
        "minimum_fare": 80.0,
        "pesos_per_km": 22.0,
        "pesos_per_km2": 32.0,
        "booking_fee": 0.0,
        "commission_percentage": 0.15,
    },
    "3": {
        "km_basis": 7.0,
        "minimum_fare": 100.0,
        "pesos_per_km": 26.0,
        "pesos_per_km2": 38.0,
        "booking_fee": 0.0,
        "commission_percentage": 0.15,
    },
}


def clean_numeric_value(value):
    if value is None or value == "":
        return None
    cleaned = re.sub(r"[^\d.]", "", str(value))
    return float(cleaned) if cleaned else None


def traffic_surcharge_percent(duration_minutes: int, duration_in_traffic_minutes: Optional[int]) -> float:
    if not traffic_cfg("TRAFFIC_SURCHARGE_ENABLED"):
        return 0.0
    if not duration_minutes or duration_minutes <= 0:
        return 0.0
    traffic_min = duration_in_traffic_minutes if duration_in_traffic_minutes is not None else duration_minutes
    ratio = traffic_min / float(duration_minutes)
    min_ratio = float(traffic_cfg("TRAFFIC_SURCHARGE_MIN_RATIO"))
    if ratio <= min_ratio:
        return 0.0
    extra = (ratio - 1.0) * 100.0
    capped = min(max(extra, 0.0), float(traffic_cfg("TRAFFIC_SURCHARGE_MAX_PERCENT")))
    return round(capped, 2)


def _departure_time_param(dt: Optional[datetime]) -> Union[str, int]:
    if dt is None:
        return "now"
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return int(dt.timestamp())


class BookingFareService:
    def __init__(self, price_config_service, price_service, promo_service=None):
        self.price_config_service = price_config_service
        self.price_service = price_service
        self.promo_service = promo_service
        self.google_maps_service = GoogleMapsService()

    def compute_fare(
        self,
        *,
        booking_type: str,
        pickup_lat,
        pickup_long,
        dropoff_lat,
        dropoff_long,
        customer_id: str = "",
        promo_id: str = "",
        departure_at: Optional[datetime] = None,
        fare_is_estimate: bool = False,
    ) -> Dict[str, Any]:
        origin = (float(pickup_lat), float(pickup_long))
        destination = (float(dropoff_lat), float(dropoff_long))
        distance_km = geodesic(origin, destination).kilometers
        distance_km_round = round(distance_km, 2)

        default_km_basis = 7.0
        default_minimum_fare = 40.0
        default_pesos_per_km = 10.0
        default_pesos_per_km2 = 15.0
        default_booking_fee = 0.0
        default_commission_percentage = 0.15

        # Old (main) computation: minimum fare, km basis, booking fee and commission
        # per vehicle type from price_config; per-km rates from the shared price table.
        try:
            pricing_config = self.price_config_service.get_pricing_for_booking(
                str(booking_type)
            )
            km_basis = pricing_config["km_basis"]
            minimum_fare = pricing_config["minimum_fare"]
            booking_fee = pricing_config["booking_fee"]
            commission_prcentage = pricing_config["commission_percentage"]
        except NotFoundError:
            km_basis = default_km_basis
            minimum_fare = default_minimum_fare
            booking_fee = default_booking_fee
            commission_prcentage = default_commission_percentage

        latest_price = self.price_service.get_latest_price()
        if latest_price:
            pesos_per_km = clean_numeric_value(latest_price.price) or default_pesos_per_km
            pesos_per_km2 = (
                clean_numeric_value(latest_price.exceed_time_travel_price)
                or default_pesos_per_km2
            )
        else:
            pesos_per_km = default_pesos_per_km
            pesos_per_km2 = default_pesos_per_km2

        base_amount = distance_km_round * pesos_per_km
        exceeding_kms_total = 0
        exceeding_kms = 0

        if distance_km_round > km_basis:
            base_amount = km_basis * pesos_per_km
            exceeding_kms = distance_km_round - km_basis
            exceeding_kms_total = exceeding_kms * pesos_per_km2

        base_fare_before_traffic = minimum_fare + base_amount + exceeding_kms_total + booking_fee

        eta_pickup_to_dropoff = 0
        duration_minutes = 0
        duration_in_traffic_minutes = None
        traffic_pct = 0.0
        traffic_surcharge_amount = 0.0
        eta_using_fallback = False

        try:
            eta_result = self.google_maps_service.get_eta(
                origin_lat=origin[0],
                origin_lng=origin[1],
                dest_lat=destination[0],
                dest_lng=destination[1],
                mode="driving",
                departure_time=_departure_time_param(departure_at),
            )
            duration_minutes = int(eta_result.get("duration_minutes") or 0)
            duration_in_traffic_minutes = eta_result.get("duration_in_traffic_minutes")
            eta_pickup_to_dropoff = (
                duration_in_traffic_minutes
                if duration_in_traffic_minutes is not None
                else duration_minutes
            )
            eta_using_fallback = bool(eta_result.get("using_fallback"))
            traffic_pct = traffic_surcharge_percent(duration_minutes, duration_in_traffic_minutes)
            traffic_surcharge_amount = round(base_fare_before_traffic * (traffic_pct / 100.0), 2)
        except Exception as e:
            logger.error("Error calculating ETA/traffic fare: %s", e)
            eta_pickup_to_dropoff = round((distance_km_round / 30) * 60)

        total_amount_wo_promo = round(base_fare_before_traffic + traffic_surcharge_amount, 2)
        total_amount = total_amount_wo_promo
        commision = round(total_amount * commission_prcentage, 2)
        rider_net_amount = round(total_amount - commision, 2)

        promo_discount_percentage = 0
        promo_discount = 0
        if promo_id and customer_id and self.promo_service and total_amount >= 150:
            promo_details = self.promo_service.get_promo_by_id(promo_id=promo_id)
            if promo_details:
                self.promo_service.validate_promo(promo_id=promo_id, customer_id=customer_id)
                promo_discount_percentage = 0.08
                if total_amount >= 200:
                    promo_discount_percentage = 0.10
                promo_discount = round(total_amount * promo_discount_percentage, 2)
                total_amount = round(total_amount - promo_discount, 2)
                commision = round(total_amount - rider_net_amount, 2)

        payload = {
            "booking_type": str(booking_type),
            "km_basis": km_basis,
            "distance_km_round": distance_km_round,
            "exceeding_kms": exceeding_kms,
            "exceeding_kms_total": exceeding_kms_total,
            "minimum_fare": minimum_fare,
            "pesos_per_km": pesos_per_km,
            "pesos_per_km2": pesos_per_km2,
            "base_amount": round(base_amount, 2),
            "booking_fee": booking_fee,
            "base_fare_before_traffic": round(base_fare_before_traffic, 2),
            "traffic_surcharge_percent": round(traffic_pct, 2),
            "traffic_surcharge_amount": traffic_surcharge_amount,
            "promo_discount_percentage": promo_discount_percentage,
            "promo_discount": promo_discount,
            "commission": commision,
            "rider_net_amount": rider_net_amount,
            "total_amount_wo_promo": total_amount_wo_promo,
            "total_amount": round(total_amount, 2),
            "pretty_total_amount_wo_promo": f"{total_amount_wo_promo:,.2f}",
            "pretty_total_amount": f"{total_amount:,.2f}",
            "eta_pickup_to_dropoff_minutes": eta_pickup_to_dropoff,
            "pretty_eta_pickup_to_dropoff": format_eta_minutes(int(eta_pickup_to_dropoff)),
            "duration_minutes": duration_minutes,
            "duration_in_traffic_minutes": duration_in_traffic_minutes,
            "fare_is_estimate": fare_is_estimate,
            "eta_using_fallback": eta_using_fallback,
        }
        if fare_is_estimate:
            payload["estimated_total_amount"] = payload["total_amount"]
            payload["estimated_total_amount_wo_promo"] = payload["total_amount_wo_promo"]
        return payload

    def recompute_and_update_payment(
        self,
        booking,
        *,
        departure_at: Optional[datetime] = None,
        fare_is_estimate: bool = False,
    ) -> Dict[str, Any]:
        from api.models.booking_payment_model import BookingPayment

        payment = BookingPayment.objects.filter(booking_id=booking.id).first()
        if payment is None:
            raise NotFoundError("Booking payment not found")

        promo_id = ""
        details = payment.all_payment_details or {}
        if isinstance(details, dict):
            promo_id = str(details.get("promo_id") or "")

        fare = self.compute_fare(
            booking_type=str(booking.booking_type),
            pickup_lat=booking.pickup_lat,
            pickup_long=booking.pickup_long,
            dropoff_lat=booking.dropoff_lat,
            dropoff_long=booking.dropoff_long,
            customer_id=str(booking.customer_id),
            promo_id=promo_id,
            departure_at=departure_at,
            fare_is_estimate=fare_is_estimate,
        )

        merged_details = dict(details) if isinstance(details, dict) else {}
        if booking.is_advance and not merged_details.get("estimated_total_amount"):
            merged_details["estimated_total_amount"] = float(payment.total_amount or 0)
            merged_details["estimated_total_amount_wo_promo"] = float(payment.total_amount_wo_promo or 0)
        merged_details.update(fare)
        merged_details["fare_is_estimate"] = fare_is_estimate
        if booking.is_advance and merged_details.get("estimated_total_amount") is not None:
            fare["estimated_total_amount"] = merged_details["estimated_total_amount"]
            fare["estimated_total_amount_wo_promo"] = merged_details.get("estimated_total_amount_wo_promo")

        payment.minimum_fare = fare["minimum_fare"]
        payment.pesos_per_km = fare["pesos_per_km"]
        payment.booking_fee = fare["booking_fee"]
        payment.base_amount = fare["base_amount"]
        payment.distance_km_round = fare["distance_km_round"]
        payment.promo_discount = fare["promo_discount"]
        payment.total_amount_wo_promo = fare["total_amount_wo_promo"]
        payment.total_amount = fare["total_amount"]
        payment.commission = fare["commission"]
        payment.rider_net_amount = fare["rider_net_amount"]
        payment.all_payment_details = merged_details
        payment.save()
        return fare
