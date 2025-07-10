#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit

# Update submodules if possible
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git submodule update --init --recursive
fi

bash "$DIR/start_jarvik.sh" "$@"
STATUS=$?
if [ "$STATUS" -ne 0 ]; then
  exit "$STATUS"
fi

# Probe the Flask port until it responds
FLASK_PORT=${FLASK_PORT:-8000}
TIMEOUT=30
PORT_READY=0
echo "⌛ Waiting for Flask on port $FLASK_PORT..."
for ((i=0;i<TIMEOUT;i++)); do
  if command -v curl >/dev/null 2>&1 && curl -sf "http://localhost:$FLASK_PORT/" >/dev/null 2>&1; then
    PORT_READY=1
  elif command -v nc >/dev/null 2>&1; then
    echo -e "GET / HTTP/1.0\r\n" | nc -w 1 localhost "$FLASK_PORT" >/dev/null 2>&1 && PORT_READY=1
  fi
  [ "$PORT_READY" -eq 1 ] && break
  sleep 1
done

if [ "$PORT_READY" -ne 1 ]; then
  echo "❌ Flask port $FLASK_PORT did not respond"
  exit 1
fi
echo "✅ Flask responded"

