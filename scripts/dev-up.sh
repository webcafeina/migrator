#!/usr/bin/env bash
# Arranca toda la stack local en una sesión tmux con 4 ventanas
# (api, worker, beat, dashboard). Idempotente: si la sesión existe la mata
# y recrea.
#
# Uso:
#   bash scripts/dev-up.sh             # arranca todo (api+worker+beat+dashboard)
#   bash scripts/dev-up.sh --no-beat   # salta beat (más rápido para smoke)
#   bash scripts/dev-up.sh --attach    # arranca y entra a la sesión tmux
#
# Tras arrancar:
#   tmux attach -t wcm-dev      # entrar a ver logs
#   Ctrl+B luego N              # siguiente ventana
#   Ctrl+B luego D              # detach (procesos siguen corriendo)
#   bash scripts/dev-down.sh    # parar todo

set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"
SESSION="wcm-dev"
SKIP_BEAT=false
ATTACH=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-beat) SKIP_BEAT=true ;;
        --attach)  ATTACH=true ;;
        -h|--help)
            grep '^#' "$0" | head -20
            exit 0
            ;;
        *) echo "ERROR: flag desconocido: $1"; exit 1 ;;
    esac
    shift
done

# ---------- Pre-checks ----------
[[ -f .env ]] || { echo "ERROR: $REPO_ROOT/.env no existe. Copia .env.example y rellénalo (ver docs/dev-local.md §3)."; exit 1; }
[[ -x .venv/bin/uvicorn ]] || { echo "ERROR: .venv/bin/uvicorn no existe. Crea el venv (ver docs/dev-local.md §1)."; exit 1; }
[[ -x .venv/bin/celery ]] || { echo "ERROR: .venv/bin/celery no existe."; exit 1; }
command -v tmux >/dev/null || { echo "ERROR: tmux no instalado. Ejecuta: brew install tmux"; exit 1; }
command -v pnpm >/dev/null || { echo "ERROR: pnpm no instalado."; exit 1; }

# ---------- Servicios base (brew) ----------
if ! brew services list 2>/dev/null | grep -qE "^redis\s+started"; then
    echo "[dev-up] Arrancando redis..."
    brew services start redis >/dev/null
    sleep 1
fi
if ! brew services list 2>/dev/null | grep -qE "^postgresql@16\s+started"; then
    echo "[dev-up] Arrancando postgresql@16..."
    brew services start postgresql@16 >/dev/null
    sleep 2
fi

# Verificación rápida
redis-cli ping >/dev/null 2>&1 || { echo "ERROR: redis no responde a ping"; exit 1; }
pg_isready -q || { echo "ERROR: postgres no acepta conexiones"; exit 1; }

# ---------- Recrear sesión tmux ----------
if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "[dev-up] Sesión '$SESSION' existe — matando para recrear..."
    tmux kill-session -t "$SESSION"
fi

# Comando base que se ejecuta en cada ventana antes del proceso real
ENV_PRELUDE='set -a; source .env; set +a'

# Ventana 1 — API
tmux new-session -d -s "$SESSION" -n api -c "$REPO_ROOT"
tmux send-keys -t "$SESSION:api" \
    "$ENV_PRELUDE && .venv/bin/uvicorn wcm_api.main:app --host 127.0.0.1 --port 8000 --reload" C-m

# Ventana 2 — Worker Celery
# pool=threads: evita SIGSEGV de PyTorch + fork() en macOS al cargar el
# modelo de embeddings (sentence-transformers). En Linux/prod se puede
# volver a prefork sin problema. WCM-033.
tmux new-window -t "$SESSION" -n worker -c "$REPO_ROOT"
tmux send-keys -t "$SESSION:worker" \
    "$ENV_PRELUDE && .venv/bin/celery -A wcm_worker.celery_app worker --loglevel=info --pool=threads --concurrency=2" C-m

# Ventana 3 — Beat (opcional)
if ! $SKIP_BEAT; then
    tmux new-window -t "$SESSION" -n beat -c "$REPO_ROOT"
    tmux send-keys -t "$SESSION:beat" \
        "$ENV_PRELUDE && .venv/bin/celery -A wcm_worker.celery_app beat --loglevel=info" C-m
fi

# Ventana 4 — Dashboard Next.js
tmux new-window -t "$SESSION" -n dashboard -c "$REPO_ROOT"
tmux send-keys -t "$SESSION:dashboard" \
    "pnpm --filter @webcafeina/dashboard exec next dev -p 3000" C-m

echo ""
echo "✓ Stack arrancada en sesión tmux '$SESSION'"
echo ""
echo "Comandos útiles:"
echo "  tmux attach -t $SESSION       # ver logs (Ctrl+B N = siguiente ventana, Ctrl+B D = detach)"
echo "  tmux list-windows -t $SESSION"
echo "  bash scripts/dev-down.sh      # parar todo (sin tocar brew services)"
echo "  bash scripts/dev-down.sh --all  # parar todo + brew services"
echo ""
echo "URLs:"
echo "  API:        http://127.0.0.1:8000  (docs: /docs)"
echo "  Dashboard:  http://localhost:3000/login"
echo ""
echo "Espera ~10s y verifica con: .venv/bin/wcm doctor"

if $ATTACH; then
    exec tmux attach -t "$SESSION"
fi
