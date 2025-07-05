#!/bin/bash

# Launch the Cloudflare tunnel named Jarvik

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

