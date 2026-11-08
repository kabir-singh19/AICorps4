"""Start the local AI and website; all listeners stay on loopback."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
RUNTIME = BACKEND / ".local-ai"


def running_models():
    try:
        with build_opener(ProxyHandler({})).open("http://127.0.0.1:11434/api/tags", timeout=2) as response:
            return {item["name"] for item in json.load(response)["models"]}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--api-only", action="store_true")
    args = parser.parse_args()
    load_dotenv(BACKEND / ".env", override=False)
    if os.environ.get("ATSC_ENV") == "production":
        raise SystemExit("Local AI must run in development mode. Hosted deployments use an authenticated HTTPS provider.")
    if os.environ.get("ATSC_AI_PROVIDER") != "ollama" or os.environ.get("ATSC_LOCAL_AI") != "true":
        raise SystemExit("Configure local Ollama settings in backend/.env first. See docs/local-ai.md.")
    binary = shutil.which("ollama") or str(RUNTIME / "Ollama.app/Contents/Resources/ollama")
    if not Path(binary).is_file():
        raise SystemExit("Install Ollama from https://ollama.com/download first.")
    owned = None
    log = None
    try:
        if running_models() is None:
            RUNTIME.mkdir(exist_ok=True)
            log = (RUNTIME / "server.log").open("a")
            environment = {**os.environ, "OLLAMA_HOST": "127.0.0.1:11434", "OLLAMA_MODELS": str(RUNTIME / "models"), "OLLAMA_NO_CLOUD": "1", "OLLAMA_NUM_PARALLEL": "1", "OLLAMA_CONTEXT_LENGTH": "8192"}
            owned = subprocess.Popen([binary, "serve"], env=environment, stdout=log, stderr=log)
            for _ in range(120):
                if owned.poll() is not None:
                    raise SystemExit("The AI runtime stopped. Check backend/.local-ai/server.log.")
                if running_models() is not None:
                    break
                time.sleep(0.25)
        if os.environ.get("ATSC_AI_MODEL") not in (running_models() or set()):
            raise SystemExit("The configured model is missing. Start Ollama and download qwen2.5:1.5b first.")
        frontend = RUNTIME / "frontend-dist"
        if not args.api_only:
            if not (frontend / "index.html").exists():
                raise SystemExit("Build the frontend into backend/.local-ai/frontend-dist first. See docs/local-ai.md.")
            os.environ["ATSC_FRONTEND_DIST"] = str(frontend)
        os.chdir(BACKEND)
        sys.path.insert(0, str(BACKEND))
        import uvicorn
        print(f"Website and AI: http://127.0.0.1:{args.port}/ — open AI assistant", flush=True)
        uvicorn.run("app.main:app", host="127.0.0.1", port=args.port)
    finally:
        if owned is not None and owned.poll() is None:
            owned.terminate()
            try:
                owned.wait(timeout=10)
            except subprocess.TimeoutExpired:
                owned.kill()
                owned.wait()
        if log:
            log.close()


if __name__ == "__main__":
    main()
