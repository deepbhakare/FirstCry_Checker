"""
FirstCry Stock Checker — Hot Wheels & Majorette
Checks for new/in-stock items and sends Telegram + Email notifications.
Supports both listing pages AND individual product pages.
"""

import os
import json
import hashlib
import smtplib
import requests
import time
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup
from datetime import datetime

# ─── CONFIG ────────────────────────────────────────────────────────────────────
PINCODE = "411014"

# ── Listing pages (monitors entire brand pages for NEW arrivals) ──────────────
LISTING_URLS = {
    "Hot Wheels": "https://www.firstcry.com/hotwheels/5/0/113?sort=popularity&q=ard-hot%20wheels&ref2=q_ard_hot%20wheels&asid=53241",
    "Majorette":  "https://www.firstcry.com/Majorette/0/0/1335?q=as_Majorette&asid=48297",
}

# ── Individual product pages (monitors specific out-of-stock cars) ────────────
# Add any specific product URL here — bot will alert you when it comes IN STOCK.
# Format:  "Your Label": "https://www.firstcry.com/...product-detail"
WATCH_PRODUCTS = {
    "HW Ferrari F40 Competizione Red": "https://www.firstcry.com/hot-wheels/hot-wheels-ferrari-f40-competizione-198-250-toy-car-red/21965916/product-detail",

    # ↓↓ ADD MORE CARS BELOW THIS LINE ↓↓
    # "HW Bone Shaker": "https://www.firstcry.com/...product-detail",
    # "Majorette Porsche 911": "https://www.firstcry.com/...product-detail",
}

# Telegram
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

# Email (Gmail recommended — use an App Password)
EMAIL_SENDER   = os.environ.get("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER", "")

# File that stores previously-seen product IDs (committed/cached between runs)
STATE_FILE = "seen_products.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.firstcry.com/",
}

# ─── STATE MANAGEMENT ─────────────────────────────────────────────────────────

def load_seen() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}

def save_seen(data: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ─── SCRAPING ─────────────────────────────────────────────────────────────────

def product_id(product: dict) -> str:
    """Stable unique key for a product."""
    raw = (product.get("id") or product.get("url") or product.get("name", "")).strip()
    return hashlib.md5(raw.encode()).hexdigest()

def fetch_page(url: str) -> str | None:
    try:
        session = requests.Session()
        # First visit homepage to get cookies
        session.get("https://www.firstcry.com/", headers=HEADERS, timeout=15)
        # Set pincode cookie
        session.cookies.set("fc_pincode", PINCODE, domain=".firstcry.com")
        time.sleep(2)
        resp = session.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"[ERROR] Fetching {url}: {e}")
        return None


