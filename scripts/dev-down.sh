#!/usr/bin/env bash
# Para la stack local: mata la sesión tmux y cualquier proceso huérfano.
# Por defecto deja Redis y Postgres corriendo (consumen poco). Para
# pararlos también, usar --all.
#
# Uso:
#   bash scripts/dev-down.sh         # mata api/worker/beat/dashboard
#   bash scripts/dev-down.sh --all   # mata todo + brew services

set -euo pipefail

SESSION="wcm-dev"
STOP_SERVICES=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --all) STOP_SERVICES=true ;;
        -h|--help)
            grep '^#' "$0" | head -10
            exit 0
            ;;
        *) echo "ERROR: flag desconocido: $1"; exit 1 ;;
    esac
    shift
done

# ---------- Matar sesión tmux ----------
if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "[dev-down] Matando sesión tmux '$SESSION'..."
    tmux kill-session -t "$SESSION"
fi

# ---------- pkill defensivo (procesos huérfanos fuera de tmux) ----------
killed_any=false
for pattern in "uvicorn wcm_api" "celery -A wcm_worker" "next dev -p 3000"; do
    if pgrep -f "$pattern" >/dev/null 2>&1; then
        pkill -f "$pattern" 2>/dev/null || true
        killed_any=true
    fi
done

if $killed_any; then
    echo "✓ Procesos parados (uvicorn, celery, next dev)"
else
    echo "[dev-down] No había procesos sueltos que matar."
fi

# ---------- Servicios brew (opcional con --all) ----------
if $STOP_SERVICES; then
    echo "[dev-down] Parando brew services..."
    brew services stop redis >/dev/null 2>&1 || true
    brew services stop postgresql@16 >/dev/null 2>&1 || true
    echo "✓ Redis y Postgres parados"
else
    echo ""
    echo "Nota: Redis y Postgres siguen corriendo como brew services."
    echo "Para pararlos también: bash scripts/dev-down.sh --all"
fi
