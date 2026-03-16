import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from config import Config
from database import Database
from herosms import HeroSMSAPI, NoNumbersError, InsufficientBalanceError, HeroSMSError
from keyboards import (
    main_menu_kb, services_kb, countries_kb, order_kb,
    order_complete_kb, topup_kb
)

logger = logging.getLogger(__name__)
router = Router()


class BuyFlow(StatesGroup):
    choosing_service = State()
    choosing_country = State()


def get_api(config: Config) -> HeroSMSAPI:
    return HeroSMSAPI(config.HEROSMS_API_KEY, config.HEROSMS_BASE_URL)


async def ensure_user(obj, db: Database):
    u = obj.from_user
    return await db.get_or_create_user(u.id, u.username or "", u.full_name or "")


async def is_banned(user_id: int, db: Database) -> bool:
    user = await db.get_user(user_id)
    return bool(user and user.get("is_banned"))


# ── /start ─────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, db: Database, config: Config):
    await ensure_user(message, db)
    if await is_banned(message.from_user.id, db):
        await message.answer("🚫 החשבון שלך חסום. פנה לתמיכה.")
        return
    await message.answer(
        f"👋 ברוך הבא ל<b>בוט מספרים וירטואליים</b>!\n\n"
        f"קבל מספר טלפון זמני לכל שירות — מיידי ופשוט.\n\n"
        f"בחר פעולה מהתפריט 👇",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )


# ── תפריט ראשי ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "main_menu")
async def cb_main_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(
        "🏠 <b>תפריט ראשי</b>\n\nמה תרצה לעשות?",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )
    await cb.answer()


