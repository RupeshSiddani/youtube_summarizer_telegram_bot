"""
services/session.py
In-memory session store — one session per Telegram chat_id.
Supports multiple concurrent users without interference.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UserSession:
    video_id: Optional[str] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None
    language: str = "English"                        # preferred response language
    history: list[dict] = field(default_factory=list) # conversation history


# Global store: { chat_id (int) -> UserSession }
_sessions: dict[int, UserSession] = {}


def get_session(chat_id: int) -> UserSession:
    """Return existing session or create a new one."""
    if chat_id not in _sessions:
        _sessions[chat_id] = UserSession()
    return _sessions[chat_id]


def update_video(chat_id: int, video_id: str, transcript: str, summary: str) -> None:
    """Store a new video context for a chat, resetting Q&A history."""
    session = get_session(chat_id)
    session.video_id = video_id
    session.transcript = transcript
    session.summary = summary
    session.history = []           # fresh history for new video


def update_language(chat_id: int, language: str) -> None:
    """Update the preferred language for a chat session."""
    get_session(chat_id).language = language


def append_history(chat_id: int, role: str, content: str) -> None:
    """Append a message to the Q&A history for a chat."""
    get_session(chat_id).history.append({"role": role, "content": content})


def has_video(chat_id: int) -> bool:
    """Return True if the chat has an active video loaded."""
    session = get_session(chat_id)
    return session.transcript is not None


def clear_session(chat_id: int) -> None:
    """Reset the session for a chat (e.g. /reset command)."""
    _sessions[chat_id] = UserSession()
