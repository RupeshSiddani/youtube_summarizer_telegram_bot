"""
handlers/link_handler.py
Handles YouTube URL messages — fetches transcript and generates summary.
"""

import asyncio
from telegram import Update
from telegram.ext import ContextTypes

from utils.url_parser import extract_video_id
from services.transcript import get_transcript
from services.llm import summarize, detect_language_request
from services import session as sess
from utils.telegram_helpers import edit_or_send_long


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    message_text = update.message.text.strip()

    # Language in same message? e.g. "https://... summarize in Hindi"
    requested_lang = detect_language_request(message_text)
    language = requested_lang or sess.get_session(chat_id).language

    video_id = extract_video_id(message_text)
    if not video_id:
        await update.message.reply_text("❌ Couldn't parse that YouTube link. Please try again.")
        return

    # Same video already loaded? Just remind user
    current = sess.get_session(chat_id)
    if current.video_id == video_id and current.transcript:
        await update.message.reply_text(
            "ℹ️ This video is already loaded. Ask me anything about it, or /summary to see the summary again."
        )
        return

    # Send loading indicator
    loading_msg = None
    try:
        loading_msg = await update.message.reply_text("⏳ Processing video…")
    except Exception:
        pass  # Don't block on this

    # Fetch transcript
    try:
        transcript, lang_code = get_transcript(video_id)
    except ValueError as e:
        msg = str(e)
        if loading_msg:
            await loading_msg.edit_text(msg)
        else:
            await update.message.reply_text(msg)
        return

    # Update loading status
    if loading_msg:
        try:
            await loading_msg.edit_text(f"✅ Transcript fetched ({len(transcript.split())} words). Summarizing…")
        except Exception:
            pass

    # Generate summary
    try:
        summary = summarize(transcript, language=language)
    except Exception as e:
        err = f"❌ Failed to generate summary: {str(e)}"
        if loading_msg:
            await loading_msg.edit_text(err)
        else:
            await update.message.reply_text(err)
        return

    # Store in session (resets Q&A history for new video)
    sess.update_video(chat_id, video_id, transcript, summary)
    if requested_lang:
        sess.update_language(chat_id, requested_lang)

    # Deliver summary (splits if too long for Telegram)
    if loading_msg:
        await edit_or_send_long(loading_msg, summary)
    else:
        await update.message.reply_text(summary)

    try:
        await update.message.reply_text("💬 Ask me anything about this video!")
    except Exception:
        pass
