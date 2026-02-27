"""
handlers/link_handler.py
Handles YouTube URL messages.

Architecture:
- Checks TranscriptCache before fetching from YouTube (avoids redundant API calls)
- If cached: serves transcript immediately, regenerates summary only if needed
- If not cached: fetches from YouTube, stores in cache for future users
"""

import asyncio
from telegram import Update
from telegram.ext import ContextTypes

from utils.url_parser import extract_video_id
from services.transcript import get_transcript
from services.llm import summarize, detect_language_request
from services.cache import transcript_cache
from services import session as sess
from utils.telegram_helpers import edit_or_send_long


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    message_text = update.message.text.strip()

    requested_lang = detect_language_request(message_text)
    language = requested_lang or sess.get_session(chat_id).language

    video_id = extract_video_id(message_text)
    if not video_id:
        await update.message.reply_text("❌ Couldn't parse that YouTube link. Please try again.")
        return

    # Same video already in THIS user's session? Just remind them
    current = sess.get_session(chat_id)
    if current.video_id == video_id and current.transcript:
        await update.message.reply_text(
            "ℹ️ This video is already loaded. Ask me anything, or /summary to re-read the summary."
        )
        return

    # Show loading indicator
    loading_msg = None
    try:
        loading_msg = await update.message.reply_text("⏳ Processing video…")
    except Exception:
        pass

    # ── Step 1: Check transcript cache (shared across all users) ──────────────
    cached = transcript_cache.get(video_id)

    if cached:
        # Cache HIT — transcript already fetched by a previous user or request
        transcript = cached.transcript
        lang_code = cached.language_code
        if loading_msg:
            try:
                await loading_msg.edit_text(
                    f"⚡ Transcript loaded from cache ({len(transcript.split())} words). Generating summary…"
                )
            except Exception:
                pass
    else:
        # Cache MISS — fetch from YouTube
        try:
            transcript, lang_code = get_transcript(video_id)
        except ValueError as e:
            msg = str(e)
            if loading_msg:
                await loading_msg.edit_text(msg)
            else:
                await update.message.reply_text(msg)
            return

        # Store in global cache for future requests
        transcript_cache.set(video_id, transcript, lang_code)

        if loading_msg:
            try:
                await loading_msg.edit_text(
                    f"✅ Transcript fetched ({len(transcript.split())} words). Generating summary…"
                )
            except Exception:
                pass

    # ── Step 2: Get summary (use cached English summary if available + English requested) ──
    if cached and cached.summary and language == "English":
        # Reuse cached summary — no LLM call needed!
        summary = cached.summary
    else:
        # Generate fresh summary
        try:
            summary = summarize(transcript, language=language)
        except Exception as e:
            err = f"❌ Failed to generate summary: {str(e)}"
            if loading_msg:
                await loading_msg.edit_text(err)
            else:
                await update.message.reply_text(err)
            return

        # Cache English summary for future users of same video
        if language == "English":
            transcript_cache.set_summary(video_id, summary)

    # ── Step 3: Store in user session ─────────────────────────────────────────
    sess.update_video(chat_id, video_id, transcript, summary)
    if requested_lang:
        sess.update_language(chat_id, requested_lang)

    # ── Step 4: Send summary ───────────────────────────────────────────────────
    if loading_msg:
        await edit_or_send_long(loading_msg, summary)
    else:
        await update.message.reply_text(summary)

    try:
        await update.message.reply_text("💬 Ask me anything about this video!")
    except Exception:
        pass
