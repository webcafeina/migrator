#!/usr/bin/env bash
# Despliegue idempotente del Webcafeína Migrator en el servidor.
#
# Pasos:
# 1. Pull del repo a ${WCM_APP_DIR}
# 2. Instalar deps Python (.venv) + nodes (pnpm)
# 3. Aplicar migraciones Alembic
# 4. Build del dashboard standalone
# 5. Restart de las units (systemctl restart wcm.target o por servicio)
# 6. health-check.sh
#
# Si falla algún paso, sale con código != 0. El operador puede ejecutar
# rollback.sh para volver al commit anterior.
set -euo pipefail
cd "$(dirname "$0")"
source ../whm-setup/00-env.sh

DEPLOY_REF="${1:-main}"
wcm_log "Despliegue → ref=${DEPLOY_REF} en ${WCM_APP_DIR}"

# Sanity: este script lo lanza el usuario WCM_USER (no root)
if [[ "$(id -un)" != "$WCM_USER" ]]; then
    wcm_die "Ejecuta como usuario ${WCM_USER}: sudo -u ${WCM_USER} bash $0 [ref]"
fi

cd "$WCM_APP_DIR"

# Guardar SHA actual antes de tocar nada (para rollback)
if git rev-parse --git-dir >/dev/null 2>&1; then
    PREV_SHA="$(git rev-parse HEAD)"
    echo "$PREV_SHA" > "${WCM_APP_DIR}/.cache/last-deploy-sha"
    wcm_log "Commit previo: $PREV_SHA"
fi

# ---- 1) Pull ----
wcm_log "git fetch && checkout ${DEPLOY_REF}..."
git fetch --quiet origin
git checkout --quiet "$DEPLOY_REF"
git pull --quiet --ff-only origin "$DEPLOY_REF"
NEW_SHA="$(git rev-parse HEAD)"
wcm_log "Nuevo commit: $NEW_SHA"

# ---- 2) Python deps ----
PY_BIN="${WCM_APP_DIR}/.venv/bin/python"
if [[ ! -x "$PY_BIN" ]]; then
    wcm_log "Creando venv..."
    /opt/python-${WCM_PYTHON_VERSION}/bin/python3 -m venv .venv
fi
wcm_log "Instalando deps Python..."
.venv/bin/pip install --upgrade --quiet pip wheel
.venv/bin/pip install --quiet \
    -e ./packages/shared-types \
    -e ./packages/db-schema \
    -e ./packages/scraper-core \
    -e ./packages/bricks-transpiler \
    -e ./packages/wp-client \
    -e ./packages/ui 2>/dev/null || true
.venv/bin/pip install --quiet \
    -e ./apps/api \
    -e ./apps/worker \
    -e ./cli

# ---- 3) Migrations ----
bash "${WCM_APP_DIR}/infra/deploy/migrate.sh"

# ---- 4) Node deps + build dashboard ----
wcm_log "Instalando deps Node con pnpm..."
pnpm install --frozen-lockfile

wcm_log "Build dashboard (next build standalone)..."
pnpm --filter @webcafeina/dashboard build

# ---- 5) Restart units ----
wcm_log "Reiniciando servicios..."
# El operador debe haber configurado sudoers para que ${WCM_USER} pueda
# reiniciar las units WCM sin password. Si no, este paso falla y hay
# que reiniciar a mano.
sudo systemctl restart wcm-api.service
sudo systemctl restart wcm-worker.service
sudo systemctl restart wcm-beat.service
sudo systemctl restart wcm-dashboard.service

# ---- 6) Health check ----
sleep 3
bash "${WCM_APP_DIR}/infra/deploy/health-check.sh" || {
    wcm_error "Health check FALLÓ. Considera bash infra/deploy/rollback.sh"
    exit 1
}

wcm_log "Despliegue OK: ${PREV_SHA:-N/A} → ${NEW_SHA}"
