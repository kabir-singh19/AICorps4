# University AI connector

For the working local Qwen/Ollama assistant, see [local-ai.md](local-ai.md). The setup below describes the separate hosted university-provider path. Local AI is disabled in production; the public service continues to require approved provider credentials and project access.

The AI assistant is a separate explanation service for this Texas A&M student capstone. It can discuss the project workflow and the selected published run/site. It does not train or execute the traffic-risk model, compute missing risk values, replace S3's memo pipeline, or represent an official university service.

## Provider setup

[Texas A&M's developer AI guidance](https://www.it.tamu.edu.prod.sites-it.cloud.tamu.edu/ai/tools/developer-ai.html) describes the TAMU Chat API as a resource for learning, experimentation, and prototyping, with individual allowances. Confirm the appropriate university service and permitted use before connecting a public deployment. [TAMUS AI](https://tamus.ai/) links to its authenticated documentation. This project does not guess a TAMU endpoint or model ID.

The adapter currently supports an **OpenAI-compatible, non-streaming chat-completions JSON API**. Obtain the complete HTTPS request URL and exact model identifier from your approved provider's documentation. If the approved service uses a different API shape or institutional authentication, adapt `backend/app/assistant.py` before enabling it. No live TAMU call has been verified without credentials.

Set these only in Render's server environment:

| Setting | Value |
| --- | --- |
| `ATSC_SESSION_SECRET` | Random secret, at least 32 characters; Blueprint generates it |
| `ATSC_ASSISTANT_PASSWORD` | Separate project password, at least 12 characters; never a NetID password |
| `ATSC_AI_CHAT_URL` | Full approved HTTPS chat-completions request URL, without query credentials |
| `ATSC_AI_API_KEY` | Provider's API key |
| `ATSC_AI_MODEL` | Exact provider-supported model ID |
| `ATSC_AI_PROVIDER_LABEL` | Display label, e.g. the verified provider's name |
| `ATSC_AI_ENABLED` | Set `true` only after configuration and use approval |
| `ATSC_AI_REQUESTS_PER_HOUR` | Global per-process ceiling; default 30, maximum 200 |

For local development, copy `backend/.env.example` to `backend/.env`, fill in the settings, then run `uvicorn app.main:app --reload --env-file .env` from `backend/`. The file is ignored by Git and the Docker build. Never use a `VITE_` variable for a secret. Use `ATSC_ENV=development` locally so HTTP development can use the access cookie; Render uses production HTTPS.

## Request flow

1. The browser obtains `/api/v1/assistant/status` and `/api/v1/auth/session`.
2. A project member signs in using `POST /api/v1/auth/login`. The server issues a signed HttpOnly, SameSite cookie that expires after one hour and is Secure in production. This is project access, not university SSO.
3. `POST /api/v1/assistant/chat` accepts only `question`, optional `run_id`, and optional `site_id`. The browser cannot override the provider URL, API key, model, system instructions, or evidence packet.
4. The server resolves the requested run and site against validated published results. With no site chosen, it supplies the run summary, backtest if available, and up to ten highest-ranked sites. With a site chosen, it supplies that site's properties and published memo if present. With no run, it supplies only the project workflow.
5. The server sends the question and this evidence to the configured provider. It limits question length, evidence size, reply length, request frequency, and timeout. Imported text is treated as untrusted content. No tool execution is exposed to the model.
6. The UI displays the answer as an **AI draft** alongside the evidence IDs supplied. Example data remains labeled synthetic. Provided evidence IDs do not prove that the model's claims or citations are correct: a human must check them. Drafts do not become published memos and do not receive `grounding_passed=true`.

The project does not persist chat history or log API keys, questions, or answers. The configured provider receives the submitted question and evidence; its retention policy still applies. The public dashboard should contain only approved public data. Each request is independent; this is not a multi-turn conversation with retained memory.

## Failures and next integration work

An unconfigured provider stays unavailable instead of returning a fabricated answer. Missing run/site evidence fails before a provider request. Quota, timeout, network, and unsupported response errors are shown without exposing credentials. AI usage is globally rate-limited within one server process; limits reset on restart. Authentication alone does not guarantee access to a provider quota.

Remaining university-specific work: verify the approved endpoint and model, complete a real provider smoke test, establish institutional access if required, and agree S3's grounding/publication contract. The shared database and actual traffic-risk inference remain separate integration tasks.
