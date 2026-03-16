import logging
import aiosqlite
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from config import Config
from database import Database
from herosms import HeroSMSAPI
from keyboards import admin_menu_kb, back_to_admin_kb

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int, config: Config) -> bool:
    return user_id in config.ADMIN_IDS


class AdminState(StatesGroup):
    adding_balance_user   = State()
    adding_balance_amount = State()
    banning_user          = State()
    broadcasting          = State()


@router.message(Command("admin"))
async def cmd_admin(message: Message, config: Config):
    if not is_admin(message.from_user.id, config):
        return
    await message.answer("🔐 <b>פאנל ניהול</b>", parse_mode="HTML", reply_markup=admin_menu_kb())


@router.callback_query(F.data == "admin_menu")
async def cb_admin_menu(cb: CallbackQuery, config: Config):
    if not is_admin(cb.from_user.id, config):
        await cb.answer("⛔ אין הרשאה.", show_alert=True)
        return
    await cb.message.edit_text("🔐 <b>פאנל ניהול</b>", parse_mode="HTML", reply_markup=admin_menu_kb())
    await cb.answer()


@router.callback_query(F.data == "adm_stats")
async def cb_stats(cb: CallbackQuery, db: Database, config: Config):
    if not is_admin(cb.from_user.id, config):
        await cb.answer("⛔", show_alert=True)
        return
    stats = await db.stats()
    text = (
        f"📊 <b>סטטיסטיקות</b>\n\n"
        f"👥 סה\"כ משתמשים: <b>{stats['total_users']}</b>\n"
        f"📋 סה\"כ הזמנות: <b>{stats['total_orders']}</b>\n"
        f"✅ הזמנות פעילות: <b>{stats['active_orders']}</b>\n"
        f"💰 סה\"כ הכנסות: <b>${stats['total_revenue']:.2f}</b>\n"
        f"⏳ טעינות ממתינות: <b>{stats['pending_topups']}</b>"
    )
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_admin_kb())
    await cb.answer()


@router.callback_query(F.data == "adm_api_balance")
async def cb_api_balance(cb: CallbackQuery, config: Config):
    if not is_admin(cb.from_user.id, config):
        await cb.answer("⛔", show_alert=True)
        return
    api = HeroSMSAPI(config.HEROSMS_API_KEY, config.HEROSMS_BASE_URL)
    try:
        bal = await api.get_balance()
        text = f"🔑 <b>יתרת HeroSMS</b>\n\n<b>${bal:.4f}</b>"
    except Exception as e:
        text = f"❌ שגיאה: {e}"
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_admin_kb())
    await cb.answer()


@router.callback_query(F.data == "adm_users")
async def cb_users(cb: CallbackQuery, db: Database, config: Config):
    if not is_admin(cb.from_user.id, config):
        await cb.answer("⛔", show_alert=True)
        return
    users = await db.all_users()
    lines = [f"👥 <b>משתמשים</b> ({len(users)} סה\"כ)\n"]
    for u in users[:30]:
        banned = "🚫 " if u.get("is_banned") else ""
        lines.append(
            f"{banned}<code>{u['user_id']}</code> — "
            f"@{u.get('username') or '—'} | "
            f"💰${u['balance']:.2f}"
        )
    await cb.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=back_to_admin_kb())
    await cb.answer()


@router.callback_query(F.data == "adm_orders")
async def cb_adm_orders(cb: CallbackQuery, db: Database, config: Config):
    if not is_admin(cb.from_user.id, config):
        await cb.answer("⛔", show_alert=True)
        return
    orders = await db.all_orders(limit=20)
    STATUS_EMOJI = {"active": "🟡", "pending": "⏳", "code_received": "🟢", "completed": "✅", "cancelled": "❌"}
    lines = ["📋 <b>הזמנות אחרונות</b>\n"]
    for o in orders:
        emoji = STATUS_EMOJI.get(o["status"], "❓")
        lines.append(f"{emoji} <b>#{o['id']}</b> uid:{o['user_id']} [{o['service']}] ${o['charged_price']:.2f}")
    await cb.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=back_to_admin_kb())
    await cb.answer()


@router.callback_query(F.data == "adm_pending_topups")
async def cb_pending_topups(cb: CallbackQuery, db: Database, config: Config):
    if not is_admin(cb.from_user.id, config):
        await cb.answer("⛔", show_alert=True)
        return
    payments = await db.pending_payments()
    if not payments:
        await cb.message.edit_text("✅ אין טעינות ממתינות.", reply_markup=back_to_admin_kb())
        await cb.answer()
        return
    from keyboards import confirm_topup_kb
    for p in payments:
        await cb.message.answer(
            f"💳 <b>תשלום #{p['id']}</b>\n"
            f"משתמש: <code>{p['user_id']}</code>\n"
            f"סכום: ${p['amount']:.2f}\n"
            f"שיטה: {p['method']}\n"
            f"הערה: {p.get('note') or '—'}\n"
            f"תאריך: {p['created_at']}",
            parse_mode="HTML",
            reply_markup=confirm_topup_kb(p['id'])
        )
    await cb.answer()


@router.callback_query(F.data.startswith("adm_confirm_payment:"))
async def cb_confirm_payment(cb: CallbackQuery, db: Database, config: Config):
    if not is_admin(cb.from_user.id, config):
        await cb.answer("⛔", show_alert=True)
        return
    payment_id = int(cb.data.split(":")[1])
    p = await db.confirm_payment(payment_id)
    await cb.message.edit_text(f"✅ תשלום #{payment_id} אושר.")
    if p:
        try:
            await cb.message.bot.send_message(
                p["user_id"],
                f"✅ <b>היתרה עודכנה!</b>\n\n"
                f"<b>${p['amount']:.2f}</b> נוספו לחשבונך.\n"
                f"מזהה תשלום: #{payment_id}",
                parse_mode="HTML"
            )
        except Exception:
            pass
    await cb.answer("✅ אושר!")


