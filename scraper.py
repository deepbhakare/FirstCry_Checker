"""
FirstCry Stock Checker — Hot Wheels & Majorette
Checks for new/in-stock items and sends Telegram + Email notifications.
Supports both listing pages AND individual product pages.

OPTIMISATIONS APPLIED:
  FIX 1 — sleep(1) instead of sleep(2) between requests
  FIX 2 — Homepage fetched ONCE, single session reused for all requests
  FIX 3 — timeout=10 on all requests (was 20) — prevents hung runs
  FIX 4 — GitHub Actions job timeout set in main.yml (timeout-minutes: 10)
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
# Bot alerts you the moment any of these show "Add to Cart" instead of "Notify Me"
# Format: "Your Label": "https://www.firstcry.com/...product-detail"
WATCH_PRODUCTS = {
    # ── Hot Wheels ──────────────────────────────────────────────────────────────
    "HW Ferrari F40 Competizione Red":       "https://www.firstcry.com/hot-wheels/hot-wheels-ferrari-f40-competizione-198-250-toy-car-red/21965916/product-detail",
    "HW McLaren Formula 1 Team 4":           "https://www.firstcry.com/hot-wheels/hot-wheels-mclaren-formula-1-team-4-formula-one-premium-die-cast-car-anthracite-black-and-yellow/22115543/product-detail",
    "HW Mercedes-Benz 300 SEL 6.8 AMG":     "https://www.firstcry.com/hot-wheels/hot-wheels-mercedes-benz-300-sel-6-8-amg-die-cast-toy-car-black/22140896/product-detail",
    "HW Honda Civic Custom STSTH":           "https://www.firstcry.com/hot-wheels/hot-wheels-73-honda-civic-custom-personnalise-car-231-250-maroon/22140905/product-detail",
    "HW Nissan 35GT RR Ver 2":               "https://www.firstcry.com/hot-wheels/hot-wheels-die-cast-lb-silhouette-works-gt-nissan-35gt-rr-ver-2-car-toy-silver/22140906/product-detail",
    "HW Mercedes-AMG Petronas F1 Team":      "https://www.firstcry.com/hot-wheels/hot-wheels-premium-2025-mercedes-amg-petronas-f1-team-car-black-and-green/22157119/product-detail",
    "HW Visa Cash App Racing Bulls F1":      "https://www.firstcry.com/hot-wheels/hot-wheels-premium-2025-visa-cash-app-racing-bulls-f1-team-car-black-and-white/22157138/product-detail",
    "HW Ferrari Team Transport":             "https://www.firstcry.com/hot-wheels/hot-wheels-second-story-lorry-die-cast-free-wheel-car-transport-truck-red/22159210/product-detail",
    "HW Ford Mustang Dark Horse":            "https://www.firstcry.com/hot-wheels/hot-wheels-ford-mustang-dark-horse-250-250-die-cast-toy-car-blue/22178581/product-detail",
    "HW Toyota Supra 232-250":               "https://www.firstcry.com/hot-wheels/hot-wheels-toyota-supra-232-250-die-cast-toy-car-green/22178925/product-detail",
    "HW McLaren P1":                         "https://www.firstcry.com/hot-wheels/hot-wheels-mclaren-p1-165-250-die-cast-toy-car-maroon/22179292/product-detail",
    "HW McLaren F1":                         "https://www.firstcry.com/hot-wheels/hot-wheels-mclaren-f1-243-250-die-cast-toy-car-red/22189703/product-detail",
    "HW STH Ford Sierra Cosworth":           "https://www.firstcry.com/hot-wheels/hot-wheels-87-ford-sierra-cosworth-116-250-toy-car-dark-pink/22240154/product-detail",
    "HW Ferrari F40 Competizione Black":     "https://www.firstcry.com/hot-wheels/hot-wheels-ferrari-f40-competizione-63-250-toy-car-black/22240147/product-detail",
    "HW Visa Cash App RB F1 68-250":         "https://www.firstcry.com/hot-wheels/hot-wheels-visa-cash-app-racing-bulls-formula-1-team-equipe-68-250-toy-car-white-and-black/22240176/product-detail",
    "HW Lamborghini Huracan Coupe":          "https://www.firstcry.com/hot-wheels/hot-wheels-lb-works-lamborghini-huracan-coupe-91-250-toy-car-black/22240182/product-detail",

    # ── Majorette ───────────────────────────────────────────────────────────────
    "Majorette Porsche 911 GT3 Cup":         "https://www.firstcry.com/majorette/majorette-1-64-scale-porsche-911-gt3-cup-edition-free-wheel-die-cast-car-green/19931378/product-detail",
    "Majorette Porsche 911 Carrera RS Black":"https://www.firstcry.com/majorette/majorette-porsche-racing-die-cast-free-wheel-model-toy-car-black/19991405/product-detail",
    "CHASE Majorette Ford F-150 Raptor":     "https://www.firstcry.com/majorette/majorette-ford-f-150-raptor-showroom-premium-die-cast-car-blue/22063291/product-detail",
    "Majorette BMW M3 Green":                "https://www.firstcry.com/majorette/majorette-bmw-m3-showroom-premium-die-cast-car-green/22063292/product-detail",
    "Majorette Aston Martin Vantage GTB":    "https://www.firstcry.com/majorette/majorette-aston-martin-vantage-gtb-showroom-premium-die-cast-car-white/22063293/product-detail",
    "Majorette Land Rover Defender 90":      "https://www.firstcry.com/majorette/majorette-land-rover-defender-90-showroom-premium-die-cast-car-silver/22063301/product-detail",
    "Majorette Lamborghini Huracan Avio":    "https://www.firstcry.com/majorette/majorette-lamborghini-huracan-avio-showroom-premium-die-cast-car-black/22063303/product-detail",
    "Majorette Toyota Supra JZA80 JDM":      "https://www.firstcry.com/majorette/majorette-toyota-supra-jzabo-jdm-legends-deluxe-die-cast-toy-car-royal-blue-and-lime-green/22063306/product-detail",
    "CHASE Majorette Nissan Cefiro A31":     "https://www.firstcry.com/majorette/majorette-nissan-cefiro-a31-jdm-legends-deluxe-die-cast-car-dark-pink/22063307/product-detail",
    "Majorette Porsche 911 Carrera RS Blue": "https://www.firstcry.com/majorette/majorette-porsche-911-carrera-rs-2-7-castheads-premium-die-cast-free-wheel-moving-cars-light-blue/22064343/product-detail",
    "Majorette Toyota Century JDM":          "https://www.firstcry.com/majorette/majorette-toyota-century-jdm-legends-premium-die-cast-car-grey/22064404/product-detail",
    "Majorette BMW M3 Vintage Black":        "https://www.firstcry.com/majorette/majorette-bmw-m3-vintage-premium-die-cast-car-black/22064424/product-detail",
    "Majorette Mercedes 450 SEL Vintage":    "https://www.firstcry.com/majorette/majorette-mercedes-benz-450-sel-vintage-premium-die-cast-car-light-green/22064428/product-detail",
    "Majorette Aston Martin CHROME Vantage": "https://www.firstcry.com/majorette/majorette-aston-martin-vantage-gtb-showroom-deluxe-die-cast-car-green/22069192/product-detail",

    # ── ADD MORE CARS BELOW THIS LINE ───────────────────────────────────────────
    # "HW Car Name": "https://www.firstcry.com/...product-detail",
    # "Majorette Car Name": "https://www.firstcry.com/...product-detail",
}

# ─── CREDENTIALS (from GitHub Secrets) ────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
EMAIL_SENDER       = os.environ.get("EMAIL_SENDER", "")
EMAIL_PASSWORD     = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_RECEIVER     = os.environ.get("EMAIL_RECEIVER", "")

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

# ─── SESSION — FIX 2: homepage fetched ONCE, reused for all requests ──────────

def create_session() -> requests.Session:
    session = requests.Session()
    try:
        session.get("https://www.firstcry.com/", headers=HEADERS, timeout=10)
        session.cookies.set("fc_pincode", PINCODE, domain=".firstcry.com")
        print("[SESSION] Initialised ✅")
    except Exception as e:
        print(f"[SESSION] Warning: {e}")
    return session

# ─── FETCH ────────────────────────────────────────────────────────────────────

def fetch_page(url: str, session: requests.Session) -> str | None:
    try:
        resp = session.get(url, headers=HEADERS, timeout=10)  # FIX 3
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"[ERROR] {url}: {e}")
        return None

# ─── LISTING PAGE PARSER ──────────────────────────────────────────────────────

def parse_products(html: str, brand: str) -> list[dict]:
    products = []
    soup = BeautifulSoup(html, "html.parser")

    # Strategy 1: Embedded JSON
    for script in soup.find_all("script"):
        text = script.string or ""
        if "__NEXT_DATA__" in text or "window.__INITIAL_STATE__" in text:
            try:
                match = re.search(r'__NEXT_DATA__\s*=\s*(\{.*?\});?\s*</script>', text, re.DOTALL)
                if not match:
                    match = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;', text, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                    items = _find_products_in_json(data)
                    if items:
                        print(f"  Found {len(items)} products via embedded JSON")
                        return items
            except Exception as e:
                print(f"  [WARN] JSON: {e}")

    # Strategy 2: HTML cards
    cards = soup.find_all(attrs={"data-prd-id": True})
    if cards:
        for card in cards:
            pid      = card.get("data-prd-id", "")
            name_el  = card.find(class_=re.compile(r'product.?name|prd.?name|title', re.I))
            name     = name_el.get_text(strip=True) if name_el else card.get("data-prd-name", "")
            price_el = card.find(class_=re.compile(r'price|selling.?price', re.I))
            price    = price_el.get_text(strip=True) if price_el else ""
            link_el  = card.find("a", href=True)
            url      = ("https://www.firstcry.com" + link_el["href"]) if link_el and link_el["href"].startswith("/") else (link_el["href"] if link_el else "")
            in_stock = not bool(card.find(string=re.compile(r"out of stock|notify me", re.I)))
            if name or pid:
                products.append({"id": pid, "name": name, "price": price, "url": url, "in_stock": in_stock, "brand": brand})
        if products:
            print(f"  Found {len(products)} products via HTML cards")
            return products

    # Strategy 3: Link scan
    seen_hrefs = set()
    for link in soup.find_all("a", href=re.compile(r"/[a-z0-9\-]+/\d{7,}")):
        href = link.get("href", "")
        if href in seen_hrefs:
            continue
        seen_hrefs.add(href)
        name = link.get_text(strip=True)
        if len(name) < 5:
            name_el = link.find(class_=re.compile(r'name|title', re.I))
            name = name_el.get_text(strip=True) if name_el else ""
        if not name:
            continue
        full_url = "https://www.firstcry.com" + href if href.startswith("/") else href
        parent = link.find_parent()
        out_of_stock = bool(parent.find(string=re.compile(r"out of stock", re.I))) if parent else False
        pid_match = re.search(r'/(\d{7,})', href)
        products.append({"id": pid_match.group(1) if pid_match else href, "name": name, "price": "", "url": full_url, "in_stock": not out_of_stock, "brand": brand})

    print(f"  Found {len(products)} products via link scan")
    return products

# ─── SINGLE PRODUCT PAGE PARSER ───────────────────────────────────────────────

def parse_single_product(html: str, label: str, url: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")

    name = label
    h1 = soup.find("h1")
    if h1:
        name = h1.get_text(strip=True)
    elif soup.title and soup.title.string:
        name = soup.title.string.strip()

    price = ""
    price_el = soup.find(class_=re.compile(r'selling.?price|final.?price|prd.?price', re.I))
    if not price_el:
        price_el = soup.find(string=re.compile(r'₹\s*\d+'))
    if price_el:
        price_text = price_el.get_text(strip=True) if hasattr(price_el, 'get_text') else str(price_el)
        m = re.search(r'[\d,]+', price_text.replace('₹', ''))
        price = m.group().replace(',', '') if m else ""

    page_text   = soup.get_text()
    notify_me   = bool(re.search(r'notify\s*me', page_text, re.I))
    add_to_cart = bool(re.search(r'add\s*to\s*(cart|bag)', page_text, re.I))

    if add_to_cart and not notify_me:
        in_stock = True
    elif notify_me:
        in_stock = False
    else:
        buttons    = soup.find_all(["button", "a"], string=re.compile(r'notify|add to cart', re.I))
        notify_btn = any(re.search(r'notify', b.get_text(), re.I) for b in buttons)
        cart_btn   = any(re.search(r'add to cart', b.get_text(), re.I) for b in buttons)
        in_stock   = cart_btn and not notify_btn

    pid_match = re.search(r'/(\d{7,})/', url)
    pid = pid_match.group(1) if pid_match else url

    print(f"  {'✅ IN STOCK' if in_stock else '❌ Out of Stock'} | {name[:55]} | ₹{price}")
    return {"id": pid, "name": name, "price": price, "url": url, "in_stock": in_stock, "brand": "Watched"}

# ─── JSON HELPERS ─────────────────────────────────────────────────────────────

def _find_products_in_json(data, depth=0) -> list:
    if depth > 8:
        return []
    if isinstance(data, list) and len(data) > 0:
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
    pid   = str(p.get("productId") or p.get("prdId") or p.get("id") or "")
    name  = p.get("productName") or p.get("name") or p.get("title") or ""
    price = str(p.get("sellingPrice") or p.get("price") or p.get("mrp") or "")
    slug  = p.get("productUrl") or p.get("url") or p.get("slug") or ""
    url   = ("https://www.firstcry.com" + slug) if slug and not slug.startswith("http") else slug
    in_stock = p.get("inStock", True)
    if "stockStatus" in p:
        in_stock = str(p["stockStatus"]).lower() not in ("oos", "out_of_stock", "0", "false")
    return {"id": pid, "name": name, "price": price, "url": url, "in_stock": in_stock, "brand": ""}

def product_id(product: dict) -> str:
    raw = (product.get("id") or product.get("url") or product.get("name", "")).strip()
    return hashlib.md5(raw.encode()).hexdigest()

# ─── NOTIFICATIONS ─────────────────────────────────────────────────────────────

def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[SKIP] Telegram not configured.")
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML", "disable_web_page_preview": False},
            timeout=10,
        )
        r.raise_for_status()
        print("[OK] Telegram sent ✅")
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")

def send_email(subject: str, body_html: str):
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
        print("[SKIP] Email not configured.")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = EMAIL_SENDER
        msg["To"]      = EMAIL_RECEIVER
        msg.attach(MIMEText(body_html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print("[OK] Email sent ✅")
    except Exception as e:
        print(f"[ERROR] Email: {e}")

def notify(new_products: list[dict], back_in_stock: list[dict]):
    if not new_products and not back_in_stock:
        return

    ts = datetime.now().strftime('%d %b %Y, %I:%M %p')
    lines_tg    = [f"🚗 <b>FirstCry Stock Alert!</b>", f"🕐 {ts}\n"]
    lines_email = [f"<h2>🚗 FirstCry Stock Alert</h2><p><i>{ts}</i></p>"]

    if new_products:
        lines_tg.append("✨ <b>NEW listings found:</b>")
        lines_email.append("<h3>✨ New Listings</h3><ul>")
        for p in new_products:
            price_str = f" — ₹{p['price']}" if p.get("price") else ""
            avail     = "✅ In Stock" if p.get("in_stock") else "❌ Out of Stock"
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

    send_telegram("\n".join(lines_tg))
    send_email(
        subject=f"🚗 FirstCry Alert: {len(new_products)} new + {len(back_in_stock)} back-in-stock",
        body_html="\n".join(lines_email),
    )

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*60}")
    print(f"FirstCry Checker — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    seen     = load_seen()
    all_new  = []
    all_back = []

    # FIX 2: One session for the entire run — homepage fetched ONCE
    session = create_session()

    # ── Part 1: Listing pages ─────────────────────────────────────────────────
    for brand, url in LISTING_URLS.items():
        print(f"\n[LISTING] {brand}")
        html = fetch_page(url, session)
        if not html:
            print("  ⚠️  Could not fetch, skipping.")
            continue

        products = parse_products(html, brand)
        if not products:
            print("  ⚠️  No products parsed — site may have changed structure.")
            soup = BeautifulSoup(html, "html.parser")
            print(f"  Page title: {soup.title.string if soup.title else 'N/A'}")
            continue

        brand_seen = seen.get(brand, {})
        new_products, back_in_stock = [], []

        for p in products:
            pid  = product_id(p)
            prev = brand_seen.get(pid)
            if prev is None:
                new_products.append(p)
                brand_seen[pid] = {"name": p["name"], "in_stock": p["in_stock"], "url": p["url"], "first_seen": datetime.now().isoformat()}
            elif not prev.get("in_stock") and p.get("in_stock"):
                back_in_stock.append(p)
                brand_seen[pid]["in_stock"] = True
            else:
                brand_seen[pid]["in_stock"] = p.get("in_stock", True)

        seen[brand] = brand_seen
        all_new.extend(new_products)
        all_back.extend(back_in_stock)
        print(f"  Total: {len(products)} | New: {len(new_products)} | Back in stock: {len(back_in_stock)}")
        time.sleep(1)  # FIX 1

    # ── Part 2: Watchlist ─────────────────────────────────────────────────────
    if WATCH_PRODUCTS:
        print(f"\n[WATCHLIST] Checking {len(WATCH_PRODUCTS)} cars...")
        watch_seen = seen.get("__watchlist__", {})

        for label, url in WATCH_PRODUCTS.items():
            print(f"\n  Checking: {label}")
            html = fetch_page(url, session)
            if not html:
                print("  ⚠️  Could not fetch, skipping.")
                continue

            p = parse_single_product(html, label, url)
            if not p:
                continue

            pid  = product_id(p)
            prev = watch_seen.get(pid)

            if prev is None:
                watch_seen[pid] = {"name": p["name"], "in_stock": p["in_stock"], "url": url, "first_seen": datetime.now().isoformat()}
                if p["in_stock"]:
                    all_back.append(p)
            elif not prev.get("in_stock") and p["in_stock"]:
                all_back.append(p)
                watch_seen[pid]["in_stock"] = True
                print(f"  🎉 BACK IN STOCK: {label}")
            else:
                watch_seen[pid]["in_stock"] = p["in_stock"]

            time.sleep(1)  # FIX 1

        seen["__watchlist__"] = watch_seen

    save_seen(seen)
    notify(all_new, all_back)

    if not all_new and not all_back:
        print("\n✅ No changes detected. All quiet.")
    else:
        print(f"\n🚨 Alerts sent — New: {len(all_new)} | Back in stock: {len(all_back)}")


if __name__ == "__main__":
    main()