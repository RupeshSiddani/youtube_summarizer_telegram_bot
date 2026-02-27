"""
bot.py
Entry point — builds and starts the Telegram bot.
"""

import os
import logging
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from handlers.command_handler import (
    cmd_start,
    cmd_help,
    cmd_summary,
    cmd_deepdive,
    cmd_actionpoints,
    cmd_reset,
)
from handlers.link_handler import handle_link
from handlers.qa_handler import handle_question
from services import session as sess

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Load environment variables ─────────────────────────────────────────────
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    raise ValueError(
        "TELEGRAM_TOKEN is not set. Please add it to your .env file.\n"
        "Get your token from @BotFather on Telegram."
    )


# ── Message router ────────────────────────────────────────────────────────
async def route_message(update: Update, context) -> None:
    """Route text messages: YouTube URL → link_handler, else → qa_handler."""
    from utils.url_parser import is_youtube_url
    text = update.message.text or ""
    if is_youtube_url(text):
        await handle_link(update, context)
    else:
        await handle_question(update, context)


# ── Global error handler ──────────────────────────────────────────────────
async def error_handler(update: object, context) -> None:
    """Log errors and notify user if possible — bot keeps running."""
    logger.error("Exception while handling update:", exc_info=context.error)
    # Try to inform the user something went wrong
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ Something went wrong. Please try again."
            )
        except Exception:
            pass  # Don't crash if we can't send

# ── Periodic cleanup job ─────────────────────────────────────────────────
async def cleanup_job(context) -> None:
    """Runs every 30 minutes: removes expired sessions from memory."""
    removed = sess.cleanup_expired()
    active = sess.active_session_count()
    if removed > 0:
        logger.info(f"Session cleanup: removed {removed} expired sessions, {active} active")

def main() -> None:
    # Use larger timeouts to handle slow connections / Gemini processing time
    request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=60.0,
        write_timeout=60.0,
        pool_timeout=60.0,
    )

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .request(request)
        .build()
    )

    # Schedule periodic session cleanup every 30 minutes
    app.job_queue.run_repeating(cleanup_job, interval=1800, first=1800)

    # Slash commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(CommandHandler("deepdive", cmd_deepdive))
    app.add_handler(CommandHandler("actionpoints", cmd_actionpoints))
    app.add_handler(CommandHandler("reset", cmd_reset))

    # All text messages (URLs and questions)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, route_message)
    )

    # Global error handler — keeps bot alive on network errors
    app.add_error_handler(error_handler)

    logger.info("🚀 Bot is running. Press Ctrl+C to stop.")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,   # ignore messages sent while bot was offline
        poll_interval=2.0,
        timeout=20,
    )


if __name__ == "__main__":
    main()
