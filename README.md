# YouTube Summarizer Telegram Bot

A smart AI research assistant for YouTube, built as a Telegram bot. Summarizes long videos, answers contextual questions, and supports multiple Indian languages.

## Features

- **Video Summarization** — Structured summary with key points, timestamps, and core insight
- **Q&A Chat** — Ask unlimited follow-up questions grounded strictly in the transcript
- **Multi-language** — English, Hindi, Telugu, Tamil, Kannada, Marathi
- **Commands** — `/summary`, `/deepdive`, `/actionpoints`, `/reset`

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your Telegram token and Groq API key

# 3. Run the bot
python bot.py
```

### Required API Keys
| Key | Where to get |
|---|---|
| `TELEGRAM_TOKEN` | [@BotFather](https://t.me/botfather) on Telegram |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) (free) |

## Architecture

### Tech Stack
- **Python 3.13** + `python-telegram-bot 22.6`
- **LLM**: Groq API (`llama-3.3-70b-versatile`) — 14,400 free requests/day
- **Transcript**: `youtube-transcript-api 1.2.4`

### Architectural Decisions

#### 1. Transcript Storage — In-Memory with Global Cache
Transcripts are stored in a global `TranscriptCache` (not per-user) so if multiple users request the same video, it is fetched only once.

- **TTL**: 24 hours (transcripts are stable; YouTube auto-captions don't change frequently)
- **Capacity**: Up to 200 videos with LRU eviction
- **Benefit**: Eliminates redundant YouTube API calls; second user gets instant response

#### 2. Session Management — Per-User with TTL
Each user (Telegram `chat_id`) has an isolated session stored in memory.

- **TTL**: 2 hours of inactivity → session auto-expires and is garbage-collected
- **History limit**: 20 messages (10 exchanges) — keeps token cost bounded
- **Cleanup**: Periodic job runs every 30 minutes to evict expired sessions
- **Isolation**: Users never share session state — suitable for simultaneous multi-user usage

#### 3. Context Handling — Full Transcript to LLM
Instead of chunking the transcript (which loses context), we send the full text to the LLM in a single call.

- **Why**: `llama-3.3-70b-versatile` supports large context windows; transcript of even a 2-hour video fits comfortably
- **For Q&A**: First 4,000 words of transcript + last 8 conversation messages are included
- **No hallucinations**: System prompt explicitly instructs the model to refuse questions not in the transcript

#### 4. Translation — Reuse Cached Summary
When user requests a language change, the existing English summary is translated (not re-generated from transcript).

- **Benefit**: Translation is a single LLM call (~1-2s) vs. full summarization from transcript

#### 5. Cost Optimization (Token Efficiency)
- Q&A uses only the first ~4,000 words of transcript (not full) — sufficient for question answering
- Conversation history capped at 20 messages to prevent unbounded token growth
- Cached summaries avoid redundant LLM calls for same video

## Project Structure

```
chat_bot/
├── bot.py                    # Entry point, handler registration, cleanup job
├── handlers/
│   ├── command_handler.py    # /start /help /summary /deepdive /actionpoints /reset
│   ├── link_handler.py       # YouTube URL processing with cache check
│   └── qa_handler.py         # Q&A and language switching
├── services/
│   ├── cache.py              # Global transcript cache (LRU + TTL)
│   ├── session.py            # Per-user session management (TTL + history limit)
│   ├── llm.py                # Groq LLM integration
│   └── transcript.py         # YouTube transcript fetching
└── utils/
    ├── url_parser.py         # YouTube URL/ID extraction
    └── telegram_helpers.py   # Long message splitting (4096 char Telegram limit)
```
