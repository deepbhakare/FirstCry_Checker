"""
config.py — Centralised configuration for FirstCry Tracker
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
All credentials, constants, listing URLs, and watched
product URLs are defined here. No other file needs editing
for normal usage.
"""

import os
from dataclasses import dataclass, field


# ─── ENVIRONMENT CONFIGS ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str = field(default_factory=lambda: os.environ["TELEGRAM_BOT_TOKEN"])
    chat_id:   str = field(default_factory=lambda: os.environ["TELEGRAM_CHAT_ID"])


@dataclass(frozen=True)
class DatabaseConfig:
    url: str = field(default_factory=lambda: os.environ["DATABASE_URL"])


@dataclass(frozen=True)
class AppConfig:
    telegram:        TelegramConfig = field(default_factory=TelegramConfig)
    database:        DatabaseConfig = field(default_factory=DatabaseConfig)
    pincode:         str = "411014"   # Pune delivery pincode
    request_timeout: int = 15         # seconds per page load
    retry_attempts:  int = 3          # retries on fetch failure
    retry_delay:     int = 5          # seconds between retries
    page_delay:      int = 1          # seconds between product page fetches


# ─── LISTING PAGES ────────────────────────────────────────────────────────────
# Entire brand pages — bot alerts on any NEW product appearing here.

LISTING_URLS: dict[str, str] = {
    "Hot Wheels": (
        "https://www.firstcry.com/hotwheels/5/0/113"
        "?sort=popularity&q=ard-hot%20wheels&ref2=q_ard_hot%20wheels&asid=53241"
    ),
    "Majorette": (
        "https://www.firstcry.com/Majorette/0/0/1335"
        "?q=as_Majorette&asid=48297"
    ),
}


# ─── WATCHED PRODUCTS ─────────────────────────────────────────────────────────
# Specific out-of-stock cars — bot alerts the moment "Add to Cart" appears.
# Format: "Your Label": "https://www.firstcry.com/...product-detail"

