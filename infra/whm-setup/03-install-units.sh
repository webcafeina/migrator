#!/usr/bin/env bash
# Renderiza las unit files con envsubst y las instala en /etc/systemd/system.
# Idempotente.
set -euo pipefail
cd "$(dirname "$0")"
source ./00-env.sh

[[ $EUID -eq 0 ]] || wcm_die "Ejecutar como root (sudo)."

UNITS=(wcm-api.service wcm-worker.service wcm-beat.service wcm-dashboard.service wcm.target)
SRC="$(cd ../systemd && pwd)"
DEST="/etc/systemd/system"

# envsubst limita las vars a las que pasamos para evitar sustituir cosas
# raras del fichero (ej. `${WCM_APP_DIR}` se reemplaza, `$host` de variables
# de shell no).
VARS='${WCM_APP_DIR} ${WCM_USER} ${WCM_PORT_API} ${WCM_PORT_DASHBOARD} ${WCM_WORKER_CONCURRENCY}'

for unit in "${UNITS[@]}"; do
    wcm_log "Instalando ${unit}..."
    envsubst "$VARS" < "${SRC}/${unit}" > "${DEST}/${unit}"
    chmod 644 "${DEST}/${unit}"
done

# log config se copia tal cual (no tiene variables)
install -m 644 "${SRC}/uvicorn-log.json" "${WCM_APP_DIR}/infra/systemd/uvicorn-log.json"

systemctl daemon-reload
systemctl enable wcm.target

wcm_log "Unit files instaladas. Para arrancar:"
wcm_log "  sudo systemctl start wcm.target"
wcm_log ""
wcm_log "Para ver estado:"
wcm_log "  sudo systemctl status wcm-api wcm-worker wcm-beat wcm-dashboard"
