#!/usr/bin/env bash
# Aplica migraciones Alembic. Idempotente.
set -euo pipefail
cd "$(dirname "$0")"
source ../whm-setup/00-env.sh

cd "$WCM_APP_DIR"
wcm_log "Aplicando migraciones..."
venv/bin/alembic -c packages/db-schema/alembic.ini upgrade head
wcm_log "Migraciones al día."
