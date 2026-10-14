#!/bin/sh
# Starts as root only long enough to make /data writable (volumes created
# by older images are root-owned), then drops to the unprivileged
# `duetfolio` user for the actual server process.
set -e
if [ "$(id -u)" = "0" ]; then
    chown -R duetfolio:duetfolio /data 2>/dev/null || true
    exec setpriv --reuid=duetfolio --regid=duetfolio --init-groups "$@"
fi
exec "$@"