# ── עזרה ───────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "help")
async def cb_help(cb: CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🏠 תפריט ראשי", callback_data="main_menu"))
    await cb.message.edit_text(
        "ℹ️ <b>איך זה עובד?</b>\n\n"
        "1️⃣ לחץ <b>רכישת מספר</b>\n"
        "2️⃣ בחר <b>שירות</b> (טלגרם, וואטסאפ וכו')\n"
        "3️⃣ בחר <b>מדינה</b>\n"
        "4️⃣ הבוט מחייב את היתרה ומספק מספר\n"
        "5️⃣ לחץ <b>בדוק SMS</b> לקבלת הקוד\n"
        "6️⃣ לחץ <b>סיום</b> כשסיימת\n\n"
        "💡 השתמש ב<b>טעינת יתרה</b> לפני הרכישה.\n"
        "📩 לתמיכה פנה למנהל.",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
    await cb.answer()


# ── יתרה ───────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "my_balance")
async def cb_balance(cb: CallbackQuery, db: Database):
    await ensure_user(cb, db)
    balance = await db.get_balance(cb.from_user.id)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="➕ טעינת יתרה", callback_data="topup"),
        InlineKeyboardButton(text="🏠 תפריט ראשי", callback_data="main_menu"),
    )
    await cb.message.edit_text(
        f"💰 <b>היתרה שלך</b>\n\n<b>${balance:.2f}</b>",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
    await cb.answer()


# ── רכישת מספר ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "buy_number")
async def cb_buy_number(cb: CallbackQuery, db: Database, config: Config, state: FSMContext):
    await ensure_user(cb, db)
    if await is_banned(cb.from_user.id, db):
        await cb.answer("🚫 החשבון שלך חסום.", show_alert=True)
        return

    await cb.message.edit_text("⏳ טוען שירותים...")
    api = get_api(config)

    try:
        services = await api.get_services_list()
    except Exception as e:
        logger.error("getServicesList error: %s", e)
        services = {}

    if not services:
        await cb.message.edit_text(
            "❌ לא ניתן לטעון שירותים כרגע. נסה שוב מאוחר יותר.",
            reply_markup=main_menu_kb()
        )
        await cb.answer()
        return

    await state.update_data(services=services)
    await state.set_state(BuyFlow.choosing_service)
    await cb.message.edit_text(
        f"📱 <b>בחר שירות</b>\n\nנמצאו {len(services)} שירותים זמינים:",
        parse_mode="HTML",
        reply_markup=services_kb(services, page=0)
    )
    await cb.answer()


@router.callback_query(F.data.startswith("svc_page:"))
async def cb_svc_page(cb: CallbackQuery, state: FSMContext):
    page = int(cb.data.split(":")[1])
    data = await state.get_data()
    services = data.get("services", {})
    await cb.message.edit_reply_markup(reply_markup=services_kb(services, page=page))
    await cb.answer()


@router.callback_query(F.data.startswith("svc:"))
async def cb_service_chosen(cb: CallbackQuery, db: Database, config: Config, state: FSMContext):
    service = cb.data.split(":", 1)[1]
    await cb.message.edit_text("⏳ טוען מדינות...")

    api = get_api(config)
    try:
        countries = await api.get_countries()
    except Exception as e:
        logger.error("getCountries error: %s", e)
        countries = []

    if not countries:
        await cb.message.edit_text(
            "❌ לא ניתן לטעון מדינות. נסה שוב.",
            reply_markup=main_menu_kb()
        )
        await cb.answer()
        return

    data = await state.get_data()
    services = data.get("services", {})
    service_name = services.get(service, service)

    await state.update_data(selected_service=service, countries=countries)
    await state.set_state(BuyFlow.choosing_country)
    await cb.message.edit_text(
        f"🌍 <b>בחר מדינה</b>\nשירות: <b>{service_name}</b>",
        parse_mode="HTML",
        reply_markup=countries_kb(countries, service, page=0)
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ctry_page:"))
async def cb_ctry_page(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split(":")
    service = parts[1]
    page = int(parts[2])
    data = await state.get_data()
    countries = data.get("countries", [])
    await cb.message.edit_reply_markup(reply_markup=countries_kb(countries, service, page=page))
    await cb.answer()


@router.callback_query(F.data.startswith("country:"))
async def cb_country_chosen(cb: CallbackQuery, db: Database, config: Config, state: FSMContext):
    parts = cb.data.split(":")
    service = parts[1]
    country = int(parts[2])
    user_id = cb.from_user.id

    balance = await db.get_balance(user_id)
    api = get_api(config)

    # שלוף מחיר
    base_price = 0.0
    try:
        prices = await api.get_prices(service=service, country=country)
        # פורמט: {country_id: {service: {cost, count}}}
        cp = prices.get(str(country), prices.get(country, {}))
        if isinstance(cp, dict):
            sv = cp.get(service, {})
            if isinstance(sv, dict):
                base_price = float(sv.get("cost", 0))
            elif isinstance(sv, (int, float)):
                base_price = float(sv)
    except Exception as e:
        logger.error("getPrices error: %s", e)

    final_price = config.final_price(base_price) if base_price > 0 else config.MARKUP

    if balance < final_price:
        kb = InlineKeyboardBuilder()
        kb.row(
            InlineKeyboardButton(text="➕ טעינת יתרה", callback_data="topup"),
            InlineKeyboardButton(text="🏠 תפריט ראשי", callback_data="main_menu"),
        )
        await cb.message.edit_text(
            f"❌ <b>יתרה לא מספיקה</b>\n\n"
            f"נדרש: <b>${final_price:.2f}</b>\n"
            f"יתרתך: <b>${balance:.2f}</b>\n\n"
            f"אנא טען יתרה ונסה שוב.",
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )
        await cb.answer()
        return

    await cb.message.edit_text("⏳ מקבל מספר, אנא המתן...")

    try:
        result = await api.get_number(service, country)
    except NoNumbersError:
        data = await state.get_data()
        countries = data.get("countries", [])
        await cb.message.edit_text(
            "😔 <b>אין מספרים זמינים</b> לבחירה זו כרגע.\nנסה מדינה אחרת.",
            parse_mode="HTML",
            reply_markup=countries_kb(countries, service, page=0)
        )
        await cb.answer()
        return
    except (InsufficientBalanceError, HeroSMSError) as e:
        await cb.message.edit_text(
            f"❌ שגיאה: {e}\nפנה למנהל.",
            parse_mode="HTML",
            reply_markup=main_menu_kb()
        )
        await cb.answer()
        return

    activation_id = result["activation_id"]
    phone_number = result["phone_number"]

    await db.update_balance(user_id, -final_price)
    order_id = await db.create_order(user_id, activation_id, phone_number, service, country, base_price, final_price)
    await db.update_order(order_id, status="active")

    try:
        await api.set_status(activation_id, 1)
    except Exception:
        pass

    await state.clear()

    await cb.message.edit_text(
        f"✅ <b>המספר מוכן!</b>\n\n"
        f"📞 <code>{phone_number}</code>\n\n"
        f"💸 חויבת: <b>${final_price:.2f}</b>\n"
        f"🆔 מספר הזמנה: <b>#{order_id}</b>\n\n"
        f"⏰ יש לך <b>20 דקות</b> לקבל את ה-SMS.\n"
        f"לחץ <b>בדוק SMS</b> לקבלת הקוד.",
        parse_mode="HTML",
        reply_markup=order_kb(order_id, activation_id)
    )
    await cb.answer()


# ── ניהול הזמנה ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("check_sms:"))
async def cb_check_sms(cb: CallbackQuery, db: Database, config: Config):
    order_id = int(cb.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order or order["user_id"] != cb.from_user.id:
        await cb.answer("הזמנה לא נמצאה.", show_alert=True)
        return

    api = get_api(config)
    try:
        result = await api.get_status(order["activation_id"])
    except Exception as e:
        await cb.answer(f"שגיאה: {e}", show_alert=True)
        return

    if result["status"] == "STATUS_OK":
        await db.update_order(order_id, status="code_received", sms_code=result["code"])
        await cb.message.edit_text(
            f"🎉 <b>קיבלת קוד SMS!</b>\n\n"
            f"📞 מספר: <code>{order['phone_number']}</code>\n"
            f"🔑 קוד: <b><code>{result['code']}</code></b>\n\n"
            f"לחץ ✅ סיום כשסיימת להשתמש בקוד.",
            parse_mode="HTML",
            reply_markup=order_kb(order_id, order["activation_id"])
        )
    elif result["status"] == "STATUS_CANCEL":
        await db.update_order(order_id, status="cancelled")
        await cb.message.edit_text(
            "❌ <b>ההפעלה בוטלה.</b> היתרה הוחזרה לחשבונך.",
            parse_mode="HTML",
            reply_markup=main_menu_kb()
        )
    else:
        await cb.answer("⏳ עדיין אין SMS. נסה שוב בעוד רגע.", show_alert=False)


@router.callback_query(F.data.startswith("new_code:"))
async def cb_new_code(cb: CallbackQuery, db: Database, config: Config):
    order_id = int(cb.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order or order["user_id"] != cb.from_user.id:
        await cb.answer("הזמנה לא נמצאה.", show_alert=True)
        return
    api = get_api(config)
    try:
        await api.set_status(order["activation_id"], 3)
        await cb.answer("🔁 בקשה לקוד חדש נשלחה. לחץ 'בדוק SMS' בעוד רגע.")
    except Exception as e:
        await cb.answer(f"שגיאה: {e}", show_alert=True)


@router.callback_query(F.data.startswith("cancel_order:"))
async def cb_cancel_order(cb: CallbackQuery, db: Database, config: Config):
    order_id = int(cb.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order or order["user_id"] != cb.from_user.id:
        await cb.answer("הזמנה לא נמצאה.", show_alert=True)
        return
    if order["status"] not in ("active", "pending"):
        await cb.answer("לא ניתן לבטל הזמנה זו.", show_alert=True)
        return

    api = get_api(config)
    try:
        cancelled = await api.cancel_activation(order["activation_id"])
    except Exception:
        cancelled = False

    refund = order["charged_price"] if cancelled else 0.0
    if refund > 0:
        await db.update_balance(cb.from_user.id, refund)
    await db.update_order(order_id, status="cancelled")

    await cb.message.edit_text(
        f"🗑️ הזמנה <b>#{order_id}</b> בוטלה.\n"
        + (f"💰 <b>${refund:.2f}</b> הוחזרו ליתרתך." if refund > 0 else ""),
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )
    await cb.answer()


@router.callback_query(F.data.startswith("complete_order:"))
async def cb_complete_order(cb: CallbackQuery, db: Database, config: Config):
    order_id = int(cb.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order or order["user_id"] != cb.from_user.id:
        await cb.answer("הזמנה לא נמצאה.", show_alert=True)
        return

    api = get_api(config)
    try:
        await api.complete_activation(order["activation_id"])
    except Exception:
        pass
    await db.update_order(order_id, status="completed")

    await cb.message.edit_text(
        f"✅ <b>הזמנה #{order_id} הושלמה!</b>\n\nתודה שהשתמשת בשירות שלנו.",
        parse_mode="HTML",
        reply_markup=order_complete_kb()
    )
    await cb.answer()


# ── ההזמנות שלי ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "my_orders")
async def cb_my_orders(cb: CallbackQuery, db: Database):
    orders = await db.user_orders(cb.from_user.id, limit=10)

    if not orders:
        kb = InlineKeyboardBuilder()
        kb.row(
            InlineKeyboardButton(text="📱 רכישת מספר", callback_data="buy_number"),
            InlineKeyboardButton(text="🏠 תפריט ראשי", callback_data="main_menu"),
        )
        await cb.message.edit_text("📭 אין לך הזמנות עדיין.", reply_markup=kb.as_markup())
        await cb.answer()
        return

    STATUS_EMOJI = {
        "active": "🟡", "pending": "⏳", "code_received": "🟢",
        "completed": "✅", "cancelled": "❌"
    }
    STATUS_HE = {
        "active": "פעיל", "pending": "ממתין", "code_received": "קוד התקבל",
        "completed": "הושלם", "cancelled": "בוטל"
    }

    lines = ["🕐 <b>ההזמנות שלך</b>\n"]
    kb = InlineKeyboardBuilder()
    for o in orders:
        emoji = STATUS_EMOJI.get(o["status"], "❓")
        status_he = STATUS_HE.get(o["status"], o["status"])
        lines.append(
            f"{emoji} <b>#{o['id']}</b> — <code>{o['phone_number'] or '—'}</code> "
            f"[{o['service']}] ${o['charged_price']:.2f} — {status_he}"
        )
        if o["status"] in ("active", "code_received"):
            kb.button(text=f"#{o['id']} נהל", callback_data=f"check_sms:{o['id']}")
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text="🏠 תפריט ראשי", callback_data="main_menu"))

    await cb.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=kb.as_markup())
    await cb.answer()


# ── טעינת יתרה ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "topup")
async def cb_topup(cb: CallbackQuery):
    await cb.message.edit_text(
        "💳 <b>טעינת יתרה</b>\n\nבחר אמצעי תשלום:",
        parse_mode="HTML",
        reply_markup=topup_kb()
    )
    await cb.answer()
