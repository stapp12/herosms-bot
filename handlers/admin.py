"""
Admin panel handlers.
Access via /admin command – only for users in ADMIN_IDS.
"""

import logging
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
    adding_balance_user  = State()
    adding_balance_amount = State()
    banning_user         = State()
    broadcasting         = State()


# ── /admin ─────────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message, config: Config):
    if not is_admin(message.from_user.id, config):
        return
    await message.answer(
        "🔐 <b>Admin Panel</b>",
        parse_mode="HTML",
        reply_markup=admin_menu_kb()
    )


@router.callback_query(F.data == "admin_menu")
async def cb_admin_menu(cb: CallbackQuery, config: Config):
    if not is_admin(cb.from_user.id, config):
        await cb.answer("⛔ Not authorized.", show_alert=True)
        return
    await cb.message.edit_text(
        "🔐 <b>Admin Panel</b>",
        parse_mode="HTML",
        reply_markup=admin_menu_kb()
    )
    await cb.answer()


# ── Stats ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_stats")
async def cb_stats(cb: CallbackQuery, db: Database, config: Config):
    if not is_admin(cb.from_user.id, config):
        await cb.answer("⛔", show_alert=True)
        return
    stats = await db.stats()
    text = (
        f"📊 <b>Bot Statistics</b>\n\n"
        f"👥 Total Users: <b>{stats['total_users']}</b>\n"
        f"📋 Total Orders: <b>{stats['total_orders']}</b>\n"
        f"✅ Active Orders: <b>{stats['active_orders']}</b>\n"
        f"💰 Total Revenue: <b>${stats['total_revenue']:.2f}</b>\n"
        f"⏳ Pending Top-Ups: <b>{stats['pending_topups']}</b>"
    )
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_admin_kb())
    await cb.answer()


# ── HeroSMS API balance ────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_api_balance")
async def cb_api_balance(cb: CallbackQuery, config: Config):
    if not is_admin(cb.from_user.id, config):
        await cb.answer("⛔", show_alert=True)
        return
    api = HeroSMSAPI(config.HEROSMS_API_KEY, config.HEROSMS_BASE_URL)
    try:
        bal = await api.get_balance()
        text = f"🔑 <b>HeroSMS API Balance</b>\n\n<b>${bal:.4f}</b>"
    except Exception as e:
        text = f"❌ Error: {e}"
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_admin_kb())
    await cb.answer()


# ── Users list ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_users")
async def cb_users(cb: CallbackQuery, db: Database, config: Config):
    if not is_admin(cb.from_user.id, config):
        await cb.answer("⛔", show_alert=True)
        return
    users = await db.all_users()
    lines = [f"👥 <b>All Users</b> ({len(users)} total)\n"]
    for u in users[:30]:
        banned = "🚫 " if u.get("is_banned") else ""
        lines.append(
            f"{banned}<code>{u['user_id']}</code> — "
            f"@{u.get('username') or '—'} | "
            f"💰${u['balance']:.2f}"
        )
    await cb.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=back_to_admin_kb())
    await cb.answer()


# ── Recent orders ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_orders")
async def cb_adm_orders(cb: CallbackQuery, db: Database, config: Config):
    if not is_admin(cb.from_user.id, config):
        await cb.answer("⛔", show_alert=True)
        return
    orders = await db.all_orders(limit=20)
    STATUS_EMOJI = {
        "active": "🟡", "pending": "⏳", "code_received": "🟢",
        "completed": "✅", "cancelled": "❌"
    }
    lines = [f"📋 <b>Recent Orders</b>\n"]
    for o in orders:
        emoji = STATUS_EMOJI.get(o["status"], "❓")
        lines.append(
            f"{emoji} <b>#{o['id']}</b> uid:{o['user_id']} "
            f"[{o['service']}] ${o['charged_price']:.2f}"
        )
    await cb.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=back_to_admin_kb())
    await cb.answer()


