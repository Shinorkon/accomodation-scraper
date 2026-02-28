"""
iProperty scraper — cloudscraper + __NEXT_DATA__ JSON extraction.
Data is embedded in <script id="__NEXT_DATA__"> as JSON.
"""
import json
import logging
from .base import Listing

logger = logging.getLogger(__name__)

BASE_URL = "https://www.iproperty.com.my/rent/kuala-lumpur/apartment-condominium/{page}/?bedroomMin={n}&bedroomMax={n}"
MAX_PAGES = 5


def _get_url(bedrooms: int, page: int = 1) -> str:
    return BASE_URL.format(page=page, n=bedrooms)


def _parse_listings(data: dict, bedrooms: int) -> list[Listing]:
    listings = []
    try:
        items = (
            data.get("props", {})
                .get("pageProps", {})
                .get("pageData", {})
                .get("data", {})
                .get("listingsData", [])
        )
    except Exception:
        return listings

    for entry in items:
        try:
            item = entry.get("listingData", {})
            if not item:
                continue

            title = item.get("localizedTitle", "Apartment") or "Apartment"

            price_obj = item.get("price", {}) or {}
            price_num = float(price_obj.get("value", 0) or 0)
            price_str = price_obj.get("pretty", "") or ""
            if not price_str:
                price_str = f"RM {price_num:,.0f}/mo" if price_num else "Price on request"

            full_address = item.get("fullAddress", "") or ""
            additional = item.get("additionalData", {}) or {}
            area_text = additional.get("areaText", "") or additional.get("districtText", "") or ""
            location = area_text or full_address or "Kuala Lumpur"

            image_url = item.get("thumbnail", "") or ""

            listing_path = item.get("url", "") or ""
            if listing_path and not listing_path.startswith("http"):
                listing_url = f"https://www.iproperty.com.my{listing_path}"
            else:
                listing_url = listing_path

            if not listing_url:
                continue

            listings.append(Listing(
                title=str(title),
                price=price_str,
                price_numeric=price_num,
                location=str(location),
                bedrooms=bedrooms,
                image_url=str(image_url),
                listing_url=listing_url,
                source="iProperty",
            ))
        except Exception as e:
            logger.debug(f"iProperty: skipped entry: {e}")

    return listings


def scrape(bedrooms: int = 1) -> list[Listing]:
    try:
        import cloudscraper
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("cloudscraper/beautifulsoup4 not installed — skipping iProperty")
        return []

    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    results = []

    for page in range(1, MAX_PAGES + 1):
        url = _get_url(bedrooms, page)
        try:
            r = scraper.get(url, timeout=20)
            if r.status_code == 403:
                logger.warning(f"iProperty: blocked (403) on page {page}")
                break
            if r.status_code != 200:
                logger.warning(f"iProperty page {page}: status {r.status_code}")
                break

            soup = BeautifulSoup(r.text, "html.parser")
            script = soup.find("script", id="__NEXT_DATA__")
            if not script or not script.string:
                logger.info(f"iProperty page {page}: no __NEXT_DATA__ found, stopping")
                break

            data = json.loads(script.string)
            page_listings = _parse_listings(data, bedrooms)
            if not page_listings:
                logger.info(f"iProperty page {page}: no listings found, stopping")
                break

            results.extend(page_listings)
            logger.info(f"iProperty page {page}: {len(page_listings)} listings")
        except Exception as e:
            logger.error(f"iProperty page {page} error: {e}")
            break

    logger.info(f"iProperty total: {len(results)} listings")
    return results
