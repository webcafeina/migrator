#!/usr/bin/env bash
# Reporta el estado runtime de la stack local (api, worker, beat, dashboard,
# redis, postgres) sin tocar nada. Complementa a `wcm doctor`, que valida
# .env y conectividad TCP/HTTP — este script inspecciona los procesos.
#
# Uso:
#   bash scripts/dev-status.sh           # tabla humana por secciones
#   bash scripts/dev-status.sh --quiet   # silencioso, solo exit code
#   bash scripts/dev-status.sh --json    # JSON para scripting
#
# Exit codes:
#   0 = ningún FAIL (los WARN/SKIP no cuentan)
#   1 = 1 o más FAIL

set -euo pipefail

cd "$(dirname "$0")/.."

SESSION="wcm-dev"
QUIET=false
JSON=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --quiet) QUIET=true ;;
        --json)  JSON=true ;;
        -h|--help)
            grep '^#' "$0" | head -15
            exit 0
            ;;
        *) echo "ERROR: flag desconocido: $1" >&2; exit 2 ;;
    esac
    shift
done

# results: array de "STATUS|SECCION|SERVICIO|DETALLE" (pipe = separador, sin
# pipes en los detalles para mantener parseable).
results=()

add() { results+=("$1|$2|$3|$4"); }

# ---------- Helpers ----------
brew_is_started() {
    # $1 = nombre del servicio brew
    brew services list 2>/dev/null | awk -v n="$1" '$1==n {print $2}' | grep -q '^started$'
}

has_window() {
    # $1 = nombre de ventana
    tmux has-session -t "$SESSION" 2>/dev/null \
        && tmux list-windows -t "$SESSION" -F '#{window_name}' 2>/dev/null | grep -qx "$1"
}

first_pid() {
    # $1 = patrón pgrep -f
    pgrep -f "$1" 2>/dev/null | head -1
}

http_code() {
    # $1 = url. Devuelve siempre 3 dígitos. "000" si curl no pudo conectar.
    local code
    code=$(curl --silent --output /dev/null --max-time 3 --write-out '%{http_code}' "$1" 2>/dev/null) || true
    [[ -n "$code" && "$code" != "000" ]] || code="000"
    printf '%s' "$code"
}

session_exists() {
    tmux has-session -t "$SESSION" 2>/dev/null
}

# ---------- 1) Servicios base ----------
if brew_is_started redis; then
    if redis-cli ping >/dev/null 2>&1; then
        add OK base redis "brew started; ping OK"
    else
        add FAIL base redis "brew started pero redis-cli ping falla"
    fi
else
    add FAIL base redis "brew services dice no started"
fi

if brew_is_started postgresql@16; then
    if pg_isready -q; then
        add OK base postgresql@16 "brew started; pg_isready OK"
    else
        add FAIL base postgresql@16 "brew started pero pg_isready falla"
    fi
else
    add FAIL base postgresql@16 "brew services dice no started"
fi

# ---------- 2) Sesión tmux ----------
if session_exists; then
    win_count=$(tmux list-windows -t "$SESSION" 2>/dev/null | wc -l | tr -d ' ')
    win_names=$(tmux list-windows -t "$SESSION" -F '#{window_name}' 2>/dev/null | paste -sd, -)
    add OK tmux "$SESSION" "$win_count ventana(s): $win_names"
else
    add FAIL tmux "$SESSION" "sesión tmux no existe (arranca con scripts/dev-up.sh)"
fi

# ---------- 3) Procesos del stack ----------
# Patrones consistentes con dev-up.sh y dev-down.sh.
declare -a SERVICES=(
    "api|uvicorn wcm_api|http://127.0.0.1:8000/health"
    "worker|celery -A wcm_worker.celery_app worker|"
    "beat|celery -A wcm_worker.celery_app beat|"
    "dashboard|next dev -p 3000|http://localhost:3000"
)

