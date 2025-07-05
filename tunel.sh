#!/bin/bash

# Launch the Cloudflare tunnel named Jarvik but first verify that the
# local Flask server is reachable.

FLASK_PORT=${FLASK_PORT:-8010}

check_port() {
  if command -v curl >/dev/null 2>&1; then
    curl -sf "http://localhost:$FLASK_PORT" >/dev/null 2>&1 && return 0
  fi
  if command -v nc >/dev/null 2>&1; then
    nc -z localhost "$FLASK_PORT" >/dev/null 2>&1 && return 0
  fi
  return 1
}

if ! check_port; then
  echo "Jarvik server not running on $FLASK_PORT"
  exit 1
fi

echo "\xF0\x9F\x9A\x80 Spouštím Cloudflare Tunnel Jarvik..."
cloudflared tunnel run Jarvik

