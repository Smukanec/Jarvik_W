#!/bin/bash

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit
source venv/bin/activate
echo "✅ Aktivováno virtuální prostředí JARVIK (venv)"
