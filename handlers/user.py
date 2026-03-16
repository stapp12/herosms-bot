"""
User-facing handlers: start, menu navigation, buy flow, order management.
"""

import asyncio
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

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


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_api(config: Config) -> HeroSMSAPI:
    return HeroSMSAPI(config.HEROSMS_API_KEY, config.HEROSMS_BASE_URL)

async def ensure_user(message_or_callback, db: Database):
    u = message_or_callback.from_user
    return await db.get_or_create_user(u.id, u.username or "", u.full_name or "")

async def is_banned(user_id: int, db: Database) -> bool:
    user = await db.get_user(user_id)
    return bool(user and user.get("is_banned"))


# ── /start ─────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, db: Database, config: Config):
    await ensure_user(message, db)
    if await is_banned(message.from_user.id, db):
        await message.answer("🚫 Your account has been suspended. Contact support.")
        return
    await message.answer(
        f"👋 Welcome to <b>Virtual Numbers Bot</b>!\n\n"
        f"Get temporary phone numbers for any service — instant delivery.\n\n"
        f"Use the menu below to get started 👇",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )


# ── Main menu ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "main_menu")
async def cb_main_menu(cb: CallbackQuery):
    await cb.message.edit_text(
        "🏠 <b>Main Menu</b>\n\nWhat would you like to do?",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )
    await cb.answer()


# ── Help ───────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "help")
async def cb_help(cb: CallbackQuery):
    text = (
        "ℹ️ <b>How it works</b>\n\n"
        "1️⃣ Press <b>Buy Number</b>\n"
        "2️⃣ Choose a <b>service</b> (Telegram, WhatsApp, etc.)\n"
        "3️⃣ Choose a <b>country</b>\n"
        "4️⃣ The bot charges your balance & gives you a number\n"
        "5️⃣ Press <b>Check SMS</b> to receive your code\n"
        "6️⃣ Once done, press <b>Complete</b>\n\n"
        "💡 Use <b>Top Up</b> to add funds before buying.\n"
        "📩 Contact @YourSupportUser for help."
    )
    from keyboards import InlineKeyboardBuilder, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder as IKB
    kb = IKB()
    kb.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"))
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
    await cb.answer()


