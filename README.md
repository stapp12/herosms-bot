# 🤖 HeroSMS Reseller Telegram Bot

A fully-featured Telegram bot that resells virtual phone numbers from **hero-sms.com**
with your custom markup. Includes crypto & manual payments and a complete admin panel.

---

## 📁 Files

```
herosms_bot/
├── bot.py          # Entry point
├── config.py       # All settings loaded from .env
├── database.py     # SQLite async DB layer
├── herosms.py      # HeroSMS API wrapper
├── keyboards.py    # All inline keyboards with emojis
├── handlers/
│   ├── user.py     # Buy flow, orders, balance
│   ├── payment.py  # Crypto (NOWPayments) & manual top-up
│   └── admin.py    # Admin panel
├── requirements.txt
└── .env.example    # Copy to .env and fill in
```

---

## 🚀 Setup

### 1. Clone & install

```bash
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
nano .env
```

Fill in:
| Variable | Description |
|---|---|
| `BOT_TOKEN` | From [@BotFather](https://t.me/BotFather) |
| `HEROSMS_API_KEY` | From [hero-sms.com/profile](https://hero-sms.com/profile) |
| `MARKUP` | Flat USD markup per number (e.g. `0.10`) |
| `MARKUP_PCT` | % markup instead (e.g. `20` = 20%). Set to 0 to use flat. |
| `ADMIN_IDS` | Your Telegram user ID (get it from @userinfobot) |
| `NOWPAYMENTS_API_KEY` | From [nowpayments.io](https://nowpayments.io) (optional) |

### 3. Run

```bash
python bot.py
```

---

## 💰 Pricing Logic

For each number, you pay HeroSMS `base_price` and charge users `final_price`:

- **Flat markup**: `final_price = base_price + MARKUP`
- **Percentage**: `final_price = base_price × (1 + MARKUP_PCT/100)`

Example: HeroSMS charges $0.15 → with `MARKUP=0.10` → you charge $0.25.

---

## 👤 User Features

| Feature | Details |
|---|---|
| 📱 Buy Number | Browse 700+ services × 180+ countries |
| 🔄 Check SMS | Poll for code in real-time |
| 🔁 New Code | Request another code (free) |
| ❌ Cancel | Cancel & auto-refund |
| 💰 Balance | View current balance |
| ➕ Top Up | Crypto (auto) or manual (admin confirms) |
| 🕐 My Orders | View recent order history |

---

## 🔐 Admin Panel (`/admin`)

| Feature | Details |
|---|---|
| 📊 Stats | Users, orders, revenue, active orders |
| 👥 Users | List all users with balances |
| 💳 Add Balance | Manually credit any user |
| 🚫 Ban/Unban | Toggle user access |
| ⏳ Pending Top-Ups | Review & confirm/reject manual payments |
| 📣 Broadcast | Send message to all users |
| 🔑 API Balance | Check your HeroSMS account balance |

---

## 🪙 Crypto Payments

Uses [NOWPayments](https://nowpayments.io):
1. Sign up and get an API key
2. Set `NOWPAYMENTS_API_KEY` in `.env`
3. (Optional) Set up an IPN webhook for automatic confirmation

Without NOWPayments, users can still request manual top-ups.

---

## 🔧 Production Tips

- Run with `systemd` or `screen`/`tmux` for persistence
- Back up `herosms_bot.db` regularly
- Use a VPS with low latency to Telegram servers
- Monitor your HeroSMS balance regularly (use the admin panel)
