"""
services/cache.py
Global transcript cache — shared across all users.

Architecture Decision:
- Caching level: video_id (not per-user), so if 10 users send the same YouTube
  link, the transcript is fetched only ONCE from YouTube's API.
- TTL: 24 hours (transcripts don't change; YouTube auto-captions are stable)
- Max size: 200 videos (LRU eviction when full)
- Thread-safe: uses a simple dict (Python's GIL + asyncio single-thread = safe)
- In-memory only: cleared on restart (acceptable — transcripts are cheap to re-fetch)

Benefits:
- Eliminates redundant YouTube API calls for popular videos
- Reduces LLM calls: cached summary served instantly vs. re-generating
- Cost optimization: same transcript is not tokenized multiple times
"""

import time
from dataclasses import dataclass, field
from typing import Optional


# Cache configuration
_TTL_SECONDS = 24 * 60 * 60   # 24 hours
_MAX_ENTRIES = 200              # Max number of cached videos


@dataclass
class CacheEntry:
    transcript: str
    language_code: str
    summary: Optional[str] = None     # Cached English summary (generated on first request)
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > _TTL_SECONDS

    def touch(self):
        self.last_accessed = time.time()
        self.access_count += 1


class TranscriptCache:
    """
    LRU-TTL cache for YouTube transcripts.
    
    Key: video_id (str)
    Value: CacheEntry (transcript + optional cached summary)
    """

    def __init__(self):
        self._store: dict[str, CacheEntry] = {}

    def get(self, video_id: str) -> Optional[CacheEntry]:
        """Return cached entry if it exists and is not expired, else None."""
        entry = self._store.get(video_id)
        if entry is None:
            return None
        if entry.is_expired():
            del self._store[video_id]
            return None
        entry.touch()
        return entry

    def set(self, video_id: str, transcript: str, language_code: str) -> CacheEntry:
        """Cache a transcript. Evicts LRU entries if over capacity."""
        self._evict_if_needed()
        entry = CacheEntry(transcript=transcript, language_code=language_code)
        self._store[video_id] = entry
        return entry

    def set_summary(self, video_id: str, summary: str) -> None:
        """Attach a generated summary to an existing cache entry."""
        entry = self._store.get(video_id)
        if entry:
            entry.summary = summary

    def _evict_if_needed(self) -> None:
        """Remove expired entries, then evict LRU if still over capacity."""
        # First pass: remove expired
        expired = [vid for vid, e in self._store.items() if e.is_expired()]
        for vid in expired:
            del self._store[vid]

        # Second pass: LRU eviction if still over capacity
        if len(self._store) >= _MAX_ENTRIES:
            lru_key = min(self._store, key=lambda k: self._store[k].last_accessed)
            del self._store[lru_key]

    def stats(self) -> dict:
        """Return cache statistics (useful for debugging / README documentation)."""
        valid = [e for e in self._store.values() if not e.is_expired()]
        return {
            "total_entries": len(valid),
            "max_entries": _MAX_ENTRIES,
            "ttl_hours": _TTL_SECONDS // 3600,
            "total_hits": sum(e.access_count for e in valid),
        }


# Singleton — import this everywhere
transcript_cache = TranscriptCache()
