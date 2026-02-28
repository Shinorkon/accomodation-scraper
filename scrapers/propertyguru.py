"""
PropertyGuru scraper — uses cloudscraper to bypass Cloudflare JS challenge.
Falls back gracefully if still blocked.
"""
import re
import json
import logging
from bs4 import BeautifulSoup
from .base import Listing

logger = logging.getLogger(__name__)

BASE_URL = "https://www.propertyguru.com.my/apartment-for-rent/with-{n}-bedroom{s}"
MAX_PAGES = 5


def _get_url(bedrooms: int, page: int = 1) -> str:
    s = "" if bedrooms == 1 else "s"
    url = BASE_URL.format(n=bedrooms, s=s)
    if page > 1:
        url += f"?page={page}"
    return url


def _parse_price(price_str: str) -> float:
    digits = re.sub(r"[^\d.]", "", str(price_str))
    try:
        return float(digits)
    except ValueError:
        return 0.0


def _extract_listings(soup: BeautifulSoup, bedrooms: int) -> list[Listing]:
    listings = []

    # Primary selector confirmed via inspection
    cards = soup.select('.listing-card-v2')
    if not cards:
        # Fallback: older layout
        cards = soup.select('[da-listing-id], .listing-card, .item.listing')

    for card in cards:
        try:
            # Title from card-body title attribute: "For Rent Opus KL" → "Opus KL"
            body = card.select_one('.card-body')
            raw_title = body.get('title', '') if body else ''
            title = raw_title.replace('For Rent ', '').replace('For Rent', '').strip()
            if not title:
                title_el = card.select_one('h3, h2, [class*="title"]')
                title = title_el.get_text(strip=True) if title_el else 'Apartment'

            # Link
            link_el = card.select_one('a[href*="property-listing"]')
            if not link_el:
                continue
            listing_url = link_el.get('href', '')
            if not listing_url.startswith('http'):
                listing_url = f'https://www.propertyguru.com.my{listing_url}'

            # Price from .listing-price
            price_el = card.select_one('.listing-price')
            price_raw = price_el.get_text(strip=True) if price_el else ''
            price_num = _parse_price(price_raw)
            price_str = price_raw if price_raw else (f'RM {price_num:,.0f}/mo' if price_num else 'Price on request')

            # Address — look for the address element inside card-body
            addr_el = card.select_one('address, [da-id*="address"], [class*="address"]')
            location = addr_el.get_text(strip=True) if addr_el else 'Kuala Lumpur'

            # Image — only property photos, not agent avatars
            img_el = card.select_one('img.hui-image[src*="/listing/"]')
            if not img_el:
                img_el = card.select_one('img[src*="cdn.pgimgs.com/listing"]')
            image_url = img_el.get('src', '') if img_el else ''

            listings.append(Listing(
                title=title,
                price=price_str,
                price_numeric=price_num,
                location=location,
                bedrooms=bedrooms,
                image_url=image_url,
                listing_url=listing_url,
                source='PropertyGuru',
            ))
        except Exception as e:
            logger.debug(f'PropertyGuru: skipped card: {e}')

    return listings


def _parse_ld_item(item: dict, bedrooms: int) -> Listing | None:
    try:
        title = item.get("name", "Apartment")
        price_raw = item.get("offers", {}).get("price", 0) if isinstance(item.get("offers"), dict) else 0
        price_num = float(price_raw) if price_raw else 0.0
        price_str = f"RM {price_num:,.0f}/mo" if price_num else "Price on request"
        location = item.get("address", {}).get("addressLocality", "Kuala Lumpur") if isinstance(item.get("address"), dict) else "Kuala Lumpur"
        image_url = item.get("image", "") or ""
        if isinstance(image_url, list):
            image_url = image_url[0] if image_url else ""
        listing_url = item.get("url", "")
        return Listing(
            title=str(title),
            price=price_str,
            price_numeric=price_num,
            location=location,
            bedrooms=bedrooms,
            image_url=str(image_url),
            listing_url=str(listing_url),
            source="PropertyGuru",
        )
    except Exception as e:
        logger.debug(f"PropertyGuru LD parse error: {e}")
        return None


def scrape(bedrooms: int = 1) -> list[Listing]:
    try:
        import cloudscraper
    except ImportError:
        logger.error("cloudscraper not installed — skipping PropertyGuru")
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
                logger.warning(f"PropertyGuru: Cloudflare blocked on page {page}")
                break
            if r.status_code != 200:
                logger.warning(f"PropertyGuru page {page}: status {r.status_code}")
                break

            soup = BeautifulSoup(r.text, "html.parser")
            page_listings = _extract_listings(soup, bedrooms)
            if not page_listings:
                logger.info(f"PropertyGuru page {page}: no listings found, stopping")
                break

            results.extend(page_listings)
            logger.info(f"PropertyGuru page {page}: {len(page_listings)} listings")
        except Exception as e:
            logger.error(f"PropertyGuru page {page} error: {e}")
            break

    logger.info(f"PropertyGuru total: {len(results)} listings")
    return results
