# 🎙️ Multi-Agent Interview Panel

AI-powered interview practice with a panel of three specialist agents — HR Interviewer, Technical Lead, and Behavioral Coach. Upload your resume, get probing questions, and receive a detailed scorecard with resume cross-referencing.

## ✨ Features

- **Three AI Interviewers** — HR (culture fit), Technical (depth), Behavioral (communication)
- **Resume-Aware Questioning** — Agents probe your projects, skills, and experience claims
- **Voice I/O** — Speak answers via NVIDIA Whisper STT with Sarvam then ElevenLabs backup, hear agents via NVIDIA TTS with Sarvam then ElevenLabs backup
- **Deterministic Rotation** — Predictable `HR → Technical → Behavioral` flow for lower latency and easier debugging
- **Provider Fallbacks** — NVIDIA NIM primary with Gemini then Groq fallback on rate limits or transient failures
- **Scorecard** — Synthesizer cross-references resume claims against interview performance
- **Configurable** — Set difficulty (easy/medium/hard) and question count (3-15)
- **Premium UI** — Glassmorphism dark theme with real-time streaming

## 🏗️ Architecture

```
┌──────────────────┐    ┌──────────────────┐    ┌─────────────────────────────┐
│   Next.js 16     │───▸│   FastAPI         │───▸│  V1 Turn Pipeline            │
│   (Frontend)     │    │   (API Layer)     │    │  Evaluator -> Supervisor -> │
│   :3000          │    │   :8000           │    │  Interviewer / Synthesizer  │
└──────────────────┘    └──────────────────┘    └─────────────────────────────┘
                              │                              │
                        ┌─────┴─────┐                ┌───────┴─────────────────┐
                        │ Supabase  │                │ NVIDIA NIM -> Gemini -> │
                        │ Postgres  │                │ Groq                    │
                        └───────────┘                └─────────────────────────┘
```

### V1 Performance Notes

- **Single `/turn` endpoint** — The frontend now sends one POST request per turn and receives a live SSE stream back. This removes the old `POST /answer` then `GET /stream` race.
- **Explicit turn pipeline** — Each turn follows `Evaluator -> Supervisor -> Interviewer`. Scoring happens after the candidate answers, not inside question generation.
- **Compact resume context** — Resume data is summarized once at session creation and reused in prompts instead of resending long excerpts every turn.
- **Real provider fallback** — The backend retries once on transient rate-limit or timeout failures, then switches provider and emits a `provider_switch` SSE event.
- **TTS by URL** — Audio is generated after the text stream completes and served from a message-scoped URL instead of being embedded in the SSE payload.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- API Keys: NVIDIA NIM, Google AI (Gemini), Groq, Sarvam AI (voice backup), ElevenLabs (extra TTS backup)

### Backend
```bash
cd backend
cp .env.example .env
# Edit .env with your API keys and Supabase database URL

python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to start interviewing.

### Docker (Production)
```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys

