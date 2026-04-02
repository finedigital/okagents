import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters,
)

from agent import get_signal_response, should_research
from okx import place_market_buy, get_token_price
from db import init_db, save_user, get_user
import config

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

init_db()

pending_trades = {}   # "chat_id:user_id" -> {user_id, inst_id, usd_sz}
conversations = {}    # "chat_id:user_id" -> message history

MIN_TRADE_USD = 1
MAX_TRADE_USD = 1000


async def cmd_start(update: Update, context):
    await update.message.reply_text(
        "I'm OKArthur. Add me to your group and @mention me for macro signal.\n"
        "Use /connect to link your OKX account."
    )


async def cmd_connect(update: Update, context):
    """Usage: /connect KEY SECRET PASSPHRASE (DM only)"""
    if update.message.chat.type != "private":
        await update.message.reply_text(
            "\u26a0\ufe0f For security, use /connect in a private message to me."
        )
        return

    parts = context.args
    if len(parts) != 3:
        await update.message.reply_text(
            "Usage: /connect <api_key> <secret> <passphrase>"
        )
        return

    save_user(str(update.effective_user.id), *parts)
    await update.message.reply_text(
        "\u2705 OKX account linked. You're ready to trade."
    )


async def handle_message(update: Update, context):
    if not update.message or not update.message.text:
        return

    text = update.message.text
    bot_me = await context.bot.get_me()
    bot_username = bot_me.username

    # Check for @mention via entities (reliable) or text fallback
    is_private = update.message.chat.type == "private"
    is_mentioned = is_private
    if not is_mentioned and update.message.entities:
        for entity in update.message.entities:
            if entity.type == "mention":
                mentioned = text[entity.offset:entity.offset + entity.length]
                if mentioned.lower() == f"@{bot_username.lower()}":
                    is_mentioned = True
                    break
            elif entity.type == "text_mention" and entity.user and entity.user.id == bot_me.id:
                is_mentioned = True
                break

    if not is_mentioned:
        return

    logger.info("Received mention from user %s in chat %s", update.effective_user.id, update.effective_chat.id)

    chat_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)
    history_key = f"{chat_id}:{user_id}"

    # Detect trade intent: "buy $200 btc", "buy $50 in avax", "sell avax $50", etc.
    SUPPORTED_TOKENS = (
        "btc|eth|avax|sol|xrp|ada|doge|bnb|bch|ltc|link|uni|aave|"
        "matic|dot|shib|trx|usdt|usdc|fil|atom"
    )

    # Phase A: detect action + amount
    trade_match = re.search(
        r"\b(buy|sell)\b.*?\$?(\d+(?:\.\d+)?)", text.lower()
    )

    # Phase B: detect token anywhere in message as a standalone word
    token = None
    if trade_match:
        token_matches = re.findall(rf"\b({SUPPORTED_TOKENS})\b", text.lower())
        for t in token_matches:
            if t not in ("usdt", "usdc"):
                token = t
                break

    logger.info(
        "Message text: %r | Trade match: %s | Token: %s",
        text,
        trade_match.groups() if trade_match else None,
        token,
    )

    if trade_match:
        action, amount = trade_match.groups()
        usd_amount = float(amount)

        if usd_amount < MIN_TRADE_USD or usd_amount > MAX_TRADE_USD:
            await update.message.reply_text(
                f"\u26a0\ufe0f Trade amount must be between ${MIN_TRADE_USD} and ${MAX_TRADE_USD}."
            )
            return

        if token is None:
            await update.message.reply_text(
                "\u26a0\ufe0f Couldn't identify the token. "
                'Please specify, e.g. "buy $50 avax" or "sell $200 btc".'
            )
            return

        inst_id = f"{token.upper()}-USDT"

        try:
            price = get_token_price(token)
        except Exception:
            await update.message.reply_text(
                f"\u26a0\ufe0f Couldn't fetch price for {token.upper()}-USDT. "
                "Check the token and try again."
            )
            return

        pending_trades[f"{chat_id}:{user_id}"] = {
            "inst_id": inst_id,
            "usd_sz": usd_amount,
            "user_id": user_id,
        }

        keyboard = [
            [
                InlineKeyboardButton(
                    "\u2705 Yes, execute",
                    callback_data=f"confirm:{chat_id}:{user_id}",
                ),
                InlineKeyboardButton(
                    "\u274c Cancel",
                    callback_data=f"cancel:{chat_id}:{user_id}",
                ),
            ]
        ]

        price_fmt = f"${price:,.2f}" if price < 10 else f"${price:,.0f}"
        await update.message.reply_text(
            f"\U0001f7e0 OKArthur: Confirm {action} ${amount} "
            f"{inst_id.split('-')[0]} at {price_fmt} on OKX?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        # Signal request — run OKArthur
        history = conversations.get(history_key, [])

        # Send placeholder if deep research is needed (takes 1-3 min)
        if should_research(text):
            placeholder = await update.message.reply_text(
                "\U0001f7e0 OKArthur: Researching Arthur's latest... one moment."
            )

        response = get_signal_response(text, history)
        conversations[history_key] = (
            history
            + [
                {"role": "user", "content": text},
                {"role": "assistant", "content": response},
            ]
        )[-10:]  # Keep last 5 turns

        if should_research(text):
            await placeholder.edit_text(f"\U0001f7e0 OKArthur: {response}")
        else:
            await update.message.reply_text(f"\U0001f7e0 OKArthur: {response}")


async def handle_callback(update: Update, context):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        return

    action, chat_id, user_id = query.data.split(":")

    # Only the user who initiated the trade can confirm/cancel
    if str(update.effective_user.id) != user_id:
        return

    if action == "cancel":
        pending_trades.pop(f"{chat_id}:{user_id}", None)
        await query.edit_message_text("\u274c Trade cancelled.")
        return

    key = f"{chat_id}:{user_id}"
    trade = pending_trades.pop(key, None)
    if not trade:
        await query.edit_message_text("\u26a0\ufe0f Trade expired or not found.")
        return

    user_creds = get_user(user_id)
    if not user_creds:
        await query.edit_message_text(
            "\u26a0\ufe0f No OKX account linked. Use /connect first."
        )
        return

    result = place_market_buy(trade["inst_id"], trade["usd_sz"], user_creds)

    if result.get("code") == "0":
        await query.edit_message_text(
            f"\u2705 Done. ${trade['usd_sz']} {trade['inst_id'].split('-')[0]} "
            f"bought on OKX. Arthur would approve."
        )
    else:
        data = result.get("data", [{}])
        detail = data[0].get("sMsg") if data else None
        error_msg = detail or result.get("msg", "Unknown error")
        await query.edit_message_text(f"\u274c Order failed: {error_msg}")


app = Application.builder().token(config.BOT_TOKEN).build()
app.add_handler(CommandHandler("start", cmd_start))
app.add_handler(CommandHandler("connect", cmd_connect))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
app.add_handler(CallbackQueryHandler(handle_callback))

if __name__ == "__main__":
    import asyncio

    async def main():
        async with app:
            await app.initialize()
            await app.start()
            await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            logger.info("OKArthur bot is running.")
            await asyncio.Event().wait()

    asyncio.run(main())
