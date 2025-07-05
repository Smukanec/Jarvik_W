#!/bin/bash

FLASK_PORT=${FLASK_PORT:-8010}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

if command_exists curl; then
  curl -sf "http://localhost:${FLASK_PORT}" >/dev/null || {
    echo "Jarvik server not running on ${FLASK_PORT}"
    exit 1
  }
elif command_exists nc; then
  nc -z localhost "${FLASK_PORT}" >/dev/null 2>&1 || {
    echo "Jarvik server not running on ${FLASK_PORT}"
    exit 1
  }
else
  echo "Neither curl nor nc is available to test connectivity" >&2
  exit 1
fi

# Allow overriding the Flask port
FLASK_PORT=${FLASK_PORT:-8010}

# Check that the Jarvik server is responding on the given port
CHECK_OK=0
if command -v curl >/dev/null 2>&1; then
  if curl -fs "http://localhost:$FLASK_PORT/" >/dev/null 2>&1; then
    CHECK_OK=1
  fi
elif command -v nc >/dev/null 2>&1; then
  if nc -z localhost "$FLASK_PORT" >/dev/null 2>&1; then
    CHECK_OK=1
  fi
fi

if [ "$CHECK_OK" -ne 1 ]; then
  echo "Jarvik server not running on $FLASK_PORT"
  exit 1
fi

echo "\xF0\x9F\x9A\x80 Spouštím Cloudflare Tunnel Jarvik..."
cloudflared tunnel run Jarvik