docker compose up --build
```

## 📁 Project Structure

```
├── backend/
│   ├── app/
│   │   ├── config.py          # Centralized configuration (single source of truth)
│   │   ├── main.py            # FastAPI app with CORS, lifespan
│   │   ├── models/            # SQLAlchemy + Pydantic schemas
│   │   ├── routes/            # API endpoints (sessions, interview, transcribe, scorecard)
│   │   ├── services/          # LLM provider, resume parser, STT/TTS
│   │   └── graph/             # LangGraph agents + supervisor
│   ├── tools.yaml             # MCP Toolbox DB tools config
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/               # Next.js pages (setup, interview, scorecard)
│   │   ├── hooks/             # useSSE, useVoiceRecorder, useAudioPlayer
│   │   └── lib/               # Types + API utilities
│   └── next.config.ts
└── docker-compose.yml
```

## ⚙️ Configuration

All settings are centralized in `backend/app/config.py` and loaded from `backend/.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `NIM_API_KEY` | NVIDIA NIM API key | (recommended) |
| `NIM_FAST_MODEL` | Primary fast model | `meta/llama-3.1-8b-instruct` |
| `GOOGLE_API_KEY` | Gemini fallback key | (optional) |
| `GROQ_API_KEY` | Groq fallback key | (optional) |
| `NIM_STT_URL` | NVIDIA Whisper gRPC server URI | `grpc.nvcf.nvidia.com:443` |
| `NIM_STT_MODEL` | NVIDIA STT model | `openai/whisper-large-v3` |
| `NIM_STT_FUNCTION_ID` | NVIDIA hosted STT function id | empty |
| `NIM_TTS_URL` | NVIDIA TTS endpoint or gRPC server URI | empty |
| `NIM_TTS_MODEL` | NVIDIA TTS model | `nvidia/magpie-tts-zeroshot` |
| `NIM_TTS_FUNCTION_ID` | NVIDIA hosted TTS function id | empty |
| `NIM_TTS_PROMPT_FILE` | Reference voice WAV for `magpie-tts-zeroshot` | empty |
| `NIM_TTS_PROMPT_TRANSCRIPT` | Transcript matching the reference voice prompt | empty |
| `SARVAM_API_KEY` | Sarvam STT/TTS backup | (optional) |
| `ELEVENLABS_API_KEY` | ElevenLabs STT/TTS backup after Sarvam | (optional) |
| `SARVAM_STT_MODEL` | Sarvam STT model | `saaras:v3` |
| `SARVAM_STT_MODE` | Sarvam STT mode | `transcribe` |
| `SARVAM_STT_LANGUAGE` | Sarvam STT language code | `unknown` |
| `ELEVENLABS_STT_MODEL` | ElevenLabs STT model | `scribe_v2` |
| `SARVAM_TTS_MODEL` | Sarvam TTS model | `bulbul:v3` |
| `SARVAM_TTS_LANGUAGE` | Sarvam TTS language code | `en-IN` |
| `DEFAULT_MAX_TURNS` | Interview length | `9` |
| `DIFFICULTY` | Panel rigor | `medium` |
| `DATABASE_URL` | Supabase Postgres connection. Use `postgresql+asyncpg://...` or paste Supabase's `postgres://...` URL. | Supabase placeholder |

For local development and tests, use the Supabase connection string from Project Settings -> Database. SQLAlchemy ORM remains the right fit here because the app already models sessions, messages, and scorecards as related Python objects while still allowing raw SQL for analytics tools.

For `magpie-tts-zeroshot`, NVIDIA requires a short reference voice sample plus its transcript. The app passes those through `NIM_TTS_PROMPT_FILE` and `NIM_TTS_PROMPT_TRANSCRIPT` when you set them.

## 🧠 How It Works

1. **Setup** — Upload resume (PDF) + paste job description
2. **Resume Parsing** — PyMuPDF extracts text → fast model structures highlights → backend builds compact resume context
3. **Turn Request** — Frontend POSTs to `/api/sessions/{id}/turn` and receives live SSE events
4. **Evaluation + Routing** — Evaluator scores the latest answer, then the deterministic supervisor picks the next interviewer
5. **Interviewer Streaming** — The chosen interviewer streams the next question in real time, with fallback provider switching if needed
6. **Synthesis** — After N questions, Synthesizer cross-references claims → scorecard
7. **Scorecard** — Per-dimension scores, strengths, improvements, resume accuracy

## 🔭 Future Improvements

- Adaptive routing based on answer quality, if deterministic rotation starts feeling too rigid
- Session-state caching only when transcript growth or concurrency makes it worth the complexity
- Richer provider policy beyond the current `fast` / `strong` split
- Background TTS jobs for longer responses
- Partial transcript summarization for very long interviews
- Analytics around provider fallback rate, latency per turn, and token spend

## 📄 License

MIT
