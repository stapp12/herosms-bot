from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict


def main_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="📱 רכישת מספר",    callback_data="buy_number"),
        InlineKeyboardButton(text="🕐 ההזמנות שלי",   callback_data="my_orders"),
    )
    kb.row(
        InlineKeyboardButton(text="💰 היתרה שלי",     callback_data="my_balance"),
        InlineKeyboardButton(text="➕ טעינת יתרה",    callback_data="topup"),
    )
    kb.row(
        InlineKeyboardButton(text="ℹ️ עזרה",          callback_data="help"),
    )
    return kb.as_markup()


SERVICE_EMOJIS = {
    "tg": "✈️", "wa": "💬", "go": "🔵", "fb": "📘", "vk": "🔷",
    "ok": "🟠", "vi": "💜", "ub": "🚗", "am": "📦", "tt": "🎵",
    "ig": "📸", "tw": "🐦", "li": "💼", "yt": "▶️", "ds": "🎮",
}
DEFAULT_EMOJI = "📲"


def services_kb(services: Dict[str, str], page: int = 0, page_size: int = 8) -> InlineKeyboardMarkup:
   items = sorted(services.items(), key=lambda x: str(x[1])) 
    start = page * page_size
    end = start + page_size
    page_items = items[start:end]

    kb = InlineKeyboardBuilder()
    for code, name in page_items:
        emoji = SERVICE_EMOJIS.get(code, DEFAULT_EMOJI)
        kb.button(text=f"{emoji} {name}", callback_data=f"svc:{code}")
    kb.adjust(2)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ הקודם", callback_data=f"svc_page:{page-1}"))
    if end < len(items):
        nav.append(InlineKeyboardButton(text="הבא ➡️", callback_data=f"svc_page:{page+1}"))
    if nav:
        kb.row(*nav)

    kb.row(InlineKeyboardButton(text="🏠 תפריט ראשי", callback_data="main_menu"))
    return kb.as_markup()


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
        cid = int(c.get("id", 0))
        name = c.get("eng") or c.get("rus") or str(cid)
        flag = COUNTRY_FLAGS.get(cid, "🌐")
        kb.button(text=f"{flag} {name}", callback_data=f"country:{service}:{cid}")
    kb.adjust(2)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ הקודם", callback_data=f"ctry_page:{service}:{page-1}"))
    if end < len(visible):
        nav.append(InlineKeyboardButton(text="הבא ➡️", callback_data=f"ctry_page:{service}:{page+1}"))
    if nav:
        kb.row(*nav)

    kb.row(
        InlineKeyboardButton(text="⬅️ חזרה", callback_data="buy_number"),
        InlineKeyboardButton(text="🏠 תפריט ראשי", callback_data="main_menu"),
    )
    return kb.as_markup()


def order_kb(order_id: int, activation_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🔄 בדוק SMS",     callback_data=f"check_sms:{order_id}"),
        InlineKeyboardButton(text="🔁 קוד חדש",      callback_data=f"new_code:{order_id}"),
    )
    kb.row(
        InlineKeyboardButton(text="❌ ביטול",        callback_data=f"cancel_order:{order_id}"),
        InlineKeyboardButton(text="✅ סיום",         callback_data=f"complete_order:{order_id}"),
    )
    kb.row(InlineKeyboardButton(text="🏠 תפריט ראשי", callback_data="main_menu"))
    return kb.as_markup()


def order_complete_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="📱 רכישה נוספת",  callback_data="buy_number"),
        InlineKeyboardButton(text="🏠 תפריט ראשי",   callback_data="main_menu"),
    )
    return kb.as_markup()


def topup_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🪙 תשלום קריפטו", callback_data="topup_crypto"))
    kb.row(InlineKeyboardButton(text="💳 העברה ידנית (אדמין יאשר)", callback_data="topup_manual"))
    kb.row(InlineKeyboardButton(text="🏠 תפריט ראשי", callback_data="main_menu"))
    return kb.as_markup()


def topup_amount_kb() -> InlineKeyboardMarkup:
    amounts = [1, 2, 5, 10, 20, 50]
    kb = InlineKeyboardBuilder()
    for amt in amounts:
        kb.button(text=f"💵 ${amt}", callback_data=f"topup_amt:{amt}")
    kb.adjust(3)
    kb.row(InlineKeyboardButton(text="⬅️ חזרה", callback_data="topup"))
    return kb.as_markup()


def admin_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="📊 סטטיסטיקות",      callback_data="adm_stats"),
        InlineKeyboardButton(text="👥 משתמשים",          callback_data="adm_users"),
    )
    kb.row(
        InlineKeyboardButton(text="💰 טעינות ממתינות",   callback_data="adm_pending_topups"),
        InlineKeyboardButton(text="📋 הזמנות אחרונות",   callback_data="adm_orders"),
    )
    kb.row(
        InlineKeyboardButton(text="💳 הוספת יתרה",       callback_data="adm_add_balance"),
        InlineKeyboardButton(text="🚫 חסימת משתמש",      callback_data="adm_ban"),
    )
    kb.row(
        InlineKeyboardButton(text="📣 שידור לכולם",      callback_data="adm_broadcast"),
        InlineKeyboardButton(text="🔑 יתרת HeroSMS",     callback_data="adm_api_balance"),
    )
    return kb.as_markup()


def confirm_topup_kb(payment_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ אשר",   callback_data=f"adm_confirm_payment:{payment_id}"),
        InlineKeyboardButton(text="❌ דחה",   callback_data=f"adm_reject_payment:{payment_id}"),
    )
    return kb.as_markup()


def back_to_admin_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="⬅️ פאנל ניהול", callback_data="admin_menu"))
    return kb.as_markup()