def parse_products(html: str, brand: str) -> list[dict]:
    """
    Parse product cards from FirstCry listing HTML.
    FirstCry renders products in <li> tags with class containing 'product-box'
    or inside JSON embedded in a <script> tag.
    """
    products = []

    soup = BeautifulSoup(html, "html.parser")

    # ── Strategy 1: Try to find embedded JSON (Next.js __NEXT_DATA__ or window.__INITIAL_STATE__)
    for script in soup.find_all("script"):
        text = script.string or ""
        # Look for __NEXT_DATA__ pattern
        if "__NEXT_DATA__" in text or "window.__INITIAL_STATE__" in text:
            try:
                # Extract JSON blob
                match = re.search(r'__NEXT_DATA__\s*=\s*(\{.*?\});?\s*</script>', text, re.DOTALL)
                if not match:
                    match = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;', text, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                    # Try to walk to product list — path varies
                    items = _find_products_in_json(data)
                    if items:
                        print(f"[INFO] Found {len(items)} products via embedded JSON for {brand}")
                        return items
            except Exception as e:
                print(f"[WARN] JSON parse error: {e}")

    # ── Strategy 2: HTML product cards
    # FirstCry uses various class names across versions
    card_selectors = [
        {"data-prd-id": True},       # attribute selector
    ]

    # Try data-prd-id attribute (common in FirstCry)
    cards = soup.find_all(attrs={"data-prd-id": True})
    if cards:
        for card in cards:
            pid = card.get("data-prd-id", "")
            name_el = card.find(class_=re.compile(r'product.?name|prd.?name|title', re.I))
            name = name_el.get_text(strip=True) if name_el else card.get("data-prd-name", "")
            price_el = card.find(class_=re.compile(r'price|selling.?price', re.I))
            price = price_el.get_text(strip=True) if price_el else ""
            link_el = card.find("a", href=True)
            url = "https://www.firstcry.com" + link_el["href"] if link_el and link_el["href"].startswith("/") else (link_el["href"] if link_el else "")

            # Check availability — look for "Out of Stock" text or button
            out_of_stock = bool(card.find(string=re.compile(r"out of stock|notify me", re.I)))
            in_stock = not out_of_stock

            if name or pid:
                products.append({
                    "id": pid,
                    "name": name,
                    "price": price,
                    "url": url,
                    "in_stock": in_stock,
                    "brand": brand,
                })
        if products:
            print(f"[INFO] Found {len(products)} products via HTML cards for {brand}")
            return products

    # ── Strategy 3: Generic anchor + product title pattern
    all_links = soup.find_all("a", href=re.compile(r"/[a-z0-9\-]+/\d{7,}"))
    seen_hrefs = set()
    for link in all_links:
        href = link.get("href", "")
        if href in seen_hrefs:
            continue
        seen_hrefs.add(href)
        name = link.get_text(strip=True)
        if len(name) < 5:  # skip nav/icon links
            name_el = link.find(class_=re.compile(r'name|title', re.I))
            name = name_el.get_text(strip=True) if name_el else ""
        if not name:
            continue
        full_url = "https://www.firstcry.com" + href if href.startswith("/") else href
        out_of_stock = bool(link.find_parent().find(string=re.compile(r"out of stock", re.I))) if link.find_parent() else False
        products.append({
            "id": re.search(r'/(\d{7,})', href).group(1) if re.search(r'/(\d{7,})', href) else href,
            "name": name,
            "price": "",
            "url": full_url,
            "in_stock": not out_of_stock,
            "brand": brand,
        })

    print(f"[INFO] Found {len(products)} products via link scan for {brand}")
    return products


