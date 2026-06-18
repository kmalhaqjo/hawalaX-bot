async def _save_usdt(update, ctx, uid, d):
    """ذخیره معامله USDT"""
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

    # آپدیت موجودی
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

    # نشر در کانال
    await ctx.bot.send_message(CHANNEL_ID, fmt_usdt(t))


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════
def main():
    load_store()
    logging.basicConfig(level=logging.INFO)

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("report",  cmd_report))
    app.add_handler(CommandHandler("pending", cmd_pending))
    app.add_handler(CommandHandler("rate",    cmd_rate))

    # Buttons
    app.add_handler(CallbackQueryHandler(callback_form,  pattern="^(cur_|par_|net_)"))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

   print("🚀 HawalaX Bot شروع به کار کرد!")
    app.run_polling()  # ← 4 فاصله indent

if name == "__main__":
    main()
