# 🚗 FirstCry Stock Checker — Hot Wheels & Majorette

Automatically monitors FirstCry for new Hot Wheels and Majorette listings and sends you instant alerts via **Telegram** and/or **Email** — runs free on GitHub Actions every 30 minutes.

---

## 📁 Files in this repo

```
├── scraper.py                        # Main scraper
├── requirements.txt                  # Python dependencies
├── seen_products.json                # State file (auto-updated by bot)
└── .github/
    └── workflows/
        └── check_stock.yml          # GitHub Actions schedule
```

---

## 🚀 Setup Guide (One Time)

### Step 1 — Create a GitHub Repository

1. Go to [github.com](https://github.com) → **New repository**
2. Name it `firstcry-checker` (or anything you like)
3. Set it to **Private** (so your secrets stay hidden)
4. Click **Create repository**
5. Upload all the files from this folder into the repo

---

### Step 2 — Set Up Telegram Bot (Free, Recommended)

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` → follow prompts → give it a name like `FirstCryAlertBot`
3. BotFather will give you a **Bot Token** like `7123456789:AAExxxxxxxxxxxxxx` — copy it
4. Now open your new bot and send it any message (like `/start`)
5. Visit this URL in your browser to get your Chat ID:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
   Look for `"chat":{"id":XXXXXXXXX}` — that number is your **Chat ID**

---

### Step 3 — Set Up Email (Optional, use Gmail)

1. Use a Gmail account (create a new one if you prefer)
2. Enable **2-Factor Authentication** on that Gmail account
3. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
4. Create an App Password for "Mail" → copy the 16-character password

---

### Step 4 — Add Secrets to GitHub

In your GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these secrets (add only the ones you want to use):

| Secret Name          | Value                              |
|----------------------|------------------------------------|
| `TELEGRAM_BOT_TOKEN` | Your bot token from BotFather      |
| `TELEGRAM_CHAT_ID`   | Your chat ID number                |
| `EMAIL_SENDER`       | your.gmail@gmail.com               |
| `EMAIL_PASSWORD`     | Your Gmail App Password            |
| `EMAIL_RECEIVER`     | Where to receive alerts (any email)|

> 💡 You can use **just Telegram** or **just Email** or **both** — the script skips whichever isn't configured.

---

### Step 5 — Enable GitHub Actions

1. Go to your repo → **Actions** tab
2. If prompted, click **"I understand my workflows, go ahead and enable them"**
3. Click on **FirstCry Stock Checker** → **Run workflow** → **Run workflow** (to test it immediately)
4. Watch the logs — you should see products being parsed

---

## ⏰ How Often Does It Run?

Every **30 minutes**, 24/7, completely free (GitHub Actions free tier gives 2,000 minutes/month; this uses ~1 min per run = ~1,440 min/month — fits within the free tier).

---

## 🔔 What Triggers a Notification?

You get alerted when:
- ✨ A **new product** appears on the Hot Wheels or Majorette listing page (even if it's out of stock — so you know it exists)
- 🔔 A product that was **out of stock comes back in stock**

You do **NOT** get spammed for products already seen.

---

## 📋 About the Wishlist

The wishlist at `firstcry.com/myshortlist` requires you to be **logged in**, so the bot can't check it without your credentials — and sharing login credentials with a bot isn't safe. 

**Workaround:** Instead of relying on the wishlist, the bot already monitors the full Hot Wheels and Majorette listing pages, so any product that exists on those pages will be detected. If there's a specific product URL you want to monitor, you can add it to the `URLS` dict in `scraper.py` like:

```python
URLS = {
    "Hot Wheels": "...",
    "Majorette": "...",
    "My Wishlist Item": "https://www.firstcry.com/hotwheels/hot-wheels-xxx/12345678",
}
```

---

## 🛠 Troubleshooting

**"No products parsed"** — FirstCry may have updated their HTML structure. Check the Actions log for the page title. You can open an issue or re-run manually.

**Telegram not sending** — Double-check that you messaged your bot first (it won't send to users who never initiated chat).

**GitHub Actions not running** — Make sure the `.github/workflows/check_stock.yml` file is in the repo. Also, GitHub sometimes disables scheduled workflows if the repo has no activity for 60 days — just push a small change to re-enable.

---

## 📬 Sample Notification

```
🚗 FirstCry Stock Alert!
🕐 17 Mar 2026, 10:30 AM

✨ New listings found:
• Hot Wheels Car Assortment 2026 K Case — ₹149 [✅ In Stock]
• Majorette Toyota GR Supra — ₹299 [✅ In Stock]

🔔 Back in stock:
• Hot Wheels Monster Trucks Bone Shaker — ₹399
```