for spec in "${SERVICES[@]}"; do
    name="${spec%%|*}"
    rest="${spec#*|}"
    pattern="${rest%|*}"
    url="${rest##*|}"

    pid=$(first_pid "$pattern" || true)
    win_alive=false
    has_window "$name" && win_alive=true

    if ! session_exists; then
        # Sin sesión: si el pid existe es huérfano; si no, SKIP.
        if [[ -n "$pid" ]]; then
            add WARN procesos "$name" "pid $pid sin sesión tmux (huérfano)"
        else
            add SKIP procesos "$name" "tmux sin sesión"
        fi
        continue
    fi

    if ! $win_alive; then
        if [[ "$name" == "beat" ]]; then
            add SKIP procesos "$name" "ventana 'beat' no existe (¿arrancado con --no-beat?)"
        else
            add FAIL procesos "$name" "ventana tmux '$name' no existe"
        fi
        continue
    fi

    if [[ -z "$pid" ]]; then
        add FAIL procesos "$name" "ventana tmux viva pero proceso no encontrado (¿murió?)"
        continue
    fi

    # Pid encontrado y en tmux → comprobar HTTP si aplica.
    # Aceptamos 2xx/3xx como OK (el dashboard redirige a /login con 307).
    if [[ -n "$url" ]]; then
        code=$(http_code "$url")
        case "$code" in
            2*|3*) add OK procesos "$name" "pid $pid; HTTP $url -> $code" ;;
            000)   add WARN procesos "$name" "pid $pid pero HTTP $url no responde (¿compilando o crash silencioso?)" ;;
            *)     add WARN procesos "$name" "pid $pid; HTTP $url -> $code" ;;
        esac
    else
        add OK procesos "$name" "pid $pid"
    fi
done

# ---------- 4) Huérfanos (procesos fuera de tmux) ----------
# Solo reportamos si la sesión existe pero hay duplicados sueltos. Si no hay
# sesión, ya se reportó arriba como huérfano por servicio.
# Excluimos `next dev` porque Next.js arranca padre (pnpm wrapper) + hijo
# (next real) y eso da 2 pids esperados, no es duplicado.
if session_exists; then
    declare -a ORPHAN_PATTERNS=("uvicorn wcm_api" "celery -A wcm_worker.celery_app worker" "celery -A wcm_worker.celery_app beat")
    orphan_lines=()
    for pat in "${ORPHAN_PATTERNS[@]}"; do
        # Si hay 2+ pids, los extra son sospechosos.
        pids=($(pgrep -f "$pat" 2>/dev/null || true))
        if (( ${#pids[@]} > 1 )); then
            orphan_lines+=("$pat: pids ${pids[*]}")
        fi
    done
    if (( ${#orphan_lines[@]} == 0 )); then
        add OK huerfanos "duplicados" "ninguno"
    else
        for line in "${orphan_lines[@]}"; do
            add WARN huerfanos "duplicados" "$line"
        done
    fi
fi

# ---------- Render ----------
fails=0
warns=0
oks=0
skips=0
for r in "${results[@]}"; do
    case "${r%%|*}" in
        OK) oks=$((oks+1)) ;;
        FAIL) fails=$((fails+1)) ;;
        WARN) warns=$((warns+1)) ;;
        SKIP) skips=$((skips+1)) ;;
    esac
done
total=${#results[@]}

if $JSON; then
    printf '['
    first=true
    for r in "${results[@]}"; do
        IFS='|' read -r status section service detail <<<"$r"
        $first || printf ','
        first=false
        printf '{"status":"%s","section":"%s","service":"%s","detail":"%s"}' \
            "$status" "$section" "$service" "$detail"
    done
    printf ']\n'
elif ! $QUIET; then
    current_section=""
    for r in "${results[@]}"; do
        IFS='|' read -r status section service detail <<<"$r"
        if [[ "$section" != "$current_section" ]]; then
            case "$section" in
                base)      header="Servicios base" ;;
                tmux)      header="Sesion tmux" ;;
                procesos)  header="Procesos del stack" ;;
                huerfanos) header="Procesos sueltos" ;;
                *)         header="$section" ;;
            esac
            printf '\n== %s ==\n' "$header"
            current_section="$section"
        fi
        printf '[%-4s] %-18s %s\n' "$status" "$service" "$detail"
    done
    printf '\nResumen: %d/%d OK; %d FAIL; %d WARN; %d SKIP\n' \
        "$oks" "$total" "$fails" "$warns" "$skips"
fi

(( fails == 0 )) || exit 1
exit 0
