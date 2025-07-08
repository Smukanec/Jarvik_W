#!/bin/bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
mkdir -p backups
BACKUP_FILE="backups/backup_${TIMESTAMP}.tar.gz"
tar --ignore-failed-read -czf "$BACKUP_FILE" knowledge memory
echo "Backup saved to $BACKUP_FILE"

