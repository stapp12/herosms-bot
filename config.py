"""
Configuration – load from environment or .env file.
Copy .env.example to .env and fill in values.
"""

import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # ── Telegram ──────────────────────────────────────────────────────────────
    BOT_TOKEN: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))

    # ── HeroSMS API ───────────────────────────────────────────────────────────
    HEROSMS_API_KEY: str = field(default_factory=lambda: os.getenv("HEROSMS_API_KEY", ""))
    HEROSMS_BASE_URL: str = "https://hero-sms.com/stubs/handler_api.php"

    # ── Markup ────────────────────────────────────────────────────────────────
    # Extra amount added on top of the HeroSMS price (in $)
    MARKUP: float = field(default_factory=lambda: float(os.getenv("MARKUP", "0.10")))
    # OR use a percentage instead (set MARKUP_PCT > 0 to use it)
    MARKUP_PCT: float = field(default_factory=lambda: float(os.getenv("MARKUP_PCT", "0")))

    # ── Admin ─────────────────────────────────────────────────────────────────
    # Comma-separated Telegram user IDs
    ADMIN_IDS: List[int] = field(default_factory=lambda: [
        int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
    ])

    # ── Crypto payments ───────────────────────────────────────────────────────
    # NOWPayments API key (https://nowpayments.io)
    NOWPAYMENTS_API_KEY: str = field(default_factory=lambda: os.getenv("NOWPAYMENTS_API_KEY", ""))
    NOWPAYMENTS_IPN_SECRET: str = field(default_factory=lambda: os.getenv("NOWPAYMENTS_IPN_SECRET", ""))

    # ── DB ────────────────────────────────────────────────────────────────────
    DB_PATH: str = field(default_factory=lambda: os.getenv("DB_PATH", "herosms_bot.db"))

    # ── Default country shown first ───────────────────────────────────────────
    DEFAULT_COUNTRY: int = 0   # 0 = Russia, common default

    def final_price(self, base_price: float) -> float:
        """Return reseller price for a given HeroSMS base price."""
        if self.MARKUP_PCT > 0:
            return round(base_price * (1 + self.MARKUP_PCT / 100), 2)
        return round(base_price + self.MARKUP, 2)
