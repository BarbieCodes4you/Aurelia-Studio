#!/bin/sh
# Nightly backup: consistent SQLite copy plus uploads. Run from cron, e.g.
#   15 2 * * * /opt/aurelia/deploy/backup.sh /opt/aurelia/data /var/backups/aurelia
set -e
DATA="${1:-/opt/aurelia/data}"
DEST="${2:-/var/backups/aurelia}"
STAMP=$(date +%Y%m%d-%H%M)
mkdir -p "$DEST"
python3 - "$DATA/aurelia.sqlite3" "$DEST/aurelia-$STAMP.sqlite3" <<'PY'
import sqlite3, sys
src = sqlite3.connect(sys.argv[1]); dst = sqlite3.connect(sys.argv[2])
src.backup(dst); dst.close(); src.close()
PY
tar -czf "$DEST/uploads-$STAMP.tgz" -C "$DATA" uploads
find "$DEST" -type f -mtime +30 -delete
echo "Backed up to $DEST ($STAMP)"