# ── Balance ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "my_balance")
async def cb_balance(cb: CallbackQuery, db: Database):
    await ensure_user(cb, db)
    balance = await db.get_balance(cb.from_user.id)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="➕ Top Up", callback_data="topup"),
        InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"),
    )
    await cb.message.edit_text(
        f"💰 <b>Your Balance</b>\n\n<b>${balance:.2f}</b>",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
    await cb.answer()


# ── Buy number flow ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "buy_number")
async def cb_buy_number(cb: CallbackQuery, db: Database, config: Config, state: FSMContext):
    await ensure_user(cb, db)
    if await is_banned(cb.from_user.id, db):
        await cb.answer("🚫 Your account is suspended.", show_alert=True)
        return

    await cb.message.edit_text("⏳ Loading services...", parse_mode="HTML")
    api = get_api(config)
    services = await api.get_services_list()
    if not services:
        await cb.message.edit_text("❌ Could not load services. Try again later.", reply_markup=main_menu_kb())
        await cb.answer()
        return

    await state.update_data(services=services)
    await state.set_state(BuyFlow.choosing_service)
    await cb.message.edit_text(
        "📱 <b>Choose a Service</b>\n\nSelect what you need a number for:",
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
    service = cb.data.split(":")[1]
    await cb.message.edit_text("⏳ Loading countries...", parse_mode="HTML")
    api = get_api(config)
    countries = await api.get_countries()
    await state.update_data(selected_service=service, countries=countries)
    await state.set_state(BuyFlow.choosing_country)
    await cb.message.edit_text(
        f"🌍 <b>Choose a Country</b>",
        parse_mode="HTML",
        reply_markup=countries_kb(countries, service, page=0)
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ctry_page:"))
async def cb_ctry_page(cb: CallbackQuery, state: FSMContext):
    _, service, page_str = cb.data.split(":")
    page = int(page_str)
    data = await state.get_data()
    countries = data.get("countries", [])
    await cb.message.edit_reply_markup(reply_markup=countries_kb(countries, service, page=page))
    await cb.answer()


@router.callback_query(F.data.startswith("country:"))
async def cb_country_chosen(cb: CallbackQuery, db: Database, config: Config, state: FSMContext):
    _, service, country_str = cb.data.split(":")
    country = int(country_str)
    user_id = cb.from_user.id

    # Check balance
    balance = await db.get_balance(user_id)

    api = get_api(config)
    # Get price for this service+country
    prices = await api.get_prices(service=service, country=country)
    base_price = 0.0
    try:
        # prices shape: {country_id: {service: {cost, count}}}
        base_price = float(prices.get(str(country), {}).get(service, {}).get("cost", 0))
    except Exception:
        pass

    final_price = config.final_price(base_price) if base_price > 0 else config.MARKUP

    if balance < final_price:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        kb = InlineKeyboardBuilder()
        kb.row(
            InlineKeyboardButton(text="➕ Top Up", callback_data="topup"),
            InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"),
        )
        await cb.message.edit_text(
            f"❌ <b>Insufficient Balance</b>\n\n"
            f"Required: <b>${final_price:.2f}</b>\n"
            f"Your balance: <b>${balance:.2f}</b>\n\n"
            f"Please top up your account.",
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )
        await cb.answer()
        return

    await cb.message.edit_text("⏳ Getting your number...")

    try:
        result = await api.get_number(service, country)
    except NoNumbersError:
        await cb.message.edit_text(
            "😔 <b>No numbers available</b> for this combination right now.\nTry a different country.",
            parse_mode="HTML",
            reply_markup=countries_kb(
                (await state.get_data()).get("countries", []), service, page=0
            )
        )
        await cb.answer()
        return
    except InsufficientBalanceError:
        await cb.message.edit_text(
            "❌ Internal balance error. Contact support.",
            parse_mode="HTML",
            reply_markup=main_menu_kb()
        )
        await cb.answer()
        return

    activation_id = result["activation_id"]
    phone_number = result["phone_number"]

    # Deduct balance and log order
    await db.update_balance(user_id, -final_price)
    order_id = await db.create_order(
        user_id, activation_id, phone_number, service, country, base_price, final_price
    )
    await db.update_order(order_id, status="active")

    # Notify API number is ready
    await api.set_status(activation_id, 1)
    await state.clear()

    await cb.message.edit_text(
        f"✅ <b>Number Ready!</b>\n\n"
        f"📞 <code>{phone_number}</code>\n\n"
        f"💸 Charged: <b>${final_price:.2f}</b>\n"
        f"🆔 Order ID: <b>#{order_id}</b>\n\n"
        f"⏰ You have <b>20 minutes</b> to receive the SMS.\n"
        f"Press <b>Check SMS</b> to refresh the code.",
        parse_mode="HTML",
        reply_markup=order_kb(order_id, activation_id)
    )
    await cb.answer()


# ── Order actions ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("check_sms:"))
async def cb_check_sms(cb: CallbackQuery, db: Database, config: Config):
    order_id = int(cb.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order or order["user_id"] != cb.from_user.id:
        await cb.answer("Order not found.", show_alert=True)
        return

    api = get_api(config)
    result = await api.get_status(order["activation_id"])

    if result["status"] == "STATUS_OK":
        await db.update_order(order_id, status="code_received", sms_code=result["code"])
        await cb.message.edit_text(
            f"🎉 <b>SMS Code Received!</b>\n\n"
            f"📞 Number: <code>{order['phone_number']}</code>\n"
            f"🔑 Code: <b><code>{result['code']}</code></b>\n\n"
            f"Press ✅ Complete when finished.",
            parse_mode="HTML",
            reply_markup=order_kb(order_id, order["activation_id"])
        )
    elif result["status"] == "STATUS_CANCEL":
        await db.update_order(order_id, status="cancelled")
        await cb.message.edit_text(
            "❌ <b>Activation was cancelled.</b> Balance has been refunded.",
            parse_mode="HTML",
            reply_markup=main_menu_kb()
        )
    else:
        await cb.answer("⏳ No SMS yet. Try again in a moment.", show_alert=False)


@router.callback_query(F.data.startswith("new_code:"))
async def cb_new_code(cb: CallbackQuery, db: Database, config: Config):
    order_id = int(cb.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order or order["user_id"] != cb.from_user.id:
        await cb.answer("Order not found.", show_alert=True)
        return
    api = get_api(config)
    await api.set_status(order["activation_id"], 3)
    await cb.answer("🔁 Requested a new code. Press Check SMS in a moment.")


@router.callback_query(F.data.startswith("cancel_order:"))
async def cb_cancel_order(cb: CallbackQuery, db: Database, config: Config):
    order_id = int(cb.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order or order["user_id"] != cb.from_user.id:
        await cb.answer("Order not found.", show_alert=True)
        return
    if order["status"] not in ("active", "pending"):
        await cb.answer("Cannot cancel this order.", show_alert=True)
        return

    api = get_api(config)
    cancelled = await api.cancel_activation(order["activation_id"])
    refund = order["charged_price"] if cancelled else 0.0
    if refund > 0:
        await db.update_balance(cb.from_user.id, refund)
    await db.update_order(order_id, status="cancelled")

    await cb.message.edit_text(
        f"🗑️ Order <b>#{order_id}</b> cancelled.\n"
        + (f"💰 <b>${refund:.2f}</b> refunded to your balance." if refund > 0 else ""),
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )
    await cb.answer()


@router.callback_query(F.data.startswith("complete_order:"))
async def cb_complete_order(cb: CallbackQuery, db: Database, config: Config):
    order_id = int(cb.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order or order["user_id"] != cb.from_user.id:
        await cb.answer("Order not found.", show_alert=True)
        return

    api = get_api(config)
    await api.complete_activation(order["activation_id"])
    await db.update_order(order_id, status="completed")

    await cb.message.edit_text(
        f"✅ <b>Order #{order_id} completed!</b>\n\nThank you for using our service.",
        parse_mode="HTML",
        reply_markup=order_complete_kb()
    )
    await cb.answer()


# ── My orders ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "my_orders")
async def cb_my_orders(cb: CallbackQuery, db: Database):
    orders = await db.user_orders(cb.from_user.id, limit=10)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    if not orders:
        kb = InlineKeyboardBuilder()
        kb.row(
            InlineKeyboardButton(text="📱 Buy Number", callback_data="buy_number"),
            InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"),
        )
        await cb.message.edit_text("📭 You have no orders yet.", reply_markup=kb.as_markup())
        await cb.answer()
        return

    STATUS_EMOJI = {
        "active": "🟡", "pending": "⏳", "code_received": "🟢",
        "completed": "✅", "cancelled": "❌"
    }
    lines = ["🕐 <b>Your Recent Orders</b>\n"]
    kb = InlineKeyboardBuilder()
    for o in orders:
        emoji = STATUS_EMOJI.get(o["status"], "❓")
        lines.append(
            f"{emoji} <b>#{o['id']}</b> — <code>{o['phone_number'] or '—'}</code> "
            f"[{o['service']}] ${o['charged_price']:.2f}"
        )
        if o["status"] in ("active", "code_received"):
            kb.button(text=f"#{o['id']} Manage", callback_data=f"check_sms:{o['id']}")
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"))

    await cb.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=kb.as_markup())
    await cb.answer()


# ── Top up (entry) ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "topup")
async def cb_topup(cb: CallbackQuery):
    await cb.message.edit_text(
        "💳 <b>Top Up Your Balance</b>\n\n"
        "Choose a payment method:",
        parse_mode="HTML",
        reply_markup=topup_kb()
    )
    await cb.answer()