@router.callback_query(F.data.startswith("adm_reject_payment:"))
async def cb_reject_payment(cb: CallbackQuery, db: Database, config: Config):
    if not is_admin(cb.from_user.id, config):
        await cb.answer("⛔", show_alert=True)
        return
    payment_id = int(cb.data.split(":")[1])
    async with aiosqlite.connect(db.path) as conn:
        await conn.execute("UPDATE payments SET status='rejected' WHERE id=?", (payment_id,))
        await conn.commit()
    await cb.message.edit_text(f"❌ תשלום #{payment_id} נדחה.")
    await cb.answer("נדחה.")


@router.callback_query(F.data == "adm_add_balance")
async def cb_adm_add_balance(cb: CallbackQuery, config: Config, state: FSMContext):
    if not is_admin(cb.from_user.id, config):
        await cb.answer("⛔", show_alert=True)
        return
    await state.set_state(AdminState.adding_balance_user)
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="❌ ביטול", callback_data="admin_menu"))
    await cb.message.edit_text(
        "💳 <b>הוספת יתרה</b>\n\nשלח את ה-ID של המשתמש:",
        parse_mode="HTML", reply_markup=kb.as_markup()
    )
    await cb.answer()


@router.message(AdminState.adding_balance_user)
async def adm_balance_user_id(message: Message, state: FSMContext, config: Config, db: Database):
    if not is_admin(message.from_user.id, config):
        return
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ ID לא תקין.")
        return
    user = await db.get_user(user_id)
    if not user:
        await message.answer(f"❌ משתמש {user_id} לא נמצא.")
        return
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminState.adding_balance_amount)
    await message.answer(
        f"משתמש: <b>{user.get('full_name', '—')}</b> (@{user.get('username', '—')})\n"
        f"יתרה נוכחית: <b>${user['balance']:.2f}</b>\n\n"
        f"הכנס סכום להוספה (לדוגמה: <code>5.00</code>):",
        parse_mode="HTML"
    )


@router.message(AdminState.adding_balance_amount)
async def adm_balance_amount(message: Message, state: FSMContext, config: Config, db: Database):
    if not is_admin(message.from_user.id, config):
        return
    try:
        amount = float(message.text.strip())
    except ValueError:
        await message.answer("❌ סכום לא תקין.")
        return
    data = await state.get_data()
    user_id = data["target_user_id"]
    new_bal = await db.update_balance(user_id, amount)
    await db.create_payment(user_id, amount, "manual", note="זיכוי ידני מאדמין")
    await message.answer(
        f"✅ נוספו <b>${amount:.2f}</b> למשתמש <code>{user_id}</code>.\n"
        f"יתרה חדשה: <b>${new_bal:.2f}</b>",
        parse_mode="HTML", reply_markup=admin_menu_kb()
    )
    try:
        await message.bot.send_message(
            user_id,
            f"🎁 <b>${amount:.2f}</b> נוספו ליתרתך על ידי מנהל!",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await state.clear()


@router.callback_query(F.data == "adm_ban")
async def cb_adm_ban(cb: CallbackQuery, config: Config, state: FSMContext):
    if not is_admin(cb.from_user.id, config):
        await cb.answer("⛔", show_alert=True)
        return
    await state.set_state(AdminState.banning_user)
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="❌ ביטול", callback_data="admin_menu"))
    await cb.message.edit_text(
        "🚫 <b>חסום/שחרר משתמש</b>\n\nשלח את ה-ID:",
        parse_mode="HTML", reply_markup=kb.as_markup()
    )
    await cb.answer()


@router.message(AdminState.banning_user)
async def adm_ban_user(message: Message, state: FSMContext, config: Config, db: Database):
    if not is_admin(message.from_user.id, config):
        return
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ ID לא תקין.")
        return
    user = await db.get_user(user_id)
    if not user:
        await message.answer("❌ משתמש לא נמצא.")
        return
    new_ban = not bool(user.get("is_banned"))
    await db.ban_user(user_id, new_ban)
    status = "🚫 נחסם" if new_ban else "✅ שוחרר"
    await message.answer(f"{status} משתמש <code>{user_id}</code>.", parse_mode="HTML", reply_markup=admin_menu_kb())
    await state.clear()


@router.callback_query(F.data == "adm_broadcast")
async def cb_adm_broadcast(cb: CallbackQuery, config: Config, state: FSMContext):
    if not is_admin(cb.from_user.id, config):
        await cb.answer("⛔", show_alert=True)
        return
    await state.set_state(AdminState.broadcasting)
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="❌ ביטול", callback_data="admin_menu"))
    await cb.message.edit_text(
        "📣 <b>שידור לכולם</b>\n\nשלח את ההודעה לשידור:",
        parse_mode="HTML", reply_markup=kb.as_markup()
    )
    await cb.answer()


@router.message(AdminState.broadcasting)
async def adm_broadcast(message: Message, state: FSMContext, config: Config, db: Database):
    if not is_admin(message.from_user.id, config):
        return
    users = await db.all_users()
    sent = failed = 0
    for u in users:
        try:
            await message.bot.send_message(
                u["user_id"],
                f"📣 <b>הודעה מהמנהל</b>\n\n{message.text}",
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            failed += 1
    await message.answer(
        f"📣 השידור הסתיים.\n✅ נשלח: {sent} | ❌ נכשל: {failed}",
        reply_markup=admin_menu_kb()
    )
    await state.clear()
