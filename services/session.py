"""
services/session.py
Per-user session management with TTL-based expiry and automatic cleanup.

Architecture Decision:
- Scope: one session per Telegram chat_id (supports multiple users simultaneously)
- Storage: in-memory dict (no database — acceptable for this scale)
- TTL: 2 hours of inactivity → session auto-expires (saves memory)
- History limit: last 20 messages (10 exchanges) — keeps token cost bounded
- Transcript storage: session stores video_id reference; full transcript in
  TranscriptCache (shared) to avoid duplicating large strings per session
- Cleanup: passive (on access) + periodic cleanup via cleanup_expired()
"""

import time
from dataclasses import dataclass, field
from typing import Optional

# Session configuration
_SESSION_TTL_SECONDS = 2 * 60 * 60   # 2 hours of inactivity
_MAX_HISTORY_MESSAGES = 20            # ~10 back-and-forth exchanges


@dataclass
class UserSession:
    # Video context
    video_id: Optional[str] = None
    transcript: Optional[str] = None      # Full transcript text
    summary: Optional[str] = None         # Generated/cached summary
    language: str = "English"             # User's preferred response language

    # Conversation history (bounded, for Q&A follow-ups)
    history: list[dict] = field(default_factory=list)

    # Session lifecycle
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    def touch(self) -> None:
        """Update last_active timestamp on any user interaction."""
        self.last_active = time.time()

    def is_expired(self) -> bool:
        """Return True if session has been inactive beyond TTL."""
        return (time.time() - self.last_active) > _SESSION_TTL_SECONDS

    def add_history(self, role: str, content: str) -> None:
        """Append a message to conversation history, enforcing the max limit."""
        self.history.append({"role": role, "content": content})
        # Keep only the most recent messages (trim from the front)
        if len(self.history) > _MAX_HISTORY_MESSAGES:
            self.history = self.history[-_MAX_HISTORY_MESSAGES:]

    def reset(self) -> None:
        """Clear video context and conversation history (used by /reset)."""
        self.video_id = None
        self.transcript = None
        self.summary = None
        self.history = []
        self.touch()


# ── Global session store ──────────────────────────────────────────────────────

_sessions: dict[int, UserSession] = {}


def get_session(chat_id: int) -> UserSession:
    """
    Return the active session for a chat_id.
    Creates a new one if none exists or if the previous one expired.
    """
    session = _sessions.get(chat_id)
    if session is None or session.is_expired():
        # Expired or new user — start fresh
        _sessions[chat_id] = UserSession()
    else:
        _sessions[chat_id].touch()
    return _sessions[chat_id]


def update_video(chat_id: int, video_id: str, transcript: str, summary: str) -> None:
    """
    Store new video context for a session.
    Resets Q&A history since it's a new video.
    """
    session = get_session(chat_id)
    session.video_id = video_id
    session.transcript = transcript
    session.summary = summary
    session.history = []  # Fresh history for new video
    session.touch()


def update_language(chat_id: int, language: str) -> None:
    """Update the user's preferred response language."""
    get_session(chat_id).language = language


def append_history(chat_id: int, role: str, content: str) -> None:
    """Append a conversation message, respecting the max history limit."""
    get_session(chat_id).add_history(role, content)


def has_video(chat_id: int) -> bool:
    """Return True if the session has an active video loaded."""
    session = _sessions.get(chat_id)
    if session is None or session.is_expired():
        return False
    return session.transcript is not None


def clear_session(chat_id: int) -> None:
    """Reset session context (/reset command)."""
    if chat_id in _sessions:
        _sessions[chat_id].reset()
    else:
        _sessions[chat_id] = UserSession()


def cleanup_expired() -> int:
    """
    Remove all expired sessions from memory.
    Intended to be called periodically (e.g., from a scheduled job).
    Returns the number of sessions removed.
    """
    expired_ids = [cid for cid, s in _sessions.items() if s.is_expired()]
    for cid in expired_ids:
        del _sessions[cid]
    return len(expired_ids)


def active_session_count() -> int:
    """Return the number of currently active (non-expired) sessions."""
    return sum(1 for s in _sessions.values() if not s.is_expired())
