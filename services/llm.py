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

# Fallback model if primary exceeds rate limit (100k Tokens Per Day)
_FALLBACK_MODEL = "llama-3.1-8b-instant"

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
    """Call Groq with retry on rate limit and fallback to smaller model if TPD exceeded."""
    models_to_try = [_MODEL, _FALLBACK_MODEL]

    for model in models_to_try:
        for attempt in range(3):
            try:
                response = _client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.3,
                    max_tokens=2048,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                err_str = str(e).lower()
                # If Tokens Per Day (TPD) is exhausted, break to try the next model
                if "tpd" in err_str or "tokens per day" in err_str:
                    print(f"⚠️ Rate limit (TPD) reached for {model}, falling back to next model...")
                    break 
                
                # For per-minute limits (RPM/RPD/TPM), wait and retry
                if "429" in err_str or "rate limit" in err_str:
                    if attempt < 2:
                        time.sleep(15)
                        continue
                
                # If neither, or we exhausted retries without hitting TPD, raise
                if attempt == 2:
                    raise

    raise RuntimeError("All Groq models are rate limited. Please wait a while and try again.")




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
    system = f"""You are an expert video analyst and researcher. 
Produce a highly detailed, comprehensive, and structured summary in {language}.
Output ONLY the summary — no preamble, no explanation.
Extract as much valuable information, nuance, and context from the transcript as possible.

Use this exact format:
🎦 *Video Title & Overview*
[Inferred title — be specific]
[A solid 3-4 sentence paragraph summarizing the entire video's premise, background context, and ultimate goal.]

📌 *Detailed Key Points & Arguments*
[Provide 7 to 10 highly detailed bullet points. Do not just list topics; explain the 'how' and 'why' for each point. Include statistics, examples, or specific anecdotes mentioned in the video.]
• [Detailed Point 1]
• [Detailed Point 2]
• [Detailed Point 3]
...

🚀 *Actionable Insights & Takeaways*
[If applicable, list 3-5 things the viewer can actually learn, do, or apply based on the video.]

⏱ *Chronological Flow*
• ~Beginning — [What was discussed in the first part]
• ~Middle — [The core discussion/climax]
• ~End — [Conclusions and final thoughts]

🧠 *Final Conclusion*
[2-3 sentences wrapping up the most important overarching theme of this video.]"""

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
Do NOT make up information. Be conversational, concise, and FORMAT YOUR ANSWER NEATLY USING BULLET POINTS OR NUMBERED LISTS where appropriate. Respond in {language}."""

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
