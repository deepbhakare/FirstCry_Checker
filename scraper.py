"""
scraper.py — Core scraping engine for FirstCry Tracker
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Uses Playwright (real Chromium browser) to:
  • Scrape Hot Wheels + Majorette brand listing pages
  • Scrape individual watched product pages

Stock detection logic:
  ┌─────────────────────────────────────────────────────────┐
  │  LISTING PAGES                                          │
  │  ─────────────────────────────────────────────────────  │
  │  First run      → store baseline silently (no alert)   │
  │  New product    → 🆕 NEW alert                         │
  │  OOS → in stock → 🔔 BACK IN STOCK alert               │
  │  In stock → OOS → update state silently                │
  │                                                         │
  │  WATCHED PRODUCTS                                       │
  │  ─────────────────────────────────────────────────────  │
  │  First seen + in stock  → 🔔 BACK IN STOCK alert       │
  │  First seen + OOS       → store baseline silently      │
  │  OOS → in stock         → 🔔 BACK IN STOCK alert       │
  │  In stock → OOS         → update state silently        │
  └─────────────────────────────────────────────────────────┘
"""

import hashlib
import logging
import re
import time

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
    TimeoutError as PWTimeout,
)

from config import AppConfig, LISTING_URLS, WATCH_PRODUCTS
from db import Database
from notifier import Notifier

logger = logging.getLogger(__name__)


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _make_key(value: str) -> str:
    """Produce a stable MD5 string key for any product identifier."""
    return hashlib.md5(value.strip().encode()).hexdigest()


def _extract_pid(url: str) -> str:
    """Extract the numeric FirstCry product ID from a product URL."""
    match = re.search(r'/(\d{7,})/', url)
    return match.group(1) if match else url


def _clean_price(raw: str) -> str:
    """Strip currency symbols and commas from a price string."""
    match = re.search(r'[\d,]+', raw.replace("₹", "").replace(",", ""))
    return match.group().replace(",", "") if match else ""


# ─── BROWSER FACTORY ──────────────────────────────────────────────────────────

def _launch_browser(pw: Playwright, config: AppConfig) -> tuple[Browser, Page]:
    """
    Launch a headless Chromium instance configured to avoid bot detection.
    Blocks image/font requests to reduce page load time.
    Sets Pune pincode cookie for correct stock availability.
    """
    browser = pw.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
        ],
    )

    context: BrowserContext = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        locale="en-IN",
        viewport={"width": 1366, "height": 768},
        extra_http_headers={"Accept-Language": "en-IN,en;q=0.9"},
    )

    # Pune pincode → correct stock and pricing
    context.add_cookies([{
        "name":   "fc_pincode",
        "value":  config.pincode,
        "domain": ".firstcry.com",
        "path":   "/",
    }])

    page: Page = context.new_page()

    # Block images, fonts and media — not needed, speeds up scraping
    page.route(
        "**/*.{png,jpg,jpeg,gif,webp,svg,ico,woff,woff2,ttf,otf,mp4,mp3}",
        lambda route: route.abort(),
    )

    logger.info("Browser launched ✅")
    return browser, page


# ─── LISTING PAGE SCRAPER ─────────────────────────────────────────────────────

