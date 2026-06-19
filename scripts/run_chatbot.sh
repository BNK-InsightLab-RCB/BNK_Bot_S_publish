#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

APP_PORT="${APP_PORT:-9000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
UI_URL="http://127.0.0.1:${FRONTEND_PORT}"

PYTHON_BIN="${PYTHON:-}"
if [ -z "$PYTHON_BIN" ]; then
  if [ -x ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

if [ ! -f ".env" ]; then
  echo ".env file is missing. Copy .env.example to .env and fill the Azure/Foundry values first." >&2
  exit 1
fi

NODE_BIN_DIR="${NODE_BIN_DIR:-$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin}"
if ! command -v node >/dev/null 2>&1 && [ -x "$NODE_BIN_DIR/node" ]; then
  export PATH="$NODE_BIN_DIR:$PATH"
fi
if ! command -v npm >/dev/null 2>&1 && [ -x "$NODE_BIN_DIR/npm" ]; then
  export PATH="$NODE_BIN_DIR:$PATH"
fi

NODE_BIN="$(command -v node || true)"
NPM_BIN="$(command -v npm || true)"

if [ -z "$NODE_BIN" ]; then
  echo "node is required to run the React UI." >&2
  exit 1
fi

if [ ! -d "frontend/node_modules" ]; then
  if [ -z "$NPM_BIN" ]; then
    echo "frontend/node_modules is missing and npm is not available to install it." >&2
    exit 1
  fi
  echo "Installing frontend dependencies..."
  (cd frontend && npm install)
fi

"$PYTHON_BIN" -m uvicorn backend.app.main:app --host 127.0.0.1 --port "$APP_PORT" &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "Waiting for backend on http://127.0.0.1:${APP_PORT}/api/health ..."
"$PYTHON_BIN" - <<PY
import time
import urllib.request

url = "http://127.0.0.1:${APP_PORT}/api/health"
for _ in range(60):
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            if response.status < 500:
                raise SystemExit(0)
    except Exception:
        time.sleep(0.5)
raise SystemExit("Backend did not become ready: " + url)
PY

if [ -n "$NPM_BIN" ]; then
  (cd frontend && npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort) &
else
  (cd frontend && "$NODE_BIN" node_modules/vite/bin/vite.js --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort) &
fi
FRONTEND_PID=$!

echo
echo "Chatbot UI: ${UI_URL}"
echo "Backend API: http://127.0.0.1:${APP_PORT}"
echo "Press Ctrl+C to stop both servers."

if command -v open >/dev/null 2>&1; then
  sleep 1
  open "$UI_URL" >/dev/null 2>&1 || true
fi

wait
