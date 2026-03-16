import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    BOT_TOKEN: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    HEROSMS_API_KEY: str = field(default_factory=lambda: os.getenv("HEROSMS_API_KEY", ""))
    HEROSMS_BASE_URL: str = "https://hero-sms.com/stubs/handler_api.php"
    MARKUP: float = field(default_factory=lambda: float(os.getenv("MARKUP", "0.10")))
    MARKUP_PCT: float = field(default_factory=lambda: float(os.getenv("MARKUP_PCT", "0")))
    ADMIN_IDS: List[int] = field(default_factory=lambda: [
        int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
    ])
    NOWPAYMENTS_API_KEY: str = field(default_factory=lambda: os.getenv("NOWPAYMENTS_API_KEY", ""))
    NOWPAYMENTS_IPN_SECRET: str = field(default_factory=lambda: os.getenv("NOWPAYMENTS_IPN_SECRET", ""))
    DB_PATH: str = field(default_factory=lambda: os.getenv("DB_PATH", "herosms_bot.db"))

    def final_price(self, base_price: float) -> float:
        if self.MARKUP_PCT > 0:
            return round(base_price * (1 + self.MARKUP_PCT / 100), 2)
        return round(base_price + self.MARKUP, 2)
