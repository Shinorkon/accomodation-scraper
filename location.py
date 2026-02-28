import re
import math
import logging
import requests
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

GEOCODE_CACHE: dict[str, Optional[Tuple[float, float]]] = {}


def parse_google_maps_url(url: str) -> Optional[Tuple[float, float]]:
    """
    Extract (lat, lng) from a Google Maps URL.
    Handles both short links (maps.app.goo.gl) and full URLs.
    Returns None if coordinates cannot be found.
    """
    try:
        # Follow redirects to get the final URL
        r = requests.get(url, allow_redirects=True, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (compatible; accommodation-scraper/1.0)"
        })
        final_url = r.url
    except Exception as e:
        logger.warning(f"Failed to follow maps URL redirect: {e}")
        final_url = url

    # Try extracting @lat,lng from the URL
    match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', final_url)
    if match:
        return float(match.group(1)), float(match.group(2))

    # Also try ?q=lat,lng pattern
    match = re.search(r'[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)', final_url)
    if match:
        return float(match.group(1)), float(match.group(2))

    # Try ll= pattern
    match = re.search(r'[?&]ll=(-?\d+\.\d+),(-?\d+\.\d+)', final_url)
    if match:
        return float(match.group(1)), float(match.group(2))

    logger.warning(f"Could not extract coordinates from: {final_url}")
    return None


def geocode_location(location_text: str) -> Optional[Tuple[float, float]]:
    """
    Geocode a location string to (lat, lng) using Nominatim.
    Results are cached; includes 1s delay to respect rate limits.
    """
    import time

    if not location_text:
        return None

    key = location_text.strip().lower()
    if key in GEOCODE_CACHE:
        return GEOCODE_CACHE[key]

    try:
        from geopy.geocoders import Nominatim

        geocoder = Nominatim(user_agent="accommodation-scraper/1.0")
        query = location_text
        if "malaysia" not in query.lower() and "kuala lumpur" not in query.lower():
            query = f"{location_text}, Kuala Lumpur, Malaysia"

        time.sleep(1.0)  # Nominatim rate limit: 1 req/s
        result = geocoder.geocode(query, timeout=8)
        if result:
            coords = (result.latitude, result.longitude)
            GEOCODE_CACHE[key] = coords
            return coords
    except Exception as e:
        logger.warning(f"Geocode failed for '{location_text}': {e}")

    GEOCODE_CACHE[key] = None
    return None


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Compute great-circle distance in km between two lat/lng points.
    """
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
