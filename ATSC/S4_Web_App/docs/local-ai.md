# Working local language-model assistant

The website can now use **Qwen 2.5 1.5B through Ollama** to generate answers about the selected model run/site. This is a real local language model, separate from the synthetic logistic classifier in Example lab. It requires no paid provider key or university API access. Model details and license: [Ollama model page](https://ollama.com/library/qwen2.5:1.5b). Runtime setup: [official macOS documentation](https://docs.ollama.com/macos).

## Start on this configured Mac

Double-click `Start Local AI.command` in the project folder. Keep its terminal open, visit `http://127.0.0.1:8010/?assistant=1`, and choose a run/site, enter a question, and click **Ask assistant**. Site details also has an **Ask AI about this site** button. The connection indicator checks that Ollama is running and the configured model is installed. The first answer can take longer while the model loads into memory.

The current runtime and approximately 986 MB model are installed under `backend/.local-ai/`. They are ignored by Git and excluded from Docker. The local settings are in ignored `backend/.env`; no cloud provider key is needed. The launcher reuses an existing Ollama service, or starts one when absent. If it starts the runtime, it stops that process when the website closes. Model weights remain on disk. Ollama's own local identity files may also be created under `~/.ollama` by the official runtime.

For development at port 5173, run the Vite server as usual and start the API from `backend/` with:

```bash
.venv/bin/python -m uvicorn app.main:app --reload --env-file .env --host 127.0.0.1 --port 8000
```

Keep Ollama running as well. The frontend continues to proxy `/api` to this backend.

## Configure another local checkout

Install Python requirements, Node dependencies, and Ollama from the official source. Copy `backend/.env.example` to `backend/.env` and set:

```dotenv
ATSC_ENV=development
ATSC_AI_ENABLED=true
ATSC_AI_PROVIDER=ollama
ATSC_LOCAL_AI=true
ATSC_AI_MODEL=qwen2.5:1.5b
ATSC_AI_REQUESTS_PER_HOUR=60
```

Start Ollama and download `qwen2.5:1.5b` using its official CLI. If using the project-contained runtime, set `OLLAMA_MODELS` to the absolute `backend/.local-ai/models` path for both the server and model installation. The desktop Ollama service may instead use its default model directory; the launcher can reuse that running service.

Build the website from `frontend/`:

```bash
npm ci
npm run build -- --outDir ../backend/.local-ai/frontend-dist
```

Then run `backend/.venv/bin/python backend/scripts/start_local_ai.py` from the project root. Rebuild this directory after frontend edits when using the standalone launcher.

## Boundaries and hosting

- Ollama and the website launcher listen on `127.0.0.1` only. The runtime is launched with `OLLAMA_NO_CLOUD=1` and one parallel inference. The configured local model processes the question and selected evidence on this Mac.
- Password-free local access requires explicit local settings, a loopback client IP, a loopback hostname, and a non-production environment. Same-origin checks still apply. Production mode disables this local access path, even if the local flags are accidentally set.
- Local provider requests use a fixed loopback endpoint, bypass proxy environment settings, and cannot be redirected by client-supplied model/URL parameters. One local answer runs at a time; a second receives a retry message. Request length, evidence size, output tokens, timeout, and usage limits remain bounded.
- Answers are AI drafts. The model can make mistakes. Example runs stay visibly synthetic, and answers do not become approved memos or computed traffic-risk predictions. Evidence shown in the UI lists the sources supplied; it is not independent fact verification.
- This runtime belongs to this Mac. The Render Docker image does not include Ollama or its model files. For a public AI assistant, configure the existing authenticated HTTPS provider path on Render with an approved university or other provider. It cannot reach this Mac's loopback service.
- API-backed chat remains stateless: each question gets the selected published evidence, not previous chat messages. No project chat-history database is created.
