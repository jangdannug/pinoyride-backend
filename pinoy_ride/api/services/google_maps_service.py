import os
import requests
import logging
from typing import Dict, List, Optional, Tuple
from api.base import ApiService
from geopy.distance import geodesic

logger = logging.getLogger('myapp')

def format_eta_minutes(minutes: int) -> str:
    """
    Format minutes into human-readable time string
    Examples:
        5 -> "5 mins"
        45 -> "45 mins"
        60 -> "1 hr"
        75 -> "1 hr 15 mins"
        120 -> "2 hrs"
        135 -> "2 hrs 15 mins"
    """
    if minutes <= 0:
        return "0 mins"

    if minutes < 60:
        return f"{minutes} min{'s' if minutes != 1 else ''}"

    hours = minutes // 60
    remaining_minutes = minutes % 60

    if remaining_minutes == 0:
        return f"{hours} hr{'s' if hours != 1 else ''}"
    else:
        return f"{hours} hr{'s' if hours != 1 else ''} {remaining_minutes} min{'s' if remaining_minutes != 1 else ''}"

class GoogleMapsService:
    """Handle Google Maps Distance Matrix API calls for ETA calculations"""

    def __init__(self):
        self.api_service = ApiService()
        self.api_key = os.getenv('SEARCH_MAP_API_KEY', 'AIzaSyAlpSoXuJzvo8uR1qbdtbbbk1sx4MHKIQk')
        self.base_url = 'https://maps.googleapis.com/maps/api/distancematrix/json'
        self.avg_speed_kmh = 30  # Average speed for Manila traffic (km/h)

    def _calculate_fallback_eta(self, distance_km: float, avg_speed_kmh: float = None) -> int:
        """
        Calculate fallback ETA using simple distance / speed formula
        Args:
            distance_km: Distance in kilometers
            avg_speed_kmh: Average speed in km/h (defaults to 30 km/h for Manila traffic)
        Returns:
            Estimated time in minutes
        """
        if avg_speed_kmh is None:
            avg_speed_kmh = self.avg_speed_kmh

        if distance_km <= 0:
            return 0

        eta_minutes = (distance_km / avg_speed_kmh) * 60
        return round(eta_minutes)

    def get_eta(self, origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float, mode: str = "driving") -> Dict:
        """
        Get ETA from origin to destination using Google Maps Distance Matrix API
        Args:
            origin_lat: Origin latitude
            origin_lng: Origin longitude
            dest_lat: Destination latitude
            dest_lng: Destination longitude
            mode: Travel mode (driving, walking, bicycling, transit)
        Returns:
            Dictionary with ETA information:
            {
                'distance_km': float,
                'duration_minutes': int,
                'duration_in_traffic_minutes': int (if available),
                'status': str,
                'using_fallback': bool
            }
        """
        origin = f"{origin_lat},{origin_lng}"
        destination = f"{dest_lat},{dest_lng}"

        params = {
            "origins": origin,
            "destinations": destination,
            "mode": mode,
            "key": self.api_key,
            "traffic_model": "best_guess",
            "departure_time": "now"
        }

        try:
            response = self.api_service.get_request(url=self.base_url, params=params)

            if response.get("status") == "OK" and response.get("rows"):
                element = response["rows"][0]["elements"][0]

                if element.get("status") == "OK":
                    distance_m = element["distance"]["value"]
                    distance_km = distance_m / 1000

                    duration_seconds = element["duration"]["value"]
                    duration_minutes = round(duration_seconds / 60)

                    result = {
                        "distance_km": round(distance_km, 2),
                        "duration_minutes": duration_minutes,
                        "status": "OK",
                        "using_fallback": False
                    }

                    # Include traffic-aware duration if available
                    if "duration_in_traffic" in element:
                        duration_traffic_seconds = element["duration_in_traffic"]["value"]
                        result["duration_in_traffic_minutes"] = round(duration_traffic_seconds / 60)

                    logger.info(f"Google Maps ETA: {origin} -> {destination}: {duration_minutes} min")
                    return result
                else:
                    logger.warning(f"Google Maps API error for element: {element.get('status')}")
            else:
                logger.warning(f"Google Maps API error: {response.get('status')}")

        except Exception as e:
            logger.error(f"Google Maps API exception: {str(e)}")

        # Fallback to simple calculation
        logger.info(f"Using fallback ETA calculation for {origin} -> {destination}")
        origin_point = (origin_lat, origin_lng)
        dest_point = (dest_lat, dest_lng)
        distance_km = geodesic(origin_point, dest_point).kilometers
        eta_minutes = self._calculate_fallback_eta(distance_km)

        return {
            "distance_km": round(distance_km, 2),
            "duration_minutes": eta_minutes,
            "status": "FALLBACK",
            "using_fallback": True
        }

    def get_multiple_etas(self, origin_lat: float, origin_lng: float, destinations: List[Tuple[float, float]], mode: str = "driving") -> List[Dict]:
        """
        Get ETAs from origin to multiple destinations (batch request)
        Google Maps allows up to 25 destinations per request
        Args:
            origin_lat: Origin latitude
            origin_lng: Origin longitude
            destinations: List of (lat, lng) tuples for destinations
            mode: Travel mode (driving, walking, bicycling, transit)
        Returns:
            List of ETA dictionaries for each destination
        """
        if not destinations:
            return []

        # Split into batches of 25 (Google Maps limit)
        batch_size = 25
        all_results = []

        for i in range(0, len(destinations), batch_size):
            batch = destinations[i:i + batch_size]

            origin = f"{origin_lat},{origin_lng}"
            dest_string = "|".join([f"{lat},{lng}" for lat, lng in batch])

            params = {
                "origins": origin,
                "destinations": dest_string,
                "mode": mode,
                "key": self.api_key,
                "traffic_model": "best_guess",
                "departure_time": "now"
            }

            try:
                response = self.api_service.get_request(url=self.base_url, params=params)

                if response.get("status") == "OK" and response.get("rows"):
                    elements = response["rows"][0]["elements"]

                    for idx, element in enumerate(elements):
                        if idx >= len(batch):
                            break

                        dest_lat, dest_lng = batch[idx]

                        if element.get("status") == "OK":
                            distance_m = element["distance"]["value"]
                            distance_km = distance_m / 1000

                            duration_seconds = element["duration"]["value"]
                            duration_minutes = round(duration_seconds / 60)

                            result = {
                                "destination_lat": dest_lat,
                                "destination_lng": dest_lng,
                                "distance_km": round(distance_km, 2),
                                "duration_minutes": duration_minutes,
                                "status": "OK",
                                "using_fallback": False
                            }

                            if "duration_in_traffic" in element:
                                duration_traffic_seconds = element["duration_in_traffic"]["value"]
                                result["duration_in_traffic_minutes"] = round(duration_traffic_seconds / 60)

                            all_results.append(result)
                        else:
                            # Fallback for failed element
                            logger.warning(f"Google Maps failed for destination {idx}: {element.get('status')}")
                            origin_point = (origin_lat, origin_lng)
                            dest_point = (dest_lat, dest_lng)
                            distance_km = geodesic(origin_point, dest_point).kilometers
                            eta_minutes = self._calculate_fallback_eta(distance_km)

                            all_results.append({
                                "destination_lat": dest_lat,
                                "destination_lng": dest_lng,
                                "distance_km": round(distance_km, 2),
                                "duration_minutes": eta_minutes,
                                "status": "FALLBACK",
                                "using_fallback": True
                            })
                else:
                    # All destinations failed, use fallback for all
                    logger.warning(f"Google Maps batch request failed: {response.get('status')}")
                    for dest_lat, dest_lng in batch:
                        origin_point = (origin_lat, origin_lng)
                        dest_point = (dest_lat, dest_lng)
                        distance_km = geodesic(origin_point, dest_point).kilometers
                        eta_minutes = self._calculate_fallback_eta(distance_km)

                        all_results.append({
                            "destination_lat": dest_lat,
                            "destination_lng": dest_lng,
                            "distance_km": round(distance_km, 2),
                            "duration_minutes": eta_minutes,
                            "status": "FALLBACK",
                            "using_fallback": True
                        })

            except Exception as e:
                logger.error(f"Google Maps batch API exception: {str(e)}")
                # Fallback for entire batch
                for dest_lat, dest_lng in batch:
                    origin_point = (origin_lat, origin_lng)
                    dest_point = (dest_lat, dest_lng)
                    distance_km = geodesic(origin_point, dest_point).kilometers
                    eta_minutes = self._calculate_fallback_eta(distance_km)

                    all_results.append({
                        "destination_lat": dest_lat,
                        "destination_lng": dest_lng,
                        "distance_km": round(distance_km, 2),
                        "duration_minutes": eta_minutes,
                        "status": "FALLBACK",
                        "using_fallback": True
                    })

        return all_results
