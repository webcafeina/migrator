#!/usr/bin/env bash
# Rollback al SHA guardado por el último deploy.sh.
# NO ejecuta migraciones en reverso — si la última migración Alembic es
# incompatible, hay que bajarla a mano con `alembic downgrade -1`.
set -euo pipefail
cd "$(dirname "$0")"
source ../whm-setup/00-env.sh

PREV_SHA_FILE="${WCM_APP_DIR}/.cache/last-deploy-sha"
[[ -f "$PREV_SHA_FILE" ]] || wcm_die "No hay SHA previo en ${PREV_SHA_FILE}"

PREV_SHA="$(cat "$PREV_SHA_FILE")"
wcm_log "Rollback a $PREV_SHA"

bash "${WCM_APP_DIR}/infra/deploy/deploy.sh" "$PREV_SHA"

wcm_warn "Si la migración del deploy fallido modificó el schema, ejecuta a mano:"
wcm_warn "  cd ${WCM_APP_DIR} && venv/bin/alembic -c packages/db-schema/alembic.ini downgrade -1"
