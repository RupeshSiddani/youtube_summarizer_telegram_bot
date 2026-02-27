"""
utils/url_parser.py
Extract YouTube video ID from various URL formats.
"""

import re

# Matches all common YouTube URL formats
_YT_REGEX = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/|v/)|youtu\.be/)"
    r"([a-zA-Z0-9_-]{11})"
)


def extract_video_id(text: str) -> str | None:
    """
    Return the 11-char video ID from a YouTube URL, or None if not found.

    Supported formats:
      - https://www.youtube.com/watch?v=VIDEO_ID
      - https://youtu.be/VIDEO_ID
      - https://www.youtube.com/shorts/VIDEO_ID
      - https://www.youtube.com/embed/VIDEO_ID
    """
    match = _YT_REGEX.search(text)
    return match.group(1) if match else None


def is_youtube_url(text: str) -> bool:
    """Return True if the text contains a recognisable YouTube URL."""
    return extract_video_id(text) is not None
