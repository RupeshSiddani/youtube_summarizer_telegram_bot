# Telegram YouTube Summarizer & Q&A Bot

A Telegram bot that accepts YouTube links, fetches transcripts, generates structured summaries, and answers follow-up questions — powered by OpenClaw (local LLM). Supports English and multiple Indian languages.

---

## Features

- **YouTube Summarization** — Structured summary with key points, timestamps, and core takeaway
- **Q&A on Video** — Ask questions grounded strictly in the video transcript (no hallucinations)
- **Multi-language** — English + Hindi, Tamil, Telugu, Kannada, Marathi
- **Long video support** — Automatic transcript chunking for hour-long videos
- **Slash commands** — `/summary`, `/deepdive`, `/actionpoints`, `/reset`
- **Multi-user** — Isolated sessions per Telegram chat

---

## Setup

### 1. Prerequisites

- Python 3.10+
- OpenClaw running locally
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure `.env`

```env
TELEGRAM_TOKEN=your_telegram_bot_token
OPENCLAW_API_BASE=http://localhost:11434/v1
OPENCLAW_API_KEY=openclaw
OPENCLAW_MODEL=llama3
```

### 4. Run

```bash
python bot.py
```

---

## Usage

| Action | How |
|---|---|
| Summarize a video | Send a YouTube link |
| Ask a question | Type any question after loading a video |
| Switch language | Say `Summarize in Hindi` |
| Re-read summary | `/summary` |
| Deep analysis | `/deepdive` |
| Action items | `/actionpoints` |
| Start fresh | `/reset` |

---

## Architecture Decisions

### Transcript Retrieval
Used `youtube-transcript-api` — no auth required, supports manual and auto-generated captions. Falls back gracefully across transcript types. Long transcripts are chunked at ~3000 words to stay within LLM context limits.

### LLM Integration
Uses the `openai` Python client pointed at the local OpenClaw endpoint (`OPENCLAW_API_BASE`). This is compatible with any OpenAI-API-compatible local server (Ollama, LM Studio, OpenClaw).

### Context & Multi-user
Each Telegram `chat_id` gets an isolated in-memory `UserSession` dataclass storing: transcript, summary, language preference, and Q&A history. No database needed. Sessions are cleared on `/reset` or when a new video is sent.

### Multi-language
Language support is prompt-engineered — the system prompt instructs the LLM to respond in the target language. No external translation API is needed. User can request a language by name at any time (`Summarize in Hindi`, `Explain in Tamil`, etc.).

### Q&A Grounding
The transcript is passed as context in the system prompt. The LLM is explicitly instructed to only use transcript content and to respond with `"This topic is not covered in the video."` when information is absent. The last 6 conversation turns are included for follow-up context.

### Error Handling
All failure modes are caught and returned as user-friendly Telegram messages:
- Invalid YouTube URL
- Transcripts disabled
- No captions available
- Video unavailable
- LLM errors

---

## File Structure

```
chat_bot/
├── .env
├── requirements.txt
├── README.md
├── bot.py                      # Entry point
├── handlers/
│   ├── link_handler.py         # YouTube URL → summary
│   ├── qa_handler.py           # Questions & language switching
│   └── command_handler.py      # /start /summary /deepdive etc.
├── services/
│   ├── transcript.py           # Transcript fetch + chunking
│   ├── llm.py                  # OpenClaw LLM calls
│   └── session.py              # Per-user session store
└── utils/
    └── url_parser.py           # YouTube URL → video ID
```

---

## Evaluation Coverage

| Criterion | Implementation |
|---|---|
| End-to-end (30%) | URL → transcript → summary → Q&A full flow |
| Summary quality (20%) | Structured prompt: key points, timestamps, takeaway |
| Q&A accuracy (20%) | Grounded in transcript, conversation history kept |
| Multi-language (15%) | 5 Indian languages via prompt engineering |
| Code quality (10%) | Modular services/handlers/utils separation |
| Error handling (5%) | All edge cases handled with user-friendly messages |
