#!/bin/sh
set -e

# Fix persistent volume mount permissions if running as root
if [ "$(id -u)" = "0" ]; then
    mkdir -p /workspace /workspace/.orion_state
    chown -R orion:orion /workspace 2>/dev/null || chmod -R 777 /workspace 2>/dev/null
    if command -v gosu >/dev/null 2>&1; then
        exec gosu orion python -m orion "$@"
    elif command -v su-exec >/dev/null 2>&1; then
        exec su-exec orion python -m orion "$@"
    else
        exec su -s /bin/sh orion -c 'python -m orion "$@"' -- "$@"
    fi
fi

exec python -m orion "$@"
