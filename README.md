# 🚗 FirstCry Stock Tracker — Hot Wheels & Majorette

Monitors FirstCry for new listings and restocked cars.
Sends instant Telegram alerts. Runs every 5 minutes on Railway.

---

## 📁 Project Structure

```
firstcry-tracker/
├── config.py        ← All URLs, credentials, constants
├── db.py            ← PostgreSQL state management
├── notifier.py      ← Telegram alert delivery
├── scraper.py       ← Playwright scraping engine + stock logic
├── main.py          ← Entry point
├── requirements.txt
├── Dockerfile
└── railway.toml     ← Railway cron config
```

---

## ⚙️ How It Works

**Every 5 minutes Railway runs `main.py` which:**

1. Connects to PostgreSQL
2. Launches headless Chromium (Playwright)
3. Scrapes Hot Wheels + Majorette listing pages
4. Scrapes each individual watched car page
5. Compares results against stored state
6. Fires Telegram alerts for anything new or restocked
7. Updates PostgreSQL state

### Alert Logic

| Scenario | Action |
|---|---|
| First run (listing) | Store baseline silently — no flood |
| New product on listing page | 🆕 NEW alert |
| Watched car — first seen + in stock | 🔔 BACK IN STOCK alert |
| Watched car — first seen + OOS | Store baseline silently |
| Any product OOS → in stock | 🔔 BACK IN STOCK alert |
| Any product in stock → OOS | Update state silently |
| Scrape fully fails | ⚠️ Error alert to Telegram |

---

## 🚀 Deployment (Railway)

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/YOUR_USERNAME/firstcry-tracker.git
git push -u origin main
```

### Step 2 — Create Railway project
1. Go to [railway.app](https://railway.app)
2. New Project → Deploy from GitHub → select this repo

### Step 3 — Add PostgreSQL
Railway Dashboard → + New → Database → PostgreSQL
`DATABASE_URL` is set automatically.

### Step 4 — Set environment variables
| Variable | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | From @BotFather on Telegram |
| `TELEGRAM_CHAT_ID` | Your chat ID from @userinfobot |
| `DATABASE_URL` | Auto-set by Railway PostgreSQL |

### Step 5 — Verify
Railway Dashboard → Deployments → View Logs

Expected first run output:
```
Initialising FirstCry Tracker...
Database initialised ✅
Browser launched ✅
⚙️  First run — building baseline. No NEW alerts will fire.
[LISTING] Hot Wheels → 45 products stored
[LISTING] Majorette  → 30 products stored
[WATCHED PRODUCTS]   → 30 cars checked
Run complete — 0 new | 0 back-in-stock
```

---

## ➕ Adding More Watched Cars

In `config.py`, add to `WATCH_PRODUCTS`:
```python
"Your Car Label": "https://www.firstcry.com/...product-detail",
```

Redeploy — Railway picks up the change automatically.

---

## 💰 Cost

| Service | Cost |
|---|---|
| Railway Hobby plan | ~$5/month (≈ ₹420) |
| PostgreSQL (included) | ₹0 |
| Telegram Bot | ₹0 |
| **Total** | **≈ ₹420/month** |
