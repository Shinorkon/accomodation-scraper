"""
DotProperty scraper — pure client-side JS, uses Playwright headless Chromium.
"""
import re
import logging
from .base import Listing

logger = logging.getLogger(__name__)

BASE_URL = "https://www.dotproperty.com.my/apartments-for-rent/kuala-lumpur/kuala-lumpur/{n}-bedroom"
MAX_PAGES = 5


def _get_url(bedrooms: int, page: int = 1) -> str:
    url = BASE_URL.format(n=bedrooms)
    if page > 1:
        url += f"?page={page}"
    return url


def _parse_price(price_str: str) -> float:
    digits = re.sub(r"[^\d.]", "", str(price_str))
    try:
        return float(digits)
    except ValueError:
        return 0.0


def _extract_listings_from_html(html: str, bedrooms: int) -> list[Listing]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    listings = []

    # DotProperty card selectors (common patterns)
    cards = soup.select(
        ".listing-card, .property-card, [class*='PropertyCard'], "
        "[class*='listing-item'], article[class*='property'], "
        "[data-property-id], [data-id]"
    )

    for card in cards:
        try:
            # Title
            title_el = card.select_one("h2, h3, h4, [class*='title'], [class*='name']")
            title = title_el.get_text(strip=True) if title_el else "Apartment"

            # Link
            link_el = card.select_one("a[href]")
            listing_url = ""
            if link_el:
                href = link_el.get("href", "")
                listing_url = href if href.startswith("http") else f"https://www.dotproperty.com.my{href}"

            # Price
            price_el = card.select_one("[class*='price'], [class*='Price'], [data-price]")
            price_num = _parse_price(price_el.get_text()) if price_el else 0.0
            price_str = f"RM {price_num:,.0f}/mo" if price_num else "Price on request"

            # Location
            loc_el = card.select_one("[class*='location'], [class*='address'], address")
            location = loc_el.get_text(strip=True) if loc_el else "Kuala Lumpur"

            # Image
            img_el = card.select_one("img[src], img[data-src]")
            image_url = ""
            if img_el:
                image_url = img_el.get("src") or img_el.get("data-src") or ""

            if not listing_url:
                continue

            listings.append(Listing(
                title=title,
                price=price_str,
                price_numeric=price_num,
                location=location,
                bedrooms=bedrooms,
                image_url=image_url,
                listing_url=listing_url,
                source="DotProperty",
            ))
        except Exception as e:
            logger.debug(f"DotProperty: skipped card: {e}")

    return listings


def scrape(bedrooms: int = 1) -> list[Listing]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("playwright not installed — skipping DotProperty")
        return []

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        for page_num in range(1, MAX_PAGES + 1):
            url = _get_url(bedrooms, page_num)
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                # Wait for listing cards to appear
                page.wait_for_selector(
                    ".listing-card, .property-card, [data-property-id], article",
                    timeout=10000
                )
                html = page.content()
                page_listings = _extract_listings_from_html(html, bedrooms)
                if not page_listings:
                    logger.info(f"DotProperty page {page_num}: no listings, stopping")
                    break
                results.extend(page_listings)
                logger.info(f"DotProperty page {page_num}: {len(page_listings)} listings")
            except Exception as e:
                logger.error(f"DotProperty page {page_num} error: {e}")
                break

        browser.close()

    logger.info(f"DotProperty total: {len(results)} listings")
    return results
