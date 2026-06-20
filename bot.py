#!/usr/bin/env python3
"""
HawalaX Telegram Bot
BakarExchange — صرافی حاجی کمال حقجو
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from datetime import datetime
import json, os

# ═══════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════
# CONFIG — مقادیر از environment variables خوانده می‌شوند
# ═══════════════════════════════════════════
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip().strip('"').strip("'")

_channel_raw = os.getenv("CHANNEL_ID", "").strip().strip('"').strip("'").strip()
try:
    CHANNEL_ID = int(_channel_raw) if _channel_raw else 0
except ValueError:
    logger.error(f"❌ CHANNEL_ID must be a number, got: '{_channel_raw}'")
    raise RuntimeError(f"CHANNEL_ID must be a number, got: '{_channel_raw}'")

ADMIN_IDS = [909200283]

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN is not set. Add it in Railway environment variables.")
    raise RuntimeError("BOT_TOKEN environment variable is not set!")
if not CHANNEL_ID:
    logger.error("❌ CHANNEL_ID is not set. Add it in Railway environment variables.")
    raise RuntimeError("CHANNEL_ID environment variable is not set!")

logger.info(f"✅ BOT_TOKEN loaded (ends: ...{BOT_TOKEN[-6:]})")
logger.info(f"✅ CHANNEL_ID loaded: {CHANNEL_ID}")

# ═══════════════════════════════════════════
# DATA STORE — در production از دیتابیس استفاده شود
# ═══════════════════════════════════════════
store = {
    "rates":      {"sar_buy": 3.82, "sar_sell": 3.90, "usd_afn": 71.5},
    "balances":   {"usdt": 1250.0, "usd": 2340.0, "sar": 42800.0},
    "remittances": [],
    "usdt_trades": [],
    "next_id":    119,
    "next_uid":   43,
}

def save_store():
    with open("hawalaX_data.json", "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)

def load_store():
    global store
    if os.path.exists("hawalaX_data.json"):
        with open("hawalaX_data.json", "r", encoding="utf-8") as f:
            store.update(json.load(f))

def is_admin(user_id):
    return user_id in ADMIN_IDS

def now_str():
    return datetime.now().strftime("%d/%m %H:%M")

def date_str():
    return datetime.now().strftime("%d/%m/%Y")

# ═══════════════════════════════════════════
# FORMATTERS — فرمت پیام‌های تلگرام
# ═══════════════════════════════════════════
def fmt_remittance(r):
    status_map = {
        "pending": "⏳ در انتظار اجرا",
        "done":    "✅ اجرا شد",
        "problem": "⚠️ مشکل دارد",
    }
    return f"""━━━━━━━━━━━━━━━━━━━
🧾 حواله شماره #{r['id']}
━━━━━━━━━━━━━━━━━━━
👤 فرستنده : {r['sender']}
👤 گیرنده  : {r['receiver']}
📞 تماس    : {r.get('phone', '—')}
💰 مبلغ    : {r['amount']:,} {r['currency']}
📍 مقصد    : {r['dest']}
🏦 صرافی   : {r['partner']}
⏰ زمان    : {r['time']}
━━━━━━━━━━━━━━━━━━━
{status_map.get(r['status'], '⏳ در انتظار')}"""

def fmt_usdt(t):
    type_label = "🟢 خرید USDT" if t['type'] == "buy" else "📤 ارسال USDT"
    detail = f"💵 پرداخت: {t.get('sar', 0):,} SR" if t['type'] == "buy" else f"💵 معادل: ${t.get('usd', 0):,}"
    return f"""━━━━━━━━━━━━━━━━━━━
💎 {type_label} #{t['id']}
━━━━━━━━━━━━━━━━━━━
👤 {'از' if t['type'] == 'buy' else 'به'} : {t['person']}
🪙 مقدار  : {t['amount']} USDT
💱 نرخ    : {t['rate']} SR
{detail}
📡 شبکه   : {t.get('network', 'TRC20')}
⏰ زمان   : {t['time']}
━━━━━━━━━━━━━━━━━━━
⏳ در انتظار تأیید"""

def fmt_balance():
    b = store["balances"]
    r = store["rates"]
    return f"""━━━━━━━━━━━━━━━━━━━
🏦 وضعیت موجودی
━━━━━━━━━━━━━━━━━━━
💎 USDT  : {b['usdt']:,}
💵 دالر  : ${b['usd']:,.0f}
🇸🇦 ریال : {b['sar']:,.0f} SR
━━━━━━━━━━━━━━━━━━━
💱 نرخ امروز:
  خرید  : {r['sar_buy']} SR
  فروش  : {r['sar_sell']} SR
  AFN   : {r['usd_afn']}
