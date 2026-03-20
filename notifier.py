"""
notifier.py — Telegram notification service for FirstCry Tracker
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Formats and delivers alerts for:
  • New product listings on brand pages
  • Watched cars back in stock
  • Tracker errors (so you know if a run silently fails)

Retries delivery up to 3 times before giving up.
"""

import logging
import time
from datetime import datetime

import requests

from config import TelegramConfig

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
_MAX_MESSAGE_LENGTH = 4096   # Telegram hard limit per message


class Notifier:
    """
    Sends formatted Telegram alerts with retry support.

    All public methods accept a list of product dicts and are
    safe to call with an empty list — they will no-op silently.
    """

    def __init__(self, config: TelegramConfig) -> None:
        self._chat_id  = config.chat_id
        self._api_url  = _TELEGRAM_API.format(token=config.bot_token)

    # ── Public API ────────────────────────────────────────────────────────────

    def alert_new_products(self, products: list[dict]) -> None:
        """Send a NEW LISTING alert. No-op if list is empty."""
        if not products:
            return
        logger.info(f"Sending NEW alert for {len(products)} product(s).")
        for chunk in self._chunk_products(products):
            self._send(self._format_new(chunk))

    def alert_back_in_stock(self, products: list[dict]) -> None:
        """Send a BACK IN STOCK alert. No-op if list is empty."""
        if not products:
            return
        logger.info(f"Sending BACK-IN-STOCK alert for {len(products)} product(s).")
        for chunk in self._chunk_products(products):
            self._send(self._format_back_in_stock(chunk))

    def alert_error(self, context: str, error: Exception) -> None:
        """Send a tracker error notification."""
        message = (
            f"⚠️ <b>FirstCry Tracker — Error</b>\n\n"
            f"📍 <b>Where:</b> <code>{context}</code>\n"
            f"❌ <b>Error:</b> <code>{type(error).__name__}: {error}</code>\n\n"
            f"🕐 {self._ts()}"
        )
        self._send(message)

    # ── Formatters ────────────────────────────────────────────────────────────

    @staticmethod
    def _format_new(products: list[dict]) -> str:
        lines = [
            "🆕 <b>New Listing on FirstCry!</b>",
            f"🕐 {Notifier._ts()}",
            "",
        ]
        for p in products:
            price = f" — <b>₹{p['price']}</b>" if p.get("price") else ""
            stock = "✅ In Stock" if p.get("in_stock") else "⏳ Out of Stock"
            brand = f" | {p['brand']}" if p.get("brand") else ""
            lines += [
                f"🚗 <a href=\"{p['url']}\">{p['name']}</a>{price}",
                f"    {stock}{brand}",
                "",
            ]
        return "\n".join(lines).strip()

    @staticmethod
    def _format_back_in_stock(products: list[dict]) -> str:
        lines = [
            "🔔 <b>Back In Stock on FirstCry!</b>",
            f"🕐 {Notifier._ts()}",
            "",
        ]
        for p in products:
            price = f" — <b>₹{p['price']}</b>" if p.get("price") else ""
            brand = f" | {p['brand']}" if p.get("brand") else ""
            lines += [
                f"🚗 <a href=\"{p['url']}\">{p['name']}</a>{price}",
                f"    ✅ Available Now{brand}",
                "",
            ]
        return "\n".join(lines).strip()

    # ── Chunking (handles Telegram 4096 char limit) ───────────────────────────

    @staticmethod
    def _chunk_products(products: list[dict], size: int = 10) -> list[list[dict]]:
        """Split large product lists into chunks to stay under message limit."""
        return [products[i:i + size] for i in range(0, len(products), size)]

    # ── Timestamp ─────────────────────────────────────────────────────────────

    @staticmethod
    def _ts() -> str:
        return datetime.now().strftime("%d %b %Y, %I:%M %p")

    # ── Delivery with retry ───────────────────────────────────────────────────

    def _send(self, message: str, max_attempts: int = 3) -> None:
        """
        POST message to Telegram API.
        Retries up to max_attempts times with 3s backoff.
        """
        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.post(
                    self._api_url,
                    json={
                        "chat_id":                  self._chat_id,
                        "text":                     message[:_MAX_MESSAGE_LENGTH],
                        "parse_mode":               "HTML",
                        "disable_web_page_preview": False,
                    },
                    timeout=10,
                )
                response.raise_for_status()
                logger.info("Telegram alert delivered ✅")
                return

            except requests.HTTPError as e:
                logger.warning(
                    f"Telegram HTTP error (attempt {attempt}/{max_attempts}): "
                    f"{e.response.status_code} — {e.response.text}"
                )
            except Exception as e:
                logger.warning(
                    f"Telegram delivery failed (attempt {attempt}/{max_attempts}): {e}"
                )

            if attempt < max_attempts:
                time.sleep(3)

        logger.error("All Telegram delivery attempts exhausted — alert not sent.")
