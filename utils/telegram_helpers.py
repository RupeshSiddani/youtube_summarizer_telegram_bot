# utils/telegram_helpers.py
"""Helper utilities for Telegram messaging."""

from telegram import Message
from telegram.constants import ParseMode

MAX_MSG_LEN = 4000  # Telegram limit is 4096; keep buffer


async def send_long_message(message: Message, text: str) -> None:
    """
    Send a potentially long text, splitting into chunks if needed.
    Uses MarkdownV2-safe plain send for overflow chunks.
    """
    if len(text) <= MAX_MSG_LEN:
        try:
            await message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await message.reply_text(text)  # fallback without markdown
        return

    # Split into chunks at newlines where possible
    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > MAX_MSG_LEN:
            if current:
                chunks.append(current)
            current = line
        else:
            current = current + "\n" + line if current else line
    if current:
        chunks.append(current)

    for chunk in chunks:
        try:
            await message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await message.reply_text(chunk)


async def edit_or_send_long(loading_msg: Message, text: str) -> None:
    """
    Edit the loading message with the first chunk,
    then send additional messages for remaining chunks.
    """
    if len(text) <= MAX_MSG_LEN:
        try:
            await loading_msg.edit_text(text, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await loading_msg.edit_text(text)
        return

    # Split into chunks
    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > MAX_MSG_LEN:
            if current:
                chunks.append(current)
            current = line
        else:
            current = current + "\n" + line if current else line
    if current:
        chunks.append(current)

    # Edit loading message with first chunk, send rest as new messages
    try:
        await loading_msg.edit_text(chunks[0], parse_mode=ParseMode.MARKDOWN)
    except Exception:
        await loading_msg.edit_text(chunks[0])

    for chunk in chunks[1:]:
        try:
            await loading_msg.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await loading_msg.reply_text(chunk)
