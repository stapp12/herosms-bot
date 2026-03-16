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


@router.callback_query(F.data == "topup_crypto")
async def cb_topup_crypto(cb: CallbackQuery):
    await cb.message.edit_text(
        "🪙 <b>תשלום קריפטו</b>\n\nבחר סכום לטעינה:",
        parse_mode="HTML",
        reply_markup=topup_amount_kb()
    )
    await cb.answer()


@router.callback_query(F.data.startswith("topup_amt:"))
async def cb_topup_amount(cb: CallbackQuery, db: Database, config: Config):
    amount = float(cb.data.split(":")[1])
    user_id = cb.from_user.id

    if not config.NOWPAYMENTS_API_KEY:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="⬅️ חזרה", callback_data="topup"))
        await cb.message.edit_text(
            "⚠️ תשלום קריפטו אוטומטי לא מוגדר עדיין.\n\n"
            "אנא השתמש בהעברה ידנית.",
            reply_markup=kb.as_markup()
        )
        await cb.answer()
        return

    await cb.message.edit_text("⏳ יוצר חשבונית תשלום...")

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
                    "pay_currency": "usdttrc20",
                    "order_id": str(payment_id),
                    "order_description": f"טעינת יתרה משתמש {user_id}",
                },
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json()

        pay_address = data.get("pay_address", "")
        pay_amount  = data.get("pay_amount", amount)
        pay_currency = data.get("pay_currency", "USDT").upper()
        payment_url = data.get("invoice_url", "")

        kb = InlineKeyboardBuilder()
        if payment_url:
            kb.row(InlineKeyboardButton(text="🔗 עמוד תשלום", url=payment_url))
        kb.row(InlineKeyboardButton(text="🏠 תפריט ראשי", callback_data="main_menu"))

        await cb.message.edit_text(
            f"🪙 <b>תשלום קריפטו</b>\n\n"
            f"סכום: <b>${amount:.2f}</b>\n"
            f"לתשלום: <b>{pay_amount} {pay_currency}</b>\n\n"
            f"כתובת:\n<code>{pay_address}</code>\n\n"
            f"⚠️ שלח בדיוק את הסכום הנ\"ל.\n"
            f"✅ היתרה תתעדכן אוטומטית לאחר אישור.",
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )
    except Exception as e:
        logger.error("NOWPayments error: %s", e)
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="⬅️ חזרה", callback_data="topup"))
        await cb.message.edit_text(
            "❌ יצירת התשלום נכשלה. נסה שוב או השתמש בהעברה ידנית.",
            reply_markup=kb.as_markup()
        )
    await cb.answer()


@router.callback_query(F.data == "topup_manual")
async def cb_topup_manual(cb: CallbackQuery, state: FSMContext):
    await state.set_state(TopUpState.entering_manual_note)
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="❌ ביטול", callback_data="topup"))
    await cb.message.edit_text(
        "📨 <b>בקשת טעינה ידנית</b>\n\n"
        "שלח הוכחת תשלום או מזהה עסקה כהודעה.\n"
        "מנהל יאשר ויזכה את חשבונך.\n\n"
        "✍️ הקלד הודעה עכשיו:",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
    await cb.answer()


@router.message(TopUpState.entering_manual_note)
async def handle_manual_note(message: Message, state: FSMContext, db: Database, config: Config):
    note = message.text or message.caption or "(ללא טקסט)"
    user_id = message.from_user.id

    payment_id = await db.create_payment(user_id, 0, "manual", note=note)

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🏠 תפריט ראשי", callback_data="main_menu"))
    await message.answer(
        f"✅ <b>הבקשה נשלחה!</b>\n\n"
        f"מזהה תשלום: <b>#{payment_id}</b>\n\n"
        f"מנהל יבדוק ויזכה את חשבונך בקרוב.",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

    from keyboards import confirm_topup_kb
    for admin_id in config.ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"💳 <b>בקשת טעינה ידנית חדשה</b>\n\n"
                f"משתמש: <b>{message.from_user.full_name}</b> (@{message.from_user.username or '—'})\n"
                f"ID: <code>{user_id}</code>\n"
                f"מזהה תשלום: <b>#{payment_id}</b>\n\n"
                f"📝 {note}",
                parse_mode="HTML",
                reply_markup=confirm_topup_kb(payment_id)
            )
        except Exception as e:
            logger.warning("לא ניתן להודיע אדמין %s: %s", admin_id, e)

    await state.clear()
