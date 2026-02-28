"""
Rentola scraper — Next.js App Router (RSC), requires Playwright headless browser.
"""
import re
import logging
from .base import Listing

logger = logging.getLogger(__name__)

BASE_URL = "https://rentola.com/for-rent/apartment/{n}-bedroom/my/kuala-lumpur"
MAX_PAGES = 3


def _get_url(bedrooms: int, page: int = 1) -> str:
    url = BASE_URL.format(n=bedrooms)
    if page > 1:
        url += f"?page={page}"
    return url


def _parse_price(text: str) -> tuple[str, float]:
    digits = re.sub(r"[^\d.]", "", text)
    try:
        n = float(digits)
        if n > 0:
            return f"RM {n:,.0f}/mo", n
    except ValueError:
        pass
    return "Price on request", 0.0


def _extract_from_html(html: str, bedrooms: int) -> list[Listing]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    listings = []
    seen_urls: set[str] = set()

    cards = soup.select(
        "article, [class*='listing'], [class*='property'], "
        "[class*='card'], [class*='result'], [class*='ad-item'], "
        "[class*='ListingCard'], [class*='PropertyCard']"
    )

    for card in cards:
        try:
            link_el = card.select_one("a[href]")
            if not link_el:
                continue
            href = link_el.get("href", "")
            listing_url = href if href.startswith("http") else f"https://rentola.com{href}"
            if listing_url in seen_urls or not href or href in ("/", "#"):
                continue
            seen_urls.add(listing_url)

            title_el = card.select_one("h2, h3, h4, [class*='title'], [class*='name'], [class*='heading']")
            title = title_el.get_text(strip=True) if title_el else "Apartment"

            price_el = card.select_one(
                "[class*='price'], [class*='Price'], [class*='rent'], "
                "[class*='amount'], [class*='cost'], [class*='Rate']"
            )
            price_str, price_num = _parse_price(price_el.get_text(strip=True)) if price_el else ("Price on request", 0.0)

            loc_el = card.select_one(
                "[class*='location'], [class*='address'], [class*='area'], "
                "[class*='Location'], address"
            )
            location = loc_el.get_text(strip=True) if loc_el else "Kuala Lumpur"

            img_el = card.select_one("img[src], img[data-src]")
            image_url = ""
            if img_el:
                image_url = img_el.get("src") or img_el.get("data-src") or ""

            listings.append(Listing(
                title=title,
                price=price_str,
                price_numeric=price_num,
                location=location,
                bedrooms=bedrooms,
                image_url=image_url,
                listing_url=listing_url,
                source="Rentola",
            ))
        except Exception as e:
            logger.debug(f"Rentola: skipped card: {e}")

    return listings


def scrape(bedrooms: int = 1) -> list[Listing]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("playwright not installed — skipping Rentola")
        return []

    results: list[Listing] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        pw_page = context.new_page()

        for page_num in range(1, MAX_PAGES + 1):
            url = _get_url(bedrooms, page_num)
            try:
                pw_page.goto(url, wait_until="networkidle", timeout=30000)
                pw_page.wait_for_timeout(2000)
                html = pw_page.content()
                page_listings = _extract_from_html(html, bedrooms)
                if not page_listings:
                    logger.info(f"Rentola page {page_num}: no listings found, stopping")
                    break
                results.extend(page_listings)
                logger.info(f"Rentola page {page_num}: {len(page_listings)} listings")
            except Exception as e:
                logger.error(f"Rentola page {page_num} error: {e}")
                break

        browser.close()

    logger.info(f"Rentola total: {len(results)} listings")
    return results