WATCH_PRODUCTS: dict[str, str] = {

    # ── Hot Wheels ─────────────────────────────────────────────────────────────
    "HW Ferrari F40 Competizione Red": (
        "https://www.firstcry.com/hot-wheels/hot-wheels-ferrari-f40-competizione"
        "-198-250-toy-car-red/21965916/product-detail"
    ),
    "HW McLaren Formula 1 Team 4": (
        "https://www.firstcry.com/hot-wheels/hot-wheels-mclaren-formula-1-team-4"
        "-formula-one-premium-die-cast-car-anthracite-black-and-yellow/22115543/product-detail"
    ),
    "HW Mercedes-Benz 300 SEL 6.8 AMG": (
        "https://www.firstcry.com/hot-wheels/hot-wheels-mercedes-benz-300-sel-6-8"
        "-amg-die-cast-toy-car-black/22140896/product-detail"
    ),
    "HW Honda Civic Custom": (
        "https://www.firstcry.com/hot-wheels/hot-wheels-73-honda-civic-custom"
        "-personnalise-car-231-250-maroon/22140905/product-detail"
    ),
    "HW Nissan 35GT RR Ver 2": (
        "https://www.firstcry.com/hot-wheels/hot-wheels-die-cast-lb-silhouette"
        "-works-gt-nissan-35gt-rr-ver-2-car-toy-silver/22140906/product-detail"
    ),
    "HW Mercedes-AMG Petronas F1 Team": (
        "https://www.firstcry.com/hot-wheels/hot-wheels-premium-2025-mercedes-amg"
        "-petronas-f1-team-car-black-and-green/22157119/product-detail"
    ),
    "HW Visa Cash App Racing Bulls F1": (
        "https://www.firstcry.com/hot-wheels/hot-wheels-premium-2025-visa-cash-app"
        "-racing-bulls-f1-team-car-black-and-white/22157138/product-detail"
    ),
    "HW Ferrari Team Transport": (
        "https://www.firstcry.com/hot-wheels/hot-wheels-second-story-lorry-die-cast"
        "-free-wheel-car-transport-truck-red/22159210/product-detail"
    ),
    "HW Ford Mustang Dark Horse": (
        "https://www.firstcry.com/hot-wheels/hot-wheels-ford-mustang-dark-horse"
        "-250-250-die-cast-toy-car-blue/22178581/product-detail"
    ),
    "HW Toyota Supra 232-250": (
        "https://www.firstcry.com/hot-wheels/hot-wheels-toyota-supra-232-250"
        "-die-cast-toy-car-green/22178925/product-detail"
    ),
    "HW McLaren P1": (
        "https://www.firstcry.com/hot-wheels/hot-wheels-mclaren-p1-165-250"
        "-die-cast-toy-car-maroon/22179292/product-detail"
    ),
    "HW McLaren F1": (
        "https://www.firstcry.com/hot-wheels/hot-wheels-mclaren-f1-243-250"
        "-die-cast-toy-car-red/22189703/product-detail"
    ),
    "HW STH Ford Sierra Cosworth": (
        "https://www.firstcry.com/hot-wheels/hot-wheels-87-ford-sierra-cosworth"
        "-116-250-toy-car-dark-pink/22240154/product-detail"
    ),
    "HW Ferrari F40 Competizione Black": (
        "https://www.firstcry.com/hot-wheels/hot-wheels-ferrari-f40-competizione"
        "-63-250-toy-car-black/22240147/product-detail"
    ),
    "HW Visa Cash App RB F1 68-250": (
        "https://www.firstcry.com/hot-wheels/hot-wheels-visa-cash-app-racing-bulls"
        "-formula-1-team-equipe-68-250-toy-car-white-and-black/22240176/product-detail"
    ),
    "HW Lamborghini Huracan Coupe": (
        "https://www.firstcry.com/hot-wheels/hot-wheels-lb-works-lamborghini-huracan"
        "-coupe-91-250-toy-car-black/22240182/product-detail"
    ),

    # ── Majorette ──────────────────────────────────────────────────────────────
    "Majorette Porsche 911 GT3 Cup": (
        "https://www.firstcry.com/majorette/majorette-1-64-scale-porsche-911-gt3"
        "-cup-edition-free-wheel-die-cast-car-green/19931378/product-detail"
    ),
    "Majorette Porsche 911 Carrera RS Black": (
        "https://www.firstcry.com/majorette/majorette-porsche-racing-die-cast"
        "-free-wheel-model-toy-car-black/19991405/product-detail"
    ),
    "CHASE Majorette Ford F-150 Raptor": (
        "https://www.firstcry.com/majorette/majorette-ford-f-150-raptor-showroom"
        "-premium-die-cast-car-blue/22063291/product-detail"
    ),
    "Majorette BMW M3 Green": (
        "https://www.firstcry.com/majorette/majorette-bmw-m3-showroom-premium"
        "-die-cast-car-green/22063292/product-detail"
    ),
    "Majorette Aston Martin Vantage GTB": (
        "https://www.firstcry.com/majorette/majorette-aston-martin-vantage-gtb"
        "-showroom-premium-die-cast-car-white/22063293/product-detail"
    ),
    "Majorette Land Rover Defender 90": (
        "https://www.firstcry.com/majorette/majorette-land-rover-defender-90"
        "-showroom-premium-die-cast-car-silver/22063301/product-detail"
    ),
    "Majorette Lamborghini Huracan Avio": (
        "https://www.firstcry.com/majorette/majorette-lamborghini-huracan-avio"
        "-showroom-premium-die-cast-car-black/22063303/product-detail"
    ),
    "Majorette Toyota Supra JZA80 JDM": (
        "https://www.firstcry.com/majorette/majorette-toyota-supra-jzabo-jdm"
        "-legends-deluxe-die-cast-toy-car-royal-blue-and-lime-green/22063306/product-detail"
    ),
    "CHASE Majorette Nissan Cefiro A31": (
        "https://www.firstcry.com/majorette/majorette-nissan-cefiro-a31-jdm"
        "-legends-deluxe-die-cast-car-dark-pink/22063307/product-detail"
    ),
    "Majorette Porsche 911 Carrera RS Blue": (
        "https://www.firstcry.com/majorette/majorette-porsche-911-carrera-rs-2-7"
        "-castheads-premium-die-cast-free-wheel-moving-cars-light-blue/22064343/product-detail"
    ),
    "Majorette Toyota Century JDM": (
        "https://www.firstcry.com/majorette/majorette-toyota-century-jdm-legends"
        "-premium-die-cast-car-grey/22064404/product-detail"
    ),
    "Majorette BMW M3 Vintage Black": (
        "https://www.firstcry.com/majorette/majorette-bmw-m3-vintage-premium"
        "-die-cast-car-black/22064424/product-detail"
    ),
    "Majorette Mercedes 450 SEL Vintage": (
        "https://www.firstcry.com/majorette/majorette-mercedes-benz-450-sel-vintage"
        "-premium-die-cast-car-light-green/22064428/product-detail"
    ),
    "Majorette Aston Martin CHROME Vantage": (
        "https://www.firstcry.com/majorette/majorette-aston-martin-vantage-gtb"
        "-showroom-deluxe-die-cast-car-green/22069192/product-detail"
    ),

    # ── ADD MORE CARS BELOW ────────────────────────────────────────────────────
    # "Label": "https://www.firstcry.com/...product-detail",
}
