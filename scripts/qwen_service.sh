#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="${QWEN_SERVICE_LABEL:-com.bnk.opsrag.qwen}"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$PLIST_DIR/${LABEL}.plist"
LOG_DIR="$ROOT_DIR/data/logs"
OUT_LOG="$LOG_DIR/qwen.out.log"
ERR_LOG="$LOG_DIR/qwen.err.log"
ACTION="${1:-status}"
UID_NUM="$(id -u)"
PORT="${LLM_PORT:-8000}"
HEALTH_URL="http://127.0.0.1:${PORT}/v1/models"

xml_escape() {
  printf "%s" "$1" \
    | sed -e "s/&/\\&amp;/g" \
      -e "s/</\\&lt;/g" \
      -e "s/>/\\&gt;/g" \
      -e "s/\"/\\&quot;/g" \
      -e "s/'/\\&apos;/g"
}

ensure_macos() {
  if [ "$(uname -s)" != "Darwin" ]; then
    echo "This service helper uses macOS launchd. Run ./scripts/run_qwen_server.sh directly on other OSes." >&2
    exit 1
  fi
}

write_plist() {
  mkdir -p "$PLIST_DIR" "$LOG_DIR"
  local command="cd \"$ROOT_DIR\" && exec ./scripts/run_qwen_server.sh"
  cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$(xml_escape "$LABEL")</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>$(xml_escape "$command")</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$(xml_escape "$ROOT_DIR")</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$(xml_escape "$OUT_LOG")</string>
  <key>StandardErrorPath</key>
  <string>$(xml_escape "$ERR_LOG")</string>
</dict>
</plist>
PLIST
}

is_loaded() {
  launchctl print "gui/${UID_NUM}/${LABEL}" >/dev/null 2>&1
}

health_check() {
  curl -fsS --max-time 2 "$HEALTH_URL" >/dev/null 2>&1
}

check_mlx_server() {
  if [ -x "$ROOT_DIR/.venv/bin/mlx_lm.server" ] || command -v mlx_lm.server >/dev/null 2>&1; then
    return 0
  fi
  echo "mlx_lm.server is not installed." >&2
  echo "Install it with: .venv/bin/pip install mlx-lm" >&2
  exit 1
}

start_service() {
  ensure_macos
  check_mlx_server
  write_plist
  if ! is_loaded; then
    launchctl bootstrap "gui/${UID_NUM}" "$PLIST_PATH"
  fi
  launchctl kickstart -k "gui/${UID_NUM}/${LABEL}" >/dev/null 2>&1 || true
  echo "Qwen service started: ${LABEL}"
  echo "Health: ${HEALTH_URL}"
  echo "Logs: $OUT_LOG / $ERR_LOG"
}

stop_service() {
  ensure_macos
  if is_loaded; then
    launchctl bootout "gui/${UID_NUM}/${LABEL}"
    echo "Qwen service stopped: ${LABEL}"
  else
    echo "Qwen service is not loaded: ${LABEL}"
  fi
}

status_service() {
  ensure_macos
  if is_loaded; then
    echo "launchd: loaded (${LABEL})"
  else
    echo "launchd: not loaded (${LABEL})"
  fi
  if health_check; then
    echo "qwen: online (${HEALTH_URL})"
  else
    echo "qwen: offline (${HEALTH_URL})"
  fi
}

case "$ACTION" in
  install|start)
    start_service
    ;;
  stop)
    stop_service
    ;;
  restart)
    stop_service || true
    start_service
    ;;
  status)
    status_service
    ;;
  logs)
    mkdir -p "$LOG_DIR"
    touch "$OUT_LOG" "$ERR_LOG"
    tail -n 80 -f "$OUT_LOG" "$ERR_LOG"
    ;;
  uninstall)
    stop_service || true
    rm -f "$PLIST_PATH"
    echo "Qwen service plist removed: $PLIST_PATH"
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs|uninstall}" >&2
    exit 2
    ;;
esac