def scrape_listing(page: Page, brand: str, url: str) -> list[dict]:
    """
    Scrape a FirstCry brand listing page for all product cards.

    Waits for the page's JS to fully render product cards before
    parsing, which avoids the empty-parse problem of plain requests.

    Falls back to link-based extraction if card selectors are not found.
    """
    products: list[dict] = []

    # ── Load page ─────────────────────────────────────────────────────────────
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_selector(
            "[data-prd-id], .product-box, .prd-info-area, a[href*='/product-detail']",
            timeout=15_000,
        )
    except PWTimeout:
        logger.warning(f"[{brand}] Page timed out waiting for products.")
        return products
    except Exception as exc:
        logger.error(f"[{brand}] Page load failed: {exc}")
        return products

    # ── Strategy 1: data-prd-id cards (preferred) ─────────────────────────────
    cards = page.query_selector_all("[data-prd-id]")

    if cards:
        for card in cards:
            try:
                pid      = card.get_attribute("data-prd-id") or ""
                name_el  = card.query_selector(".prd-info-area, [class*='product-name'], h3, h2")
                name     = (
                    name_el.inner_text().strip()
                    if name_el
                    else (card.get_attribute("data-prd-name") or "")
                )
                price_el = card.query_selector("[class*='selling-price'], [class*='prd-price'], [class*='price']")
                price    = _clean_price(price_el.inner_text()) if price_el else ""
                link_el  = card.query_selector("a[href]")
                href     = link_el.get_attribute("href") if link_el else ""
                full_url = (
                    f"https://www.firstcry.com{href}"
                    if href and href.startswith("/")
                    else (href or url)
                )
                card_text = card.inner_text().lower()
                in_stock  = (
                    "notify me"     not in card_text and
                    "out of stock"  not in card_text
                )

                if not name or not pid:
                    continue

                products.append({
                    "product_key": _make_key(pid),
                    "product_id":  pid,
                    "name":        name,
                    "url":         full_url,
                    "price":       price,
                    "brand":       brand,
                    "category":    "listing",
                    "in_stock":    in_stock,
                })
            except Exception as exc:
                logger.debug(f"  Card parse error: {exc}")

        logger.info(f"[{brand}] {len(products)} products via card strategy.")
        return products

    # ── Strategy 2: product-detail link scan (fallback) ───────────────────────
    links = page.query_selector_all("a[href*='/product-detail']")
    seen: set[str] = set()

    for link in links:
        href = link.get_attribute("href") or ""
        if href in seen or not href:
            continue
        seen.add(href)

        name = link.inner_text().strip()
        if len(name) < 5:
            continue

        full_url = f"https://www.firstcry.com{href}" if href.startswith("/") else href
        pid      = _extract_pid(full_url)

        products.append({
            "product_key": _make_key(pid),
            "product_id":  pid,
            "name":        name,
            "url":         full_url,
            "price":       "",
            "brand":       brand,
            "category":    "listing",
            "in_stock":    True,   # Can't determine from link alone
        })

    logger.info(f"[{brand}] {len(products)} products via link fallback.")
    return products


# ─── WATCHED PRODUCT SCRAPER ──────────────────────────────────────────────────

def scrape_watch_product(page: Page, label: str, url: str) -> dict | None:
    """
    Scrape an individual product page and determine its stock status.

    Stock detection priority:
      1. Button elements — most reliable (actual DOM buttons)
      2. Full page text — catches edge-case markup patterns
      3. Conservative default → treat as OOS if indeterminate
    """
    # ── Load page ─────────────────────────────────────────────────────────────
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_selector(
            "button, [class*='add-to-cart'], [class*='notify'], h1",
            timeout=15_000,
        )
    except PWTimeout:
        logger.warning(f"[WATCH] Timeout loading: {label}")
        return None
    except Exception as exc:
        logger.error(f"[WATCH] Failed to load {label}: {exc}")
        return None

    # ── Product name ──────────────────────────────────────────────────────────
    name  = label
    h1_el = page.query_selector("h1")
    if h1_el:
        h1_text = h1_el.inner_text().strip()
        if h1_text:
            name = h1_text

    # ── Price ─────────────────────────────────────────────────────────────────
    price    = ""
    price_el = page.query_selector(
        "[class*='selling-price'], [class*='final-price'], [class*='prd-price']"
    )
    if price_el:
        price = _clean_price(price_el.inner_text())

    # ── Stock status ──────────────────────────────────────────────────────────
    # Priority 1: Check actual button elements
    buttons    = page.query_selector_all("button")
    btn_texts  = [b.inner_text().strip().lower() for b in buttons if b.inner_text()]

    has_cart_btn   = any("add to cart" in t or "add to bag" in t for t in btn_texts)
    has_notify_btn = any("notify" in t for t in btn_texts)

    if has_cart_btn and not has_notify_btn:
        in_stock = True
    elif has_notify_btn and not has_cart_btn:
        in_stock = False
    else:
        # Priority 2: Full page text scan
        page_text   = page.inner_text("body").lower()
        notify_me   = bool(re.search(r'notify\s*me', page_text))
        add_to_cart = bool(re.search(r'add\s*to\s*(cart|bag)', page_text))

        if add_to_cart and not notify_me:
            in_stock = True
        elif notify_me:
            in_stock = False
        else:
            # Priority 3: Conservative default — treat as out of stock
            in_stock = False
            logger.warning(f"  ⚠️  Could not determine stock for {label} — defaulting OOS.")

    pid    = _extract_pid(url)
    status = "✅ IN STOCK" if in_stock else "❌ Out of Stock"
    logger.info(f"  {status} | {name[:60]} | ₹{price or '—'}")

    return {
        "product_key": _make_key(pid),
        "product_id":  pid,
        "name":        name,
        "url":         url,
        "price":       price,
        "brand":       "Watched",
        "category":    "watched",
        "in_stock":    in_stock,
    }


# ─── RETRY WRAPPER ────────────────────────────────────────────────────────────

