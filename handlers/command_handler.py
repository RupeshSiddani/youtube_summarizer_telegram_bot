"""
handlers/command_handler.py
Handles all / slash commands.
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from services.llm import deepdive, action_points
from services import session as sess


# ── /start ────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    name = update.effective_user.first_name or "there"
    await update.message.reply_text(
        f"👋 Hi *{name}*! I'm your YouTube Research Assistant.\n\n"
        "📹 *Send me a YouTube link* and I'll:\n"
        "  • Summarize the video with key points\n"
        "  • Let you ask questions about it\n"
        "  • Respond in English or an Indian language\n\n"
        "🌐 *Language support:* English, Hindi, Tamil, Telugu, Kannada, Marathi\n"
        "  Just say *'Summarize in Hindi'* to switch.\n\n"
        "📌 *Commands:*\n"
        "  /summary — Show last summary\n"
        "  /deepdive — Deep analysis of the video\n"
        "  /actionpoints — Actionable items from the video\n"
        "  /reset — Clear current session\n"
        "  /help — Show this message",
        parse_mode=ParseMode.MARKDOWN,
    )


# ── /help ─────────────────────────────────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


# ── /summary ──────────────────────────────────────────────────────────────

async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    session = sess.get_session(chat_id)

    if not sess.has_video(chat_id) or not session.summary:
        await update.message.reply_text(
            "📹 No video loaded yet. Send me a YouTube link first!"
        )
        return

    await update.message.reply_text(session.summary, parse_mode=ParseMode.MARKDOWN)


# ── /deepdive ─────────────────────────────────────────────────────────────

async def cmd_deepdive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    session = sess.get_session(chat_id)

    if not sess.has_video(chat_id):
        await update.message.reply_text("📹 Please send a YouTube link first!")
        return

    loading = await update.message.reply_text("🔍 Running deep analysis…")
    try:
        result = deepdive(session.transcript, language=session.language)
        await loading.edit_text(result, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await loading.edit_text(f"❌ Error: {str(e)}")


# ── /actionpoints ─────────────────────────────────────────────────────────

async def cmd_actionpoints(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    session = sess.get_session(chat_id)

    if not sess.has_video(chat_id):
        await update.message.reply_text("📹 Please send a YouTube link first!")
        return

    loading = await update.message.reply_text("✅ Extracting action points…")
    try:
        result = action_points(session.transcript, language=session.language)
        await loading.edit_text(result, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await loading.edit_text(f"❌ Error: {str(e)}")


# ── /reset ────────────────────────────────────────────────────────────────

async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    sess.clear_session(chat_id)
    await update.message.reply_text(
        "🔄 Session cleared! Send a new YouTube link to start fresh."
    )
