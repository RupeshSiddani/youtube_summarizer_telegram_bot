"""
services/transcript.py
Fetch YouTube video transcripts using youtube-transcript-api v1.x

Design:
- Returns full transcript as plain text — no chunking
- Gemini 2.0 Flash handles up to 1M tokens; even a 3-hour video fits easily
- Graceful error handling with user-friendly messages
"""

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)

_api = YouTubeTranscriptApi()


def get_transcript(video_id: str) -> tuple[str, str]:
    """
    Fetch the full transcript for a YouTube video.

    Returns:
        (full_text, language_code)

    Raises:
        ValueError with a user-friendly message on failure.
    """
    try:
        transcript_list = _api.list(video_id)

        # Priority: English → any manual → any auto-generated
        try:
            transcript = transcript_list.find_transcript(["en"])
        except NoTranscriptFound:
            try:
                transcript = transcript_list.find_manually_created_transcript(
                    [t.language_code for t in transcript_list]
                )
            except NoTranscriptFound:
                transcript = transcript_list.find_generated_transcript(
                    [t.language_code for t in transcript_list]
                )

        fetched = transcript.fetch()
        language_code = transcript.language_code
        full_text = " ".join(entry.text for entry in fetched)
        return full_text.strip(), language_code

    except TranscriptsDisabled:
        raise ValueError("❌ Transcripts are disabled for this video.")
    except NoTranscriptFound:
        raise ValueError("❌ No transcript found. This video may not have captions.")
    except VideoUnavailable:
        raise ValueError("❌ Video unavailable or invalid URL.")
    except Exception as e:
        raise ValueError(f"❌ Could not fetch transcript: {str(e)}")
