"""
services/llm.py
Core LLM service using Groq API (llama3-70b-8192).

Why Groq:
- Free tier: 14,400 requests/day, 30 req/min — very generous
- OpenAI-compatible API — simple to use
- Fast inference (runs on custom hardware)
- llama3-70b gives excellent quality

Design:
- No chunking: transcript sent in full (Llama 3 supports large context)
- Separate summarize vs translate (translation reuses cached summary — fast)
- Q&A: grounded strictly in transcript, conversation history maintained
"""

import os
import time
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

SUPPORTED_LANGUAGES = {
    "hindi": "Hindi", "हिंदी": "Hindi",
    "tamil": "Tamil", "தமிழ்": "Tamil",
    "telugu": "Telugu", "తెలుగు": "Telugu",
    "kannada": "Kannada", "ಕನ್ನಡ": "Kannada",
    "marathi": "Marathi", "मराठी": "Marathi",
    "english": "English",
}


# ─── Core LLM call ────────────────────────────────────────────────────────────

def _ask(system: str, user: str) -> str:
    """Call Groq with retry on rate limit."""
    for attempt in range(3):
        try:
            response = _client.chat.completions.create(
                model=_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.3,
                max_tokens=2048,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e).lower():
                if attempt < 2:
                    time.sleep(15)
                    continue
            raise
    raise RuntimeError("Rate limited. Please wait a moment and try again.")


# ─── Language detection ───────────────────────────────────────────────────────

def detect_language_request(message: str) -> str | None:
    """Detect if user is requesting a specific language. Returns language name or None."""
    lower = message.lower()
    for keyword, lang in SUPPORTED_LANGUAGES.items():
        if keyword in lower:
            return lang
    return None


# ─── Summarization ────────────────────────────────────────────────────────────

def summarize(transcript: str, language: str = "English") -> str:
    """Summarize a full video transcript in the given language."""
    system = f"""You are a professional YouTube video analyst. 
Produce a structured summary in {language}.
Output ONLY the summary — no preamble, no explanation.
Fill every section with specific real content from the transcript.

Use this exact format:
🎦 *Video Title*
[Inferred title — be specific]

📌 *Key Points*
1. [Specific point with detail]
2. [Specific point with detail]
3. [Specific point with detail]
4. [Specific point with detail]
5. [Specific point with detail]

⏱ *Important Timestamps*
• ~Start — [What is discussed at beginning]
• ~Middle — [What is discussed in middle]
• ~End — [What is discussed near end]

🧠 *Core Takeaway*
[2-3 sentences with the most important insight from this video]"""

    # Groq's llama3-70b supports up to 8192 tokens — limit transcript to ~6000 tokens (~4500 words)
    transcript_snippet = " ".join(transcript.split()[:4500])
    return _ask(system, f"Transcript:\n{transcript_snippet}")


# ─── Translation ──────────────────────────────────────────────────────────────

def translate_summary(summary: str, target_language: str) -> str:
    """Translate an existing summary — much faster than re-summarizing."""
    return _ask(
        f"You are a translator. Translate this YouTube summary into {target_language}. "
        f"Keep all emojis and structure identical. Output ONLY the translated text.",
        summary
    )


# ─── Q&A ──────────────────────────────────────────────────────────────────────

def answer_question(
    transcript: str,
    history: list[dict],
    question: str,
    language: str = "English",
) -> str:
    """Answer questions strictly grounded in the transcript."""
    history_text = ""
    for msg in history[-8:]:
        role = "User" if msg["role"] == "user" else "Bot"
        history_text += f"{role}: {msg['content']}\n"

    # Limit transcript to fit in context window
    transcript_snippet = " ".join(transcript.split()[:4000])

    system = f"""You are a helpful video assistant. Answer questions based ONLY on the transcript.
If the answer is not in the transcript, say: "❓ This topic is not covered in the video."
Do NOT make up information. Be conversational and concise. Respond in {language}."""

    user_msg = f"""Transcript:
{transcript_snippet}

Conversation so far:
{history_text}
User: {question}"""

    return _ask(system, user_msg)


# ─── Bonus ────────────────────────────────────────────────────────────────────

def deepdive(transcript: str, language: str = "English") -> str:
    snippet = " ".join(transcript.split()[:4000])
    return _ask(
        f"Provide a detailed analytical deep-dive in {language}: main themes, key arguments, evidence, observations.",
        f"Transcript:\n{snippet}"
    )


def action_points(transcript: str, language: str = "English") -> str:
    snippet = " ".join(transcript.split()[:4000])
    return _ask(
        f"Extract every actionable recommendation and next step as a numbered list in {language}.",
        f"Transcript:\n{snippet}"
    )
