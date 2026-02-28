"""
EdgeProp scraper — requests + __NEXT_DATA__ JSON extraction.
EdgeProp embeds listing data in <script id="__NEXT_DATA__">.
Bonus: listings include native lat/lng in the `location_p` field ("lat,lng").
"""
import json
import logging
import requests
from .base import Listing, HEADERS

logger = logging.getLogger(__name__)

# category=condo-apartment filters to only apartments/condos
BASE_URL = (
    "https://www.edgeprop.my/rent"
    "?location=kuala-lumpur"
    "&category=condo-apartment"
    "&bedrooms={n}"
    "&state=Kuala+Lumpur"
    "&page={page}"
)
LISTING_BASE = "https://www.edgeprop.my/"
MAX_PAGES = 5

# Property URL segments that indicate non-apartment listings — skip these
_EXCLUDE_TYPES = frozenset({
    "landed", "terracehouse", "bungalow", "semi-d", "semid",
    "townhouse", "shopoffice", "commercial", "office", "land",
})


def _get_url(bedrooms: int, page: int = 1) -> str:
    return BASE_URL.format(n=bedrooms, page=page)


def _parse_location_p(location_p: str):
    """Parse 'lat,lng' string into (float, float) or (None, None)."""
    try:
        parts = str(location_p).split(",")
        if len(parts) == 2:
            return float(parts[0].strip()), float(parts[1].strip())
    except Exception:
        pass
    return None, None


def _parse_listings(data: dict, bedrooms: int) -> list[Listing]:
    listings = []
    try:
        items = (
            data.get("props", {})
                .get("pageProps", {})
                .get("listData", {})
                .get("property", [])
        )
    except Exception:
        return listings

    for item in items:
        try:
            # Filter: KL only
            state = (item.get("state_s_lower", "") or "").lower()
            if state and "kuala lumpur" not in state:
                continue

            # URL — build first so we can type-check it
            url_s = item.get("url_s", "") or ""
            if url_s and not url_s.startswith("http"):
                listing_url = LISTING_BASE + url_s.lstrip("/")
            else:
                listing_url = url_s

            if not listing_url:
                continue

            # Filter: skip non-apartment property types (landed, commercial, etc.)
            url_lower = url_s.lower()
            if any(t in url_lower for t in _EXCLUDE_TYPES):
                logger.debug(f"EdgeProp: skipping non-apartment listing: {url_s}")
                continue

            title = item.get("title_t", "") or "Apartment"

            price_num = float(item.get("field_prop_asking_price_d", 0) or 0)
            price_str = f"RM {price_num:,.0f}/mo" if price_num else "Price on request"

            # Native coordinates
            location_p = item.get("location_p", "") or ""
            lat, lng = _parse_location_p(location_p)

            # Location text: combine district + state
            district = item.get("district_s_lower", "") or ""
            location_parts = [p.title() for p in [district, state] if p]
            location = ", ".join(location_parts) if location_parts else "Kuala Lumpur"

            # Image
            images = item.get("field_prop_images_txt", []) or []
            image_url = images[0] if images else ""

            listings.append(Listing(
                title=str(title),
                price=price_str,
                price_numeric=price_num,
                location=location,
                bedrooms=bedrooms,
                image_url=str(image_url),
                listing_url=listing_url,
                source="EdgeProp",
                lat=lat,
                lng=lng,
            ))
        except Exception as e:
            logger.debug(f"EdgeProp: skipped entry: {e}")

    return listings


def scrape(bedrooms: int = 1) -> list[Listing]:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("beautifulsoup4 not installed — skipping EdgeProp")
        return []

    results = []

    for page in range(1, MAX_PAGES + 1):
        url = _get_url(bedrooms, page)
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                logger.warning(f"EdgeProp page {page}: status {r.status_code}")
                break

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, "html.parser")
            script = soup.find("script", id="__NEXT_DATA__")
            if not script or not script.string:
                logger.info(f"EdgeProp page {page}: no __NEXT_DATA__ found, stopping")
                break

            data = json.loads(script.string)
            page_listings = _parse_listings(data, bedrooms)
            if not page_listings:
                logger.info(f"EdgeProp page {page}: no listings found, stopping")
                break

            results.extend(page_listings)
            logger.info(f"EdgeProp page {page}: {len(page_listings)} listings")
        except Exception as e:
            logger.error(f"EdgeProp page {page} error: {e}")
            break

    logger.info(f"EdgeProp total: {len(results)} listings")
    return results