━━━━━━━━━━━━━━━━━━━
📅 {now_str()}"""

def fmt_daily_report():
    today = date_str()
    remits = [r for r in store["remittances"] if today in r.get('time', '')]
    usdt_buys = [t for t in store["usdt_trades"] if t['type'] == 'buy' and today in t.get('time', '')]
    total_usdt = sum(t['amount'] for t in usdt_buys)
    pending = [r for r in store["remittances"] if r['status'] == 'pending']
    done = [r for r in remits if r['status'] == 'done']
    profit = sum(
        (t['amount'] * (store['rates']['sar_sell'] - store['rates']['sar_buy']))
        for t in usdt_buys
    )
    return f"""━━━━━━━━━━━━━━━━━━━
📊 گزارش روز | {today}
━━━━━━━━━━━━━━━━━━━
🧾 حواله امروز   : {len(remits)}
✅ تکمیل شده    : {len(done)}
⏳ در انتظار    : {len(pending)}
━━━━━━━━━━━━━━━━━━━
💎 USDT خرید    : {total_usdt:,}
📈 سود تقریبی   : ${profit:.1f}
━━━━━━━━━━━━━━━━━━━
💎 موجودی USDT  : {store['balances']['usdt']:,}
💵 موجودی USD   : ${store['balances']['usd']:,.0f}
🇸🇦 موجودی SAR  : {store['balances']['sar']:,.0f}
━━━━━━━━━━━━━━━━━━━
✅ روز خوبی داشتید 🤲"""

# ═══════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ دسترسی ندارید.")
        return
    keyboard = [
        [InlineKeyboardButton("🧾 حواله جدید", callback_data="new_remit"),
         InlineKeyboardButton("💎 USDT جدید", callback_data="new_usdt")],
        [InlineKeyboardButton("🏦 موجودی", callback_data="balance"),
         InlineKeyboardButton("📊 گزارش امروز", callback_data="report")],
        [InlineKeyboardButton("💱 تغییر نرخ", callback_data="set_rate"),
         InlineKeyboardButton("⏳ حواله‌های باز", callback_data="pending")],
    ]
    await update.message.reply_text(
        f"🌟 *HawalaX — BakarExchange*\n"
        f"صرافی حاجی کمال حقجو\n\n"
        f"📅 {now_str()}\n\n"
        f"چه کاری انجام دهم؟",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def cmd_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    await update.message.reply_text(fmt_balance())

async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    await update.message.reply_text(fmt_daily_report())

async def cmd_pending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    pending = [r for r in store["remittances"] if r['status'] == 'pending']
    if not pending:
        await update.message.reply_text("✅ هیچ حواله باز نیست!")
        return
    for r in pending:
        keyboard = [[
            InlineKeyboardButton("✅ اجرا شد", callback_data=f"confirm_{r['id']}"),
            InlineKeyboardButton("⚠️ مشکل", callback_data=f"problem_{r['id']}"),
        ]]
        await update.message.reply_text(
            fmt_remittance(r),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def cmd_rate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    args = ctx.args
    try:
        rates = {}
        for i in range(0, len(args)-1, 2):
            key, val = args[i], float(args[i+1])
            if key == "buy":   rates["sar_buy"] = val
            if key == "sell":  rates["sar_sell"] = val
            if key == "afn":   rates["usd_afn"] = val
        store["rates"].update(rates)
        save_store()
        await update.message.reply_text(
            f"✅ نرخ‌ها ذخیره شد!\n"
            f"خرید: {store['rates']['sar_buy']} SR\n"
            f"فروش: {store['rates']['sar_sell']} SR\n"
            f"AFN: {store['rates']['usd_afn']}"
        )
    except:
        await update.message.reply_text(
            "فرمت:\n/rate buy 3.82 sell 3.90 afn 71.5"
        )

# ═══════════════════════════════════════════
# CONVERSATION STATE
# ═══════════════════════════════════════════
user_state = {}

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    if not is_admin(uid):
        await query.edit_message_text("⛔ دسترسی ندارید.")
        return

    if data == "new_remit":
        user_state[uid] = {"step": "remit_sender", "data": {}}
        await query.edit_message_text(
            "🧾 *حواله جدید*\n\n👤 نام فرستنده را بنویسید:",
            parse_mode="Markdown"
        )

    elif data == "new_usdt":
        keyboard = [
            [InlineKeyboardButton("🟢 خرید USDT", callback_data="usdt_buy"),
             InlineKeyboardButton("📤 ارسال USDT", callback_data="usdt_send")],
        ]
        await query.edit_message_text(
            "💎 *معامله USDT*\n\nنوع معامله را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data in ["usdt_buy", "usdt_send"]:
        utype = "buy" if data == "usdt_buy" else "send"
        user_state[uid] = {"step": "usdt_person", "data": {"type": utype}}
        label = "از چه کسی می‌خرید" if utype == "buy" else "به چه کسی می‌فرستید"
        await query.edit_message_text(f"💎 {label}؟\n\nنام را بنویسید:")

    elif data == "balance":
        await query.edit_message_text(fmt_balance())

    elif data == "report":
        await query.edit_message_text(fmt_daily_report())

    elif data == "pending":
        pending = [r for r in store["remittances"] if r['status'] == 'pending']
        if not pending:
            await query.edit_message_text("✅ هیچ حواله باز نیست!")
        else:
            await query.edit_message_text(f"⏳ {len(pending)} حواله باز دارید.\n/pending را بزنید.")

    elif data.startswith("confirm_"):
        rid = int(data.split("_")[1])
        for r in store["remittances"]:
            if r['id'] == rid:
                r['status'] = 'done'
                save_store()
                await ctx.bot.send_message(
                    CHANNEL_ID,
                    f"✅ *حواله #{rid} اجرا شد!*\n"
                    f"👤 گیرنده: {r['receiver']}\n"
                    f"💰 مبلغ: {r['amount']:,} {r['currency']}\n"
                    f"📍 {r['dest']}\n"
                    f"⏰ {now_str()}",
                    parse_mode="Markdown"
                )
                await query.edit_message_text(f"✅ حواله #{rid} تأیید و در کانال نشر شد!")
                break

    elif data.startswith("problem_"):
        rid = int(data.split("_")[1])
        for r in store["remittances"]:
            if r['id'] == rid:
                r['status'] = 'problem'
                save_store()
                await query.edit_message_text(f"⚠️ حواله #{rid} مشکل‌دار ثبت شد.")
                break

    elif data == "set_rate":
        await query.edit_message_text(
            "💱 *تغییر نرخ*\n\n"
            "فرمت بنویسید:\n"
            "`/rate buy 3.82 sell 3.90 afn 71.5`",
            parse_mode="Markdown"
        )

# ═══════════════════════════════════════════
# MESSAGE HANDLER
# ═══════════════════════════════════════════
async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid): return
    text = update.message.text.strip()

    if uid not in user_state:
        await update.message.reply_text("برای شروع /start را بزنید.")
        return

    state = user_state[uid]
    step = state["step"]
    d = state["data"]

    if step == "remit_sender":
        d["sender"] = text
        state["step"] = "remit_receiver"
        await update.message.reply_text("👤 نام گیرنده را بنویسید:")

    elif step == "remit_receiver":
        d["receiver"] = text
        state["step"] = "remit_phone"
        await update.message.reply_text("📞 شماره تماس گیرنده (یا — بنویسید):")

    elif step == "remit_phone":
        d["phone"] = text
        state["step"] = "remit_amount"
        await update.message.reply_text("💰 مبلغ را بنویسید (فقط عدد):")

    elif step == "remit_amount":
        try:
            d["amount"] = float(text.replace(",", ""))
            state["step"] = "remit_currency"
            keyboard = [[
                InlineKeyboardButton("🇦🇫 AFN", callback_data="cur_AFN"),
                InlineKeyboardButton("💵 USD", callback_data="cur_USD"),
                InlineKeyboardButton("🇸🇦 SAR", callback_data="cur_SAR"),
            ]]
            await update.message.reply_text(
                "💱 ارز را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.message.reply_text("⚠️ فقط عدد بنویسید. دوباره:")

    elif step == "remit_dest":
        d["dest"] = text
        state["step"] = "remit_partner"
        keyboard = [[
            InlineKeyboardButton("حمیدی", callback_data="par_حمیدی"),
            InlineKeyboardButton("احمد نیازی", callback_data="par_احمد نیازی"),
            InlineKeyboardButton("جبار خان", callback_data="par_جبار خان"),
        ]]
        await update.message.reply_text(
            "🏦 کدام صرافی اجرا کند؟",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif step == "usdt_person":
        d["person"] = text
        state["step"] = "usdt_amount"
        await update.message.reply_text("💎 مقدار USDT (فقط عدد):")

    elif step == "usdt_amount":
        try:
            d["amount"] = float(text.replace(",", ""))
            state["step"] = "usdt_rate"
            await update.message.reply_text(
                f"💱 نرخ SAR:\n"
                f"(نرخ فعلی خرید: {store['rates']['sar_buy']})\n"
                f"عدد را بنویسید:"
            )
        except:
            await update.message.reply_text("⚠️ فقط عدد. دوباره:")

    elif step == "usdt_rate":
        try:
            d["rate"] = float(text)
            state["step"] = "usdt_network"
            keyboard = [[
                InlineKeyboardButton("TRC20", callback_data="net_TRC20"),
                InlineKeyboardButton("BEP20", callback_data="net_BEP20"),
                InlineKeyboardButton("ERC20", callback_data="net_ERC20"),
            ]]
            await update.message.reply_text(
                "📡 شبکه انتقال:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.message.reply_text("⚠️ فقط عدد. دوباره:")

    elif step == "usdt_txid":
        d["txid"] = text
        await _save_usdt(update, ctx, uid, d)


async def callback_form(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    if uid not in user_state:
        return
    state = user_state[uid]
    d = state["data"]

    if data.startswith("cur_"):
        d["currency"] = data[4:]
        state["step"] = "remit_dest"
        await query.edit_message_text("📍 شهر مقصد را بنویسید:")

    elif data.startswith("par_"):
        d["partner"] = data[4:]
        await _save_remittance(query, ctx, uid, d)

    elif data.startswith("net_"):
        d["network"] = data[4:]
        state["step"] = "usdt_txid"
        await query.edit_message_text("🔗 TXID تراکنش را بنویسید (یا — بنویسید):")


async def _save_remittance(query, ctx, uid, d):
    rid = store["next_id"]
    store["next_id"] += 1
    r = {
        "id": rid,
        "sender": d["sender"],
        "receiver": d["receiver"],
        "phone": d.get("phone", "—"),
        "amount": d["amount"],
        "currency": d["currency"],
        "dest": d["dest"],
        "partner": d["partner"],
        "status": "pending",
        "time": now_str(),
    }
    store["remittances"].insert(0, r)
    save_store()
    del user_state[uid]

    await query.edit_message_text(
        f"✅ حواله #{rid} ثبت شد!\n"
        f"در حال نشر در کانال..."
    )

    keyboard = [[
        InlineKeyboardButton("✅ اجرا شد", callback_data=f"confirm_{rid}"),
        InlineKeyboardButton("⚠️ مشکل", callback_data=f"problem_{rid}"),
    ]]
    await ctx.bot.send_message(
        CHANNEL_ID,
        fmt_remittance(r),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def _save_usdt(update, ctx, uid, d):
    tid = f"U-{store['next_uid']}"
    store["next_uid"] += 1
    t = {
        "id": tid,
        "type": d["type"],
        "person": d["person"],
        "amount": d["amount"],
        "rate": d["rate"],
        "sar": d["amount"] * d["rate"] if d["type"] == "buy" else 0,
        "usd": d["amount"] if d["type"] == "send" else 0,
        "network": d.get("network", "TRC20"),
        "txid": d.get("txid", "—"),
        "time": now_str(),
        "status": "pending",
    }
    store["usdt_trades"].insert(0, t)

    if d["type"] == "buy":
        store["balances"]["usdt"] += d["amount"]
        store["balances"]["sar"]  -= d["amount"] * d["rate"]
    else:
        store["balances"]["usdt"] -= d["amount"]

    save_store()
    del user_state[uid]

    await update.message.reply_text(
        f"✅ معامله {tid} ثبت شد!\n"
        f"{'خرید' if d['type'] == 'buy' else 'ارسال'}: {d['amount']} USDT\n"
        f"موجودی USDT: {store['balances']['usdt']:,}"
    )

    await ctx.bot.send_message(CHANNEL_ID, fmt_usdt(t))


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════
def main():
    load_store()
    logger.info("🚀 Starting HawalaX Bot...")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("report",  cmd_report))
    app.add_handler(CommandHandler("pending", cmd_pending))
    app.add_handler(CommandHandler("rate",    cmd_rate))

    app.add_handler(CallbackQueryHandler(callback_form,  pattern="^(cur_|par_|net_)"))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("✅ HawalaX Bot is running! (polling)")
    app.run_polling()


if __name__ == "__main__":
    main()

