#!/bin/bash

# Launch the Cloudflare tunnel named Jarvik only if the local server is running

FLASK_PORT="${FLASK_PORT:-8010}"

if ! curl -fs "http://localhost:${FLASK_PORT}" >/dev/null 2>&1; then
    echo "Jarvik server not running on ${FLASK_PORT}"
    exit 1
fi

echo "\xF0\x9F\x9A\x80 Spouštím Cloudflare Tunnel Jarvik..."
cloudflared tunnel run Jarvik

