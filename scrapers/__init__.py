"""
Runs all scrapers in parallel and merges results.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Tuple

from .base import Listing
from . import rentola, propertyguru, dotproperty, iproperty, edgeprop, mudah, starproperty

logger = logging.getLogger(__name__)

SCRAPERS = {
    "PropertyGuru": propertyguru.scrape,
    "DotProperty": dotproperty.scrape,
    "Rentola": rentola.scrape,
    "iProperty": iproperty.scrape,
    "EdgeProp": edgeprop.scrape,
    "Mudah": mudah.scrape,
    "StarProperty": starproperty.scrape,
}


def run_all_scrapers(
    bedrooms: int = 1,
    target_lat: Optional[float] = None,
    target_lng: Optional[float] = None,
    enabled: Optional[list[str]] = None,
) -> Tuple[list[dict], dict[str, str]]:
    """
    Scrape all (or selected) sites in parallel.
    If target_lat/lng provided, geocode listings and compute distances.

    Returns:
        (listings_as_dicts, errors_per_source)
    """
    from location import geocode_location, haversine_km

    active_scrapers = {
        name: fn for name, fn in SCRAPERS.items()
        if enabled is None or name in enabled
    }

    all_listings: list[Listing] = []
    errors: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=len(active_scrapers)) as executor:
        future_to_name = {
            executor.submit(fn, bedrooms): name
            for name, fn in active_scrapers.items()
        }
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                listings = future.result()
                all_listings.extend(listings)
                logger.info(f"{name}: returned {len(listings)} listings")
            except Exception as e:
                msg = str(e)
                errors[name] = msg
                logger.error(f"{name} scraper failed: {msg}")

    # Locations that are too generic to geocode meaningfully
    GENERIC_LOCATIONS = {
        "kuala lumpur", "kl", "kl city", "kuala lumpur, malaysia",
        "malaysia", "kuala lumpur kuala lumpur", "bandar kuala lumpur",
        "bandar kuala lumpur, kuala lumpur, kuala lumpur",
    }

    def is_specific_location(loc: str) -> bool:
        return loc.strip().lower() not in GENERIC_LOCATIONS

    # Geocode and compute distances if target provided
    # Cap unique geocoding calls to 40 to keep response time reasonable
    MAX_GEOCODE = 40
    geocoded_count = 0

    if target_lat is not None and target_lng is not None:
        for listing in all_listings:
            if listing.lat and listing.lng:
                listing.distance_km = haversine_km(target_lat, target_lng, listing.lat, listing.lng)
            elif listing.location and is_specific_location(listing.location):
                loc_key = listing.location.strip().lower()
                already_cached = loc_key in __import__('location').GEOCODE_CACHE
                if not already_cached and geocoded_count >= MAX_GEOCODE:
                    continue  # skip further new geocode calls
                coords = geocode_location(listing.location)
                if coords:
                    listing.lat, listing.lng = coords
                    listing.distance_km = haversine_km(target_lat, target_lng, *coords)
                if not already_cached:
                    geocoded_count += 1

    # Sort: listings with distance first (by distance), then undistanced by price
    with_dist = sorted(
        [l for l in all_listings if l.distance_km is not None],
        key=lambda l: l.distance_km
    )
    without_dist = sorted(
        [l for l in all_listings if l.distance_km is None],
        key=lambda l: l.price_numeric
    )
    sorted_listings = with_dist + without_dist

    return [l.to_dict() for l in sorted_listings], errors