def _with_retry(fn, *args, attempts: int, delay: int, **kwargs):
    """
    Call fn(*args, **kwargs) up to `attempts` times.
    Waits `delay` seconds between each attempt.
    Returns None if all attempts fail.
    """
    for attempt in range(1, attempts + 1):
        try:
            result = fn(*args, **kwargs)
            if result is not None:
                return result
            logger.warning(f"Attempt {attempt}/{attempts} returned None.")
        except Exception as exc:
            logger.warning(f"Attempt {attempt}/{attempts} raised: {exc}")
        if attempt < attempts:
            time.sleep(delay)
    logger.error(f"All {attempts} attempts failed for {fn.__name__}.")
    return None


# ─── MAIN RUN ─────────────────────────────────────────────────────────────────

def run(config: AppConfig, db: Database, notifier: Notifier) -> None:
    """
    Full scrape cycle:
      Part 1 — Brand listing pages (Hot Wheels, Majorette)
      Part 2 — Individual watched product pages

    Alerts fired:
      • 🆕  New product on listing page   (suppressed on first run)
      • 🔔  Watched car back in stock
      • 🔔  Watched car in stock on first sight
      • ⚠️  Error alert if a scrape fully fails
    """
    logger.info("=" * 60)
    logger.info("FirstCry Tracker — Run started")
    logger.info("=" * 60)

    new_products:  list[dict] = []
    back_in_stock: list[dict] = []

    # Detect first run — suppress NEW alerts to avoid spam
    is_first_run = len(db.get_all_by_category("listing")) == 0
    if is_first_run:
        logger.info("⚙️  First run — building baseline. No NEW alerts will fire.")

    with sync_playwright() as pw:
        browser, page = _launch_browser(pw, config)

        try:

            # ── Part 1: Brand listing pages ───────────────────────────────────
            for brand, url in LISTING_URLS.items():
                logger.info(f"\n[LISTING] {brand}")

                products: list[dict] = _with_retry(
                    scrape_listing, page, brand, url,
                    attempts=config.retry_attempts,
                    delay=config.retry_delay,
                ) or []

                if not products:
                    notifier.alert_error(
                        f"Listing scrape failed — {brand}",
                        Exception("No products returned after all retries."),
                    )
                    continue

                for p in products:
                    existing = db.get_product(p["product_key"])

                    if existing is None:
                        # Brand-new product on listing page
                        if not is_first_run:
                            new_products.append(p)
                            logger.info(f"  🆕 NEW: {p['name']}")
                        else:
                            logger.info(f"  📦 Baseline stored: {p['name']}")

                    elif not existing["in_stock"] and p["in_stock"]:
                        # Was out of stock — now available
                        back_in_stock.append(p)
                        logger.info(f"  🔔 BACK IN STOCK: {p['name']}")

                    elif existing["in_stock"] and not p["in_stock"]:
                        # Went out of stock — update silently
                        logger.info(f"  ❌ Now OOS: {p['name']}")

                    db.upsert_product(p)

                time.sleep(2)   # polite pause between brand pages

            # ── Part 2: Watched products ──────────────────────────────────────
            logger.info("\n[WATCHED PRODUCTS]")

            for label, url in WATCH_PRODUCTS.items():
                product: dict | None = _with_retry(
                    scrape_watch_product, page, label, url,
                    attempts=config.retry_attempts,
                    delay=config.retry_delay,
                )

                if product is None:
                    logger.warning(f"  ⚠️  Skipped after all retries: {label}")
                    continue

                existing = db.get_product(product["product_key"])

                if existing is None:
                    # First time this car has been scraped
                    if product["in_stock"]:
                        # Already available — alert immediately
                        back_in_stock.append(product)
                        logger.info(f"  🔔 FIRST SEEN + IN STOCK: {product['name']}")
                    else:
                        # Out of stock on first sight — store baseline silently
                        logger.info(f"  📦 Baseline OOS: {product['name']}")

                elif not existing["in_stock"] and product["in_stock"]:
                    # Was out of stock — now back in stock
                    back_in_stock.append(product)
                    logger.info(f"  🔔 BACK IN STOCK: {product['name']}")

                elif existing["in_stock"] and not product["in_stock"]:
                    # Went out of stock — update silently
                    logger.info(f"  ❌ Now OOS: {product['name']}")

                db.upsert_product(product)
                time.sleep(config.page_delay)

        finally:
            browser.close()
            logger.info("Browser closed.")

    # ── Fire notifications ────────────────────────────────────────────────────
    notifier.alert_new_products(new_products)
    notifier.alert_back_in_stock(back_in_stock)

    logger.info(
        f"\n{'=' * 60}\n"
        f"Run complete — "
        f"{len(new_products)} new listing(s) | "
        f"{len(back_in_stock)} back-in-stock\n"
        f"{'=' * 60}"
    )