def parse_single_product(html: str, label: str, url: str) -> dict | None:
    """
    Parse a single FirstCry product detail page.
    Detects whether the product is in stock or showing 'Notify Me'.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Extract product name from title or h1
    name = label  # fallback to the label we gave it
    h1 = soup.find("h1")
    if h1:
        name = h1.get_text(strip=True)
    elif soup.title:
        name = soup.title.string.strip()

    # Extract price
    price = ""
    price_el = soup.find(class_=re.compile(r'selling.?price|final.?price|prd.?price', re.I))
    if not price_el:
        price_el = soup.find(string=re.compile(r'₹\s*\d+'))
    if price_el:
        price_text = price_el.get_text(strip=True) if hasattr(price_el, 'get_text') else str(price_el)
        price_match = re.search(r'[\d,]+', price_text.replace('₹', ''))
        price = price_match.group().replace(',', '') if price_match else ""

    # Detect stock status — look for "Notify Me" button or "Add to Cart"
    page_text = soup.get_text()
    notify_me  = bool(re.search(r'notify\s*me', page_text, re.I))
    add_to_cart = bool(re.search(r'add\s*to\s*(cart|bag)', page_text, re.I))

    # "Add to Cart" present and "Notify Me" absent = in stock
    if add_to_cart and not notify_me:
        in_stock = True
    elif notify_me:
        in_stock = False
    else:
        # Ambiguous — check button elements specifically
        buttons = soup.find_all(["button", "a"], string=re.compile(r'notify|add to cart', re.I))
        notify_btn   = any(re.search(r'notify', b.get_text(), re.I) for b in buttons)
        addcart_btn  = any(re.search(r'add to cart', b.get_text(), re.I) for b in buttons)
        in_stock = addcart_btn and not notify_btn

    # Extract product ID from URL
    pid_match = re.search(r'/(\d{7,})/', url)
    pid = pid_match.group(1) if pid_match else url

    print(f"  → {'✅ IN STOCK' if in_stock else '❌ Out of Stock'} | {name[:60]} | ₹{price}")

    return {
        "id": pid,
        "name": name,
        "price": price,
        "url": url,
        "in_stock": in_stock,
        "brand": "Watched",
    }


def _find_products_in_json(data, depth=0) -> list:
    """Recursively hunt for a product list inside a nested JSON blob."""
    if depth > 8:
        return []
    if isinstance(data, list) and len(data) > 0:
        # Check if this looks like a product list
        first = data[0]
        if isinstance(first, dict) and any(k in first for k in ("productId", "prdId", "name", "productName", "title")):
            return [_normalize_json_product(p) for p in data if isinstance(p, dict)]
    if isinstance(data, dict):
        for key, val in data.items():
            if key in ("products", "productList", "items", "data", "results", "listing"):
                result = _find_products_in_json(val, depth + 1)
                if result:
                    return result
            else:
                result = _find_products_in_json(val, depth + 1)
                if result:
                    return result
    return []


def _normalize_json_product(p: dict) -> dict:
    pid = str(p.get("productId") or p.get("prdId") or p.get("id") or "")
    name = p.get("productName") or p.get("name") or p.get("title") or ""
    price = str(p.get("sellingPrice") or p.get("price") or p.get("mrp") or "")
    slug = p.get("productUrl") or p.get("url") or p.get("slug") or ""
    url = ("https://www.firstcry.com" + slug) if slug and not slug.startswith("http") else slug
    in_stock = p.get("inStock", True)
    if "stockStatus" in p:
        in_stock = str(p["stockStatus"]).lower() not in ("oos", "out_of_stock", "0", "false")
    return {"id": pid, "name": name, "price": price, "url": url, "in_stock": in_stock, "brand": ""}


# ─── NOTIFICATIONS ─────────────────────────────────────────────────────────────

def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[SKIP] Telegram not configured.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        print("[OK] Telegram notification sent.")
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")


def send_email(subject: str, body_html: str):
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
        print("[SKIP] Email not configured.")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECEIVER
        msg.attach(MIMEText(body_html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print("[OK] Email notification sent.")
    except Exception as e:
        print(f"[ERROR] Email: {e}")


def notify(new_products: list[dict], back_in_stock: list[dict]):
    if not new_products and not back_in_stock:
        return

    lines_tg = ["🚗 <b>FirstCry Stock Alert!</b>", f"🕐 {datetime.now().strftime('%d %b %Y, %I:%M %p')}\n"]
    lines_email = ["<h2>🚗 FirstCry Stock Alert</h2>", f"<p><i>{datetime.now().strftime('%d %b %Y, %I:%M %p')}</i></p>"]

    if new_products:
        lines_tg.append("✨ <b>NEW listings found:</b>")
        lines_email.append("<h3>✨ New Listings</h3><ul>")
        for p in new_products:
            price_str = f" — ₹{p['price']}" if p.get("price") else ""
            avail = "✅ In Stock" if p.get("in_stock") else "❌ Out of Stock"
            lines_tg.append(f"• <a href=\"{p['url']}\">{p['name']}</a>{price_str} [{avail}]")
            lines_email.append(f"<li><a href=\"{p['url']}\">{p['name']}</a>{price_str} — {avail}</li>")
        lines_email.append("</ul>")

    if back_in_stock:
        lines_tg.append("\n🔔 <b>Back in stock:</b>")
        lines_email.append("<h3>🔔 Back In Stock</h3><ul>")
        for p in back_in_stock:
            price_str = f" — ₹{p['price']}" if p.get("price") else ""
            lines_tg.append(f"• <a href=\"{p['url']}\">{p['name']}</a>{price_str}")
            lines_email.append(f"<li><a href=\"{p['url']}\">{p['name']}</a>{price_str}</li>")
        lines_email.append("</ul>")

    tg_message = "\n".join(lines_tg)
    email_html = "\n".join(lines_email)

    send_telegram(tg_message)
    send_email(
        subject=f"🚗 FirstCry Alert: {len(new_products)} new + {len(back_in_stock)} back-in-stock",
        body_html=email_html,
    )


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*60}")
    print(f"FirstCry Checker — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    seen = load_seen()
    all_new = []
    all_back = []

    # ── Part 1: Listing pages (detect new arrivals) ───────────────────────────
    for brand, url in LISTING_URLS.items():
        print(f"\n[LISTING] {brand}")
        html = fetch_page(url)
        if not html:
            print(f"  ⚠️  Could not fetch page, skipping.")
            continue

        products = parse_products(html, brand)
        if not products:
            print(f"  ⚠️  No products parsed. Site may have changed structure.")
            soup = BeautifulSoup(html, "html.parser")
            print(f"  Page title: {soup.title.string if soup.title else 'N/A'}")
            continue

        brand_seen = seen.get(brand, {})
        new_products = []
        back_in_stock = []

        for p in products:
            pid = product_id(p)
            prev = brand_seen.get(pid)

            if prev is None:
                new_products.append(p)
                brand_seen[pid] = {
                    "name": p["name"],
                    "in_stock": p["in_stock"],
                    "url": p["url"],
                    "first_seen": datetime.now().isoformat(),
                }
            elif not prev.get("in_stock") and p.get("in_stock"):
                back_in_stock.append(p)
                brand_seen[pid]["in_stock"] = True
            else:
                brand_seen[pid]["in_stock"] = p.get("in_stock", True)

        seen[brand] = brand_seen
        all_new.extend(new_products)
        all_back.extend(back_in_stock)
        print(f"  Total: {len(products)} | New: {len(new_products)} | Back in stock: {len(back_in_stock)}")
        time.sleep(2)

    # ── Part 2: Individual watched products (detect back-in-stock) ────────────
    if WATCH_PRODUCTS:
        print(f"\n[WATCHLIST] Checking {len(WATCH_PRODUCTS)} specific product(s)...")
        watch_seen = seen.get("__watchlist__", {})

        for label, url in WATCH_PRODUCTS.items():
            print(f"\n  Checking: {label}")
            html = fetch_page(url)
            if not html:
                print(f"  ⚠️  Could not fetch, skipping.")
                continue

            p = parse_single_product(html, label, url)
            if not p:
                continue

            pid = product_id(p)
            prev = watch_seen.get(pid)

            if prev is None:
                # First time seeing this — record its current status
                watch_seen[pid] = {
                    "name": p["name"],
                    "in_stock": p["in_stock"],
                    "url": url,
                    "first_seen": datetime.now().isoformat(),
                }
                # Only alert if it's ALREADY in stock on first check
                if p["in_stock"]:
                    all_back.append(p)
            elif not prev.get("in_stock") and p["in_stock"]:
                # Was out of stock — NOW in stock! 🎉
                all_back.append(p)
                watch_seen[pid]["in_stock"] = True
                print(f"  🎉 BACK IN STOCK: {label}")
            else:
                watch_seen[pid]["in_stock"] = p["in_stock"]

            time.sleep(2)

        seen["__watchlist__"] = watch_seen

    save_seen(seen)
    notify(all_new, all_back)

    if not all_new and not all_back:
        print("\n✅ No changes detected. All quiet.")
    else:
        print(f"\n🚨 Alerts sent: {len(all_new)} new listings, {len(all_back)} back-in-stock")


if __name__ == "__main__":
    main()
