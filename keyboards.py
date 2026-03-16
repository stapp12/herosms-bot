"""
Inline keyboard builders with emoji for the HeroSMS reseller bot.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict


# ── Main menu ──────────────────────────────────────────────────────────────────

def main_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="📱 Buy Number",       callback_data="buy_number"),
        InlineKeyboardButton(text="🕐 My Orders",        callback_data="my_orders"),
    )
    kb.row(
        InlineKeyboardButton(text="💰 My Balance",       callback_data="my_balance"),
        InlineKeyboardButton(text="➕ Top Up",           callback_data="topup"),
    )
    kb.row(
        InlineKeyboardButton(text="ℹ️ Help",             callback_data="help"),
    )
    return kb.as_markup()


# ── Services list ──────────────────────────────────────────────────────────────

SERVICE_EMOJIS = {
    "tg": "✈️", "wa": "💬", "go": "🔵", "fb": "📘", "vk": "🔷",
    "ok": "🟠", "vi": "💜", "ub": "🚗", "am": "📦", "tt": "🎵",
    "ig": "📸", "tw": "🐦", "li": "💼", "yt": "▶️", "ds": "🎮",
}
DEFAULT_SERVICE_EMOJI = "📲"


def services_kb(services: Dict[str, str], page: int = 0, page_size: int = 8) -> InlineKeyboardMarkup:
    """Paginated services keyboard."""
    items = sorted(services.items(), key=lambda x: x[1])
    start = page * page_size
    end = start + page_size
    page_items = items[start:end]

    kb = InlineKeyboardBuilder()
    for code, name in page_items:
        emoji = SERVICE_EMOJIS.get(code, DEFAULT_SERVICE_EMOJI)
        kb.button(text=f"{emoji} {name}", callback_data=f"svc:{code}")
    kb.adjust(2)

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"svc_page:{page-1}"))
    if end < len(items):
        nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"svc_page:{page+1}"))
    if nav_row:
        kb.row(*nav_row)

    kb.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"))
    return kb.as_markup()


# ── Countries list ─────────────────────────────────────────────────────────────

COUNTRY_FLAGS = {
    0: "🇷🇺", 1: "🇺🇦", 2: "🇰🇿", 3: "🇨🇳", 4: "🇵🇭", 5: "🇲🇲",
    6: "🇮🇩", 7: "🇲🇾", 8: "🇰🇪", 9: "🇹🇿", 10: "🇻🇳", 11: "🇰🇬",
    14: "🇺🇸", 22: "🇬🇧", 31: "🇧🇷", 32: "🇳🇬", 44: "🇮🇳", 56: "🇩🇪",
    83: "🇮🇱", 100: "🇫🇷", 101: "🇳🇱",
}


def countries_kb(countries: List[Dict], service: str, page: int = 0, page_size: int = 8) -> InlineKeyboardMarkup:
    visible = [c for c in countries if c.get("visible", 1)]
    start = page * page_size
    end = start + page_size
    page_items = visible[start:end]

    kb = InlineKeyboardBuilder()
    for c in page_items:
        cid = c.get("id", 0)
        name = c.get("eng") or c.get("rus") or str(cid)
        flag = COUNTRY_FLAGS.get(cid, "🌐")
        kb.button(text=f"{flag} {name}", callback_data=f"country:{service}:{cid}")
    kb.adjust(2)

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"ctry_page:{service}:{page-1}"))
    if end < len(visible):
        nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"ctry_page:{service}:{page+1}"))
    if nav_row:
        kb.row(*nav_row)

    kb.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data="buy_number"),
        InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"),
    )
    return kb.as_markup()


# ── Order management ───────────────────────────────────────────────────────────

def order_kb(order_id: int, activation_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🔄 Check SMS", callback_data=f"check_sms:{order_id}"),
        InlineKeyboardButton(text="🔁 New Code",  callback_data=f"new_code:{order_id}"),
    )
    kb.row(
        InlineKeyboardButton(text="❌ Cancel",    callback_data=f"cancel_order:{order_id}"),
        InlineKeyboardButton(text="✅ Complete",  callback_data=f"complete_order:{order_id}"),
    )
    kb.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"))
    return kb.as_markup()


def order_complete_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="📱 Buy Another", callback_data="buy_number"),
        InlineKeyboardButton(text="🏠 Main Menu",   callback_data="main_menu"),
    )
    return kb.as_markup()


# ── Top-up ─────────────────────────────────────────────────────────────────────

def topup_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🪙 Pay with Crypto", callback_data="topup_crypto"))
    kb.row(InlineKeyboardButton(text="💳 I already transferred (manual)", callback_data="topup_manual"))
    kb.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"))
    return kb.as_markup()


def topup_amount_kb() -> InlineKeyboardMarkup:
    amounts = [1, 2, 5, 10, 20, 50]
    kb = InlineKeyboardBuilder()
    for amt in amounts:
        kb.button(text=f"💵 ${amt}", callback_data=f"topup_amt:{amt}")
    kb.adjust(3)
    kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data="topup"))
    return kb.as_markup()


# ── Admin panel ────────────────────────────────────────────────────────────────

def admin_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="📊 Stats",          callback_data="adm_stats"),
        InlineKeyboardButton(text="👥 Users",           callback_data="adm_users"),
    )
    kb.row(
        InlineKeyboardButton(text="💰 Pending Top-ups", callback_data="adm_pending_topups"),
        InlineKeyboardButton(text="📋 Recent Orders",   callback_data="adm_orders"),
    )
    kb.row(
        InlineKeyboardButton(text="💳 Add Balance",     callback_data="adm_add_balance"),
        InlineKeyboardButton(text="🚫 Ban User",        callback_data="adm_ban"),
    )
    kb.row(
        InlineKeyboardButton(text="📣 Broadcast",       callback_data="adm_broadcast"),
        InlineKeyboardButton(text="🔑 HeroSMS Balance", callback_data="adm_api_balance"),
    )
    return kb.as_markup()


def confirm_topup_kb(payment_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ Confirm",  callback_data=f"adm_confirm_payment:{payment_id}"),
        InlineKeyboardButton(text="❌ Reject",   callback_data=f"adm_reject_payment:{payment_id}"),
    )
    return kb.as_markup()


def back_to_admin_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="⬅️ Admin Panel", callback_data="admin_menu"))
    return kb.as_markup()
