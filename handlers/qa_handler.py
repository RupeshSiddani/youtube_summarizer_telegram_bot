"""
handlers/qa_handler.py
Handles all non-URL text messages — Q&A and language switching.
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from services.llm import answer_question, detect_language_request, translate_summary
from services import session as sess
from utils.telegram_helpers import edit_or_send_long


async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    question = update.message.text.strip()
    session = sess.get_session(chat_id)

    # ── Language switch? ──────────────────────────────────────────────────────
    lang_request = detect_language_request(question)
    if lang_request:
        sess.update_language(chat_id, lang_request)

        if not sess.has_video(chat_id) or not session.summary:
            await update.message.reply_text(
                f"✅ Language set to *{lang_request}*. Send a YouTube link to get started!",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        loading = await update.message.reply_text(f"🌐 Translating to {lang_request}…")
        try:
            translated = translate_summary(session.summary, lang_request)
            sess.get_session(chat_id).summary = translated
            await edit_or_send_long(loading, translated)
        except Exception as e:
            await loading.edit_text(f"❌ Translation failed: {str(e)}")
        return

    # ── No video loaded ────────────────────────────────────────────────────────
    if not sess.has_video(chat_id):
        await update.message.reply_text(
            "👋 Send me a YouTube link and I'll summarize it for you!\n"
            "Then you can ask me anything about the video."
        )
        return

    # ── Answer question (chat mode) ────────────────────────────────────────────
    thinking = await update.message.reply_text("🤔 …")

    try:
        answer = answer_question(
            transcript=session.transcript,
            history=session.history,
            question=question,
            language=session.language,
        )
    except Exception as e:
        await thinking.edit_text(f"❌ Error: {str(e)}")
        return

    # Maintain conversation history
    sess.append_history(chat_id, "user", question)
    sess.append_history(chat_id, "assistant", answer)

    await edit_or_send_long(thinking, answer)
