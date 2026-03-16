"""
Payment handlers.
- Crypto top-up via NOWPayments
- Manual top-up (user sends note, admin confirms)
"""

import logging
import aiohttp
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from config import Config
from database import Database
from keyboards import topup_amount_kb

logger = logging.getLogger(__name__)
router = Router()


class TopUpState(StatesGroup):
    entering_manual_note = State()
    entering_custom_amount = State()


# ── Crypto top-up ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "topup_crypto")
async def cb_topup_crypto(cb: CallbackQuery):
    await cb.message.edit_text(
        "🪙 <b>Crypto Top-Up</b>\n\nSelect an amount:",
        parse_mode="HTML",
        reply_markup=topup_amount_kb()
    )
    await cb.answer()


@router.callback_query(F.data.startswith("topup_amt:"))
async def cb_topup_amount(cb: CallbackQuery, db: Database, config: Config):
    amount = float(cb.data.split(":")[1])
    user_id = cb.from_user.id

    if not config.NOWPAYMENTS_API_KEY:
        # Fallback if no NOWPayments key configured
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data="topup"))
        await cb.message.edit_text(
            "⚠️ Automatic crypto payments are not configured yet.\n\n"
            "Please use the manual top-up option or contact support.",
            reply_markup=kb.as_markup()
        )
        await cb.answer()
        return

    await cb.message.edit_text("⏳ Creating payment invoice...")

    payment_id = await db.create_payment(user_id, amount, "crypto")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.nowpayments.io/v1/payment",
                headers={
                    "x-api-key": config.NOWPAYMENTS_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "price_amount": amount,
                    "price_currency": "usd",
                    "pay_currency": "usdt",   # default; user can change on NOWPayments page
                    "order_id": str(payment_id),
                    "order_description": f"Balance top-up for user {user_id}",
                    "ipn_callback_url": "",   # Set your webhook URL here
                },
            ) as resp:
                data = await resp.json()

        pay_address = data.get("pay_address", "")
        pay_amount = data.get("pay_amount", amount)
        pay_currency = data.get("pay_currency", "USDT").upper()
        payment_url = data.get("invoice_url") or ""

        kb = InlineKeyboardBuilder()
        if payment_url:
            kb.row(InlineKeyboardButton(text="🔗 Open Payment Page", url=payment_url))
        kb.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"))

        await cb.message.edit_text(
            f"🪙 <b>Crypto Payment</b>\n\n"
            f"Amount: <b>${amount:.2f}</b>\n"
            f"Pay: <b>{pay_amount} {pay_currency}</b>\n"
            f"Address:\n<code>{pay_address}</code>\n\n"
            f"⚠️ Send exactly the amount shown.\n"
            f"✅ Balance will be credited automatically after confirmation.",
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )
    except Exception as e:
        logger.error("NOWPayments error: %s", e)
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data="topup"))
        await cb.message.edit_text(
            "❌ Payment creation failed. Please try again or use manual top-up.",
            reply_markup=kb.as_markup()
        )
    await cb.answer()


# ── Manual top-up ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "topup_manual")
async def cb_topup_manual(cb: CallbackQuery, state: FSMContext, config: Config):
    await state.set_state(TopUpState.entering_manual_note)
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="❌ Cancel", callback_data="topup"))
    await cb.message.edit_text(
        "📨 <b>Manual Top-Up Request</b>\n\n"
        "Please send your payment proof or transaction ID as a message.\n"
        "An admin will review and confirm it manually.\n\n"
        "Type your message now:",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
    await cb.answer()


@router.message(TopUpState.entering_manual_note)
async def handle_manual_note(message: Message, state: FSMContext, db: Database, config: Config):
    note = message.text or message.caption or "(no text)"
    user_id = message.from_user.id

    payment_id = await db.create_payment(user_id, 0, "manual", note=note)

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu"))
    await message.answer(
        f"✅ <b>Request submitted!</b>\n\n"
        f"Payment ID: <b>#{payment_id}</b>\n\n"
        f"An admin will review your request and credit your balance shortly.",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

    # Notify all admins
    from aiogram import Bot
    bot = message.bot
    for admin_id in config.ADMIN_IDS:
        try:
            from keyboards import confirm_topup_kb
            await bot.send_message(
                admin_id,
                f"💳 <b>New Manual Top-Up Request</b>\n\n"
                f"From: <b>{message.from_user.full_name}</b> (@{message.from_user.username or '—'})\n"
                f"User ID: <code>{user_id}</code>\n"
                f"Payment ID: <b>#{payment_id}</b>\n\n"
                f"Note: {note}",
                parse_mode="HTML",
                reply_markup=confirm_topup_kb(payment_id)
            )
        except Exception as e:
            logger.warning("Could not notify admin %s: %s", admin_id, e)

    await state.clear()