# ── Pending top-ups ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_pending_topups")
async def cb_pending_topups(cb: CallbackQuery, db: Database, config: Config):
    if not is_admin(cb.from_user.id, config):
        await cb.answer("⛔", show_alert=True)
        return
    payments = await db.pending_payments()
    if not payments:
        await cb.message.edit_text("✅ No pending top-ups.", reply_markup=back_to_admin_kb())
        await cb.answer()
        return

    for p in payments:
        from keyboards import confirm_topup_kb
        await cb.message.answer(
            f"💳 <b>Payment #{p['id']}</b>\n"
            f"User: <code>{p['user_id']}</code>\n"
            f"Amount: ${p['amount']:.2f}\n"
            f"Method: {p['method']}\n"
            f"Note: {p.get('note') or '—'}\n"
            f"Date: {p['created_at']}",
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
    await db.confirm_payment(payment_id)

    # Find payment to notify user
    async with __import__("aiosqlite").connect(db.path) as conn:
        conn.row_factory = __import__("aiosqlite").Row
        async with conn.execute("SELECT * FROM payments WHERE id=?", (payment_id,)) as cur:
            p = await cur.fetchone()
            p = dict(p) if p else {}

    await cb.message.edit_text(f"✅ Payment #{payment_id} confirmed.")
    if p:
        try:
            await cb.message.bot.send_message(
                p["user_id"],
                f"✅ <b>Balance Added!</b>\n\n"
                f"<b>${p['amount']:.2f}</b> has been added to your account.\n"
                f"Payment ID: #{payment_id}",
                parse_mode="HTML"
            )
        except Exception:
            pass
    await cb.answer("✅ Confirmed!")


@router.callback_query(F.data.startswith("adm_reject_payment:"))
async def cb_reject_payment(cb: CallbackQuery, db: Database, config: Config):
    if not is_admin(cb.from_user.id, config):
        await cb.answer("⛔", show_alert=True)
        return
    payment_id = int(cb.data.split(":")[1])
    import aiosqlite
    async with aiosqlite.connect(db.path) as conn:
        await conn.execute("UPDATE payments SET status='rejected' WHERE id=?", (payment_id,))
        await conn.commit()
    await cb.message.edit_text(f"❌ Payment #{payment_id} rejected.")
    await cb.answer("Rejected.")


# ── Add balance manually ───────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_add_balance")
async def cb_adm_add_balance(cb: CallbackQuery, config: Config, state: FSMContext):
    if not is_admin(cb.from_user.id, config):
        await cb.answer("⛔", show_alert=True)
        return
    await state.set_state(AdminState.adding_balance_user)
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="❌ Cancel", callback_data="admin_menu"))
    await cb.message.edit_text(
        "💳 <b>Add Balance</b>\n\nSend the user's Telegram ID:",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
    await cb.answer()


@router.message(AdminState.adding_balance_user)
async def adm_balance_user_id(message: Message, state: FSMContext, config: Config, db: Database):
    if not is_admin(message.from_user.id, config):
        return
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Invalid user ID.")
        return
    user = await db.get_user(user_id)
    if not user:
        await message.answer(f"❌ User {user_id} not found.")
        return
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminState.adding_balance_amount)
    await message.answer(
        f"User: <b>{user.get('full_name', '—')}</b> (@{user.get('username', '—')})\n"
        f"Current balance: <b>${user['balance']:.2f}</b>\n\n"
        f"Enter amount to add (e.g. <code>5.00</code>):",
        parse_mode="HTML"
    )


@router.message(AdminState.adding_balance_amount)
async def adm_balance_amount(message: Message, state: FSMContext, config: Config, db: Database):
    if not is_admin(message.from_user.id, config):
        return
    try:
        amount = float(message.text.strip())
    except ValueError:
        await message.answer("❌ Invalid amount.")
        return
    data = await state.get_data()
    user_id = data["target_user_id"]
    new_bal = await db.update_balance(user_id, amount)
    await db.create_payment(user_id, amount, "manual", note="Admin manual credit")

    await message.answer(
        f"✅ Added <b>${amount:.2f}</b> to user <code>{user_id}</code>.\n"
        f"New balance: <b>${new_bal:.2f}</b>",
        parse_mode="HTML",
        reply_markup=admin_menu_kb()
    )
    try:
        await message.bot.send_message(
            user_id,
            f"🎁 <b>${amount:.2f}</b> has been added to your balance by admin!",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await state.clear()


# ── Ban user ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_ban")
async def cb_adm_ban(cb: CallbackQuery, config: Config, state: FSMContext):
    if not is_admin(cb.from_user.id, config):
        await cb.answer("⛔", show_alert=True)
        return
    await state.set_state(AdminState.banning_user)
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="❌ Cancel", callback_data="admin_menu"))
    await cb.message.edit_text(
        "🚫 <b>Ban/Unban User</b>\n\nSend the user ID to toggle ban:",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
    await cb.answer()


@router.message(AdminState.banning_user)
async def adm_ban_user(message: Message, state: FSMContext, config: Config, db: Database):
    if not is_admin(message.from_user.id, config):
        return
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Invalid user ID.")
        return
    user = await db.get_user(user_id)
    if not user:
        await message.answer("❌ User not found.")
        return
    new_ban = not bool(user.get("is_banned"))
    await db.ban_user(user_id, new_ban)
    status = "🚫 Banned" if new_ban else "✅ Unbanned"
    await message.answer(f"{status} user <code>{user_id}</code>.", parse_mode="HTML", reply_markup=admin_menu_kb())
    await state.clear()


# ── Broadcast ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_broadcast")
async def cb_adm_broadcast(cb: CallbackQuery, config: Config, state: FSMContext):
    if not is_admin(cb.from_user.id, config):
        await cb.answer("⛔", show_alert=True)
        return
    await state.set_state(AdminState.broadcasting)
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="❌ Cancel", callback_data="admin_menu"))
    await cb.message.edit_text(
        "📣 <b>Broadcast</b>\n\nSend the message to broadcast to all users:",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
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
                f"📣 <b>Announcement</b>\n\n{message.text}",
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            failed += 1
    await message.answer(
        f"📣 Broadcast complete.\n✅ Sent: {sent} | ❌ Failed: {failed}",
        reply_markup=admin_menu_kb()
    )
    await state.clear()
