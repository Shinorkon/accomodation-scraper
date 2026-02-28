"""
StarProperty.my scraper — cloudscraper + HTML/JSON extraction.
StarProperty is a Malaysian property portal with verified listings.
"""
import re
import json
import logging
from bs4 import BeautifulSoup
from .base import Listing

logger = logging.getLogger(__name__)

BASE_URL = (
    "https://www.starproperty.my/rent/kuala-lumpur/residential/"
    "?bedroomMin={n}&bedroomMax={n}&page={page}"
)
LISTING_BASE = "https://www.starproperty.my"
MAX_PAGES = 5


def _get_url(bedrooms: int, page: int = 1) -> str:
    return BASE_URL.format(n=bedrooms, page=page)


def _parse_price(text: str) -> float:
    digits = re.sub(r"[^\d.]", "", str(text))
    try:
        return float(digits)
    except ValueError:
        return 0.0


def _parse_json(soup: BeautifulSoup, bedrooms: int) -> list[Listing]:
    """Try __NEXT_DATA__ JSON extraction."""
    listings = []
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return listings

    try:
        data = json.loads(script.string)
        page_props = data.get("props", {}).get("pageProps", {})
        items = (
            page_props.get("listings", []) or
            page_props.get("properties", []) or
            page_props.get("data", {}).get("listings", []) or
            page_props.get("data", {}).get("properties", []) or
            page_props.get("listingData", [])
        )
        for item in items:
            try:
                title = item.get("title", "") or item.get("name", "") or "Apartment"
                price_num = float(
                    item.get("price", 0) or item.get("rental", 0) or
                    item.get("asking_price", 0) or 0
                )
                price_str = f"RM {price_num:,.0f}/mo" if price_num else "Price on request"
                location = (
                    item.get("area", "") or item.get("district", "") or
                    item.get("location", "") or item.get("address", "") or "Kuala Lumpur"
                )
                image_url = (
                    item.get("image", "") or item.get("thumbnail", "") or
                    item.get("photo", "") or item.get("cover_photo", "") or ""
                )
                if isinstance(image_url, list):
                    image_url = image_url[0] if image_url else ""
                url_path = item.get("url", "") or item.get("link", "") or item.get("slug", "")
                if url_path and not url_path.startswith("http"):
                    listing_url = f"{LISTING_BASE}{url_path}"
                else:
                    listing_url = url_path
                if not listing_url:
                    continue
                listings.append(Listing(
                    title=str(title)[:100],
                    price=price_str,
                    price_numeric=price_num,
                    location=str(location),
                    bedrooms=bedrooms,
                    image_url=str(image_url),
                    listing_url=listing_url,
                    source="StarProperty",
                ))
            except Exception as e:
                logger.debug(f"StarProperty JSON item error: {e}")
    except Exception as e:
        logger.debug(f"StarProperty __NEXT_DATA__ parse error: {e}")

    return listings


def _parse_html(soup: BeautifulSoup, bedrooms: int) -> list[Listing]:
    """HTML fallback parser."""
    listings = []

    cards = (
        soup.select("[class*='listing-card']") or
        soup.select("[class*='property-card']") or
        soup.select("[class*='listing-item']") or
        soup.select("article")
    )

    for card in cards:
        try:
            link_el = card.select_one("a[href]")
            if not link_el:
                continue
            url_path = link_el.get("href", "")
            if not url_path:
                continue
            listing_url = url_path if url_path.startswith("http") else f"{LISTING_BASE}{url_path}"

            title_el = card.select_one("h2, h3, h4, [class*='title']")
            title = (title_el.get_text(strip=True) if title_el else "Apartment") or "Apartment"

            price_el = card.select_one("[class*='price']")
            price_raw = price_el.get_text(strip=True) if price_el else ""
            price_num = _parse_price(price_raw)
            price_str = (
                price_raw if (price_raw and "RM" in price_raw.upper())
                else (f"RM {price_num:,.0f}/mo" if price_num else "Price on request")
            )

            loc_el = card.select_one("[class*='location'], [class*='address'], [class*='area']")
            location = loc_el.get_text(strip=True) if loc_el else "Kuala Lumpur"
            if not location:
                location = "Kuala Lumpur"

            img_el = card.select_one("img")
            image_url = (img_el.get("data-src") or img_el.get("src", "")) if img_el else ""

            listings.append(Listing(
                title=title[:100],
                price=price_str,
                price_numeric=price_num,
                location=location,
                bedrooms=bedrooms,
                image_url=str(image_url),
                listing_url=listing_url,
                source="StarProperty",
            ))
        except Exception as e:
            logger.debug(f"StarProperty: skipped card: {e}")

    return listings


def scrape(bedrooms: int = 1) -> list[Listing]:
    try:
        import cloudscraper
    except ImportError:
        logger.error("cloudscraper not installed — skipping StarProperty")
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
                logger.warning(f"StarProperty: blocked (403) on page {page}")
                break
            if r.status_code != 200:
                logger.warning(f"StarProperty page {page}: status {r.status_code}")
                break

            soup = BeautifulSoup(r.text, "html.parser")
            page_listings = _parse_json(soup, bedrooms)
            if not page_listings:
                page_listings = _parse_html(soup, bedrooms)

            if not page_listings:
                logger.info(f"StarProperty page {page}: no listings found, stopping")
                break

            results.extend(page_listings)
            logger.info(f"StarProperty page {page}: {len(page_listings)} listings")
        except Exception as e:
            logger.error(f"StarProperty page {page} error: {e}")
            break

    logger.info(f"StarProperty total: {len(results)} listings")
    return results
