"""
Mudah.my scraper — cloudscraper + HTML/JSON extraction.
Mudah is a classifieds site; listings may be server-rendered or embedded in JSON.
"""
import re
import json
import logging
from bs4 import BeautifulSoup
from .base import Listing

logger = logging.getLogger(__name__)

# o= is 1-indexed page number; bedrm= filters bedrooms
BASE_URL = (
    "https://www.mudah.my/kuala-lumpur/apartments-condominiums-for-rent-11"
    "?o={page}&bedrm={n}"
)
MAX_PAGES = 5


def _get_url(bedrooms: int, page: int = 1) -> str:
    return BASE_URL.format(page=page, n=bedrooms)


def _parse_price(text: str) -> float:
    digits = re.sub(r"[^\d.]", "", str(text))
    try:
        return float(digits)
    except ValueError:
        return 0.0


def _parse_json(soup: BeautifulSoup, bedrooms: int) -> list[Listing]:
    """Try __NEXT_DATA__ JSON extraction first."""
    listings = []
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return listings

    try:
        data = json.loads(script.string)
        page_props = data.get("props", {}).get("pageProps", {})
        items = (
            page_props.get("ads", []) or
            page_props.get("listings", []) or
            page_props.get("data", {}).get("ads", []) or
            page_props.get("data", {}).get("listings", [])
        )
        for item in items:
            try:
                title = item.get("title", "") or item.get("name", "") or "Apartment"
                price_num = float(item.get("price", 0) or 0)
                price_str = f"RM {price_num:,.0f}/mo" if price_num else "Price on request"
                location = (
                    item.get("region", "") or item.get("area", "") or
                    item.get("location", "") or "Kuala Lumpur"
                )
                image_url = item.get("image", "") or item.get("thumbnail", "") or ""
                if isinstance(image_url, list):
                    image_url = image_url[0] if image_url else ""
                url_path = item.get("url", "") or item.get("link", "") or ""
                if url_path and not url_path.startswith("http"):
                    listing_url = f"https://www.mudah.my{url_path}"
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
                    source="Mudah",
                ))
            except Exception as e:
                logger.debug(f"Mudah JSON item error: {e}")
    except Exception as e:
        logger.debug(f"Mudah __NEXT_DATA__ parse error: {e}")

    return listings


def _parse_html(soup: BeautifulSoup, bedrooms: int) -> list[Listing]:
    """HTML fallback parser."""
    listings = []

    cards = (
        soup.select('li[class*="listing"]') or
        soup.select('[data-qa-key*="listing"]') or
        soup.select('[class*="list-item"]') or
        soup.select("article")
    )

    for card in cards:
        try:
            link_el = card.select_one('a[href*="mudah.my"], a[href*="/property/"]')
            if not link_el:
                link_el = card.select_one("a[href]")
            if not link_el:
                continue

            url_path = link_el.get("href", "")
            if not url_path:
                continue
            listing_url = url_path if url_path.startswith("http") else f"https://www.mudah.my{url_path}"

            title_el = card.select_one("h2, h3, [class*='title'], [class*='name']")
            title = title_el.get_text(strip=True) if title_el else link_el.get_text(strip=True) or "Apartment"
            title = title[:100] or "Apartment"

            price_el = card.select_one("[class*='price']")
            price_raw = price_el.get_text(strip=True) if price_el else ""
            price_num = _parse_price(price_raw)
            price_str = (
                price_raw if (price_raw and "RM" in price_raw.upper())
                else (f"RM {price_num:,.0f}/mo" if price_num else "Price on request")
            )

            loc_el = card.select_one("[class*='location'], [class*='address'], [class*='region']")
            location = loc_el.get_text(strip=True) if loc_el else "Kuala Lumpur"
            if not location:
                location = "Kuala Lumpur"

            img_el = card.select_one("img")
            image_url = (img_el.get("data-src") or img_el.get("src", "")) if img_el else ""

            listings.append(Listing(
                title=title,
                price=price_str,
                price_numeric=price_num,
                location=location,
                bedrooms=bedrooms,
                image_url=str(image_url),
                listing_url=listing_url,
                source="Mudah",
            ))
        except Exception as e:
            logger.debug(f"Mudah: skipped card: {e}")

    return listings


def scrape(bedrooms: int = 1) -> list[Listing]:
    try:
        import cloudscraper
    except ImportError:
        logger.error("cloudscraper not installed — skipping Mudah")
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
                logger.warning(f"Mudah: blocked (403) on page {page}")
                break
            if r.status_code != 200:
                logger.warning(f"Mudah page {page}: status {r.status_code}")
                break

            soup = BeautifulSoup(r.text, "html.parser")
            page_listings = _parse_json(soup, bedrooms)
            if not page_listings:
                page_listings = _parse_html(soup, bedrooms)

            if not page_listings:
                logger.info(f"Mudah page {page}: no listings found, stopping")
                break

            results.extend(page_listings)
            logger.info(f"Mudah page {page}: {len(page_listings)} listings")
        except Exception as e:
            logger.error(f"Mudah page {page} error: {e}")
            break

    logger.info(f"Mudah total: {len(results)} listings")
    return results
