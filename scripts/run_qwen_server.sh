#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

dotenv_value() {
  local key="$1"
  local default="$2"
  local env_value="${!key:-}"
  local file_value=""
  if [ -n "$env_value" ]; then
    printf "%s" "$env_value"
    return
  fi
  if [ -f ".env" ]; then
    file_value="$(awk -v key="$key" '
      index($0, key "=") == 1 {
        sub("^[^=]*=", "")
        print
        exit
      }
    ' .env)"
    file_value="${file_value%\"}"
    file_value="${file_value#\"}"
    file_value="${file_value%\'}"
    file_value="${file_value#\'}"
  fi
  printf "%s" "${file_value:-$default}"
}

MODEL="$(dotenv_value LLM_MODEL "Qwen/Qwen3-14B-MLX-4bit")"
HOST="$(dotenv_value LLM_HOST "127.0.0.1")"
PORT="$(dotenv_value LLM_PORT "8000")"

MLX_SERVER="${MLX_SERVER:-}"
if [ -z "$MLX_SERVER" ]; then
  if [ -x ".venv/bin/mlx_lm.server" ]; then
    MLX_SERVER=".venv/bin/mlx_lm.server"
  else
    MLX_SERVER="$(command -v mlx_lm.server || true)"
  fi
fi

if [ -z "$MLX_SERVER" ]; then
  echo "mlx_lm.server is not installed." >&2
  echo "Install it with: .venv/bin/pip install mlx-lm" >&2
  exit 1
fi

exec "$MLX_SERVER" \
  --model "$MODEL" \
  --host "$HOST" \
  --port "$PORT" \
  --chat-template-args '{"enable_thinking":false}' \
  --decode-concurrency 1 \
  --prompt-concurrency 1
