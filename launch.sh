#!/usr/bin/env bash
# Start LinkScribe (if not already running) and open it in a browser.
set -u
cd "$(dirname "$(readlink -f "$0")")"
URL="http://127.0.0.1:8765"
if ! curl -sf "$URL/health" >/dev/null 2>&1; then
  nohup .venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8765 >>server.log 2>&1 &
  for _ in $(seq 1 60); do
    curl -sf "$URL/health" >/dev/null 2>&1 && break
    sleep 0.5
  done
fi
if ! curl -sf "$URL/health" >/dev/null 2>&1; then
  echo "LinkScribe failed to become healthy; see server.log" >&2
  exit 1
fi
if command -v google-chrome >/dev/null 2>&1; then
  nohup google-chrome "$URL" >/dev/null 2>&1 &
else
  nohup xdg-open "$URL" >/dev/null 2>&1 &
fi
