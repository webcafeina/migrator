#!/usr/bin/env bash
# Genera un .env inicial en ${WCM_APP_DIR} a partir de .env.example, con
# secretos auto-generados (JWT_SECRET, SECRET_KEY). NO sobreescribe si
# ya existe.
set -euo pipefail
cd "$(dirname "$0")"
source ./00-env.sh

ENV_PATH="${WCM_APP_DIR}/.env"
[[ -f "$ENV_PATH" ]] && wcm_die ".env ya existe en ${ENV_PATH}. Borralo manualmente si quieres regenerar."

ENV_EXAMPLE="${WCM_APP_DIR}/.env.example"
[[ -f "$ENV_EXAMPLE" ]] || wcm_die "${ENV_EXAMPLE} no encontrado. Has hecho git pull en ${WCM_APP_DIR}?"

cp "$ENV_EXAMPLE" "$ENV_PATH"

# Secretos
gen() { openssl rand -hex 32; }
sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$(gen)/" "$ENV_PATH"
sed -i "s/^JWT_SECRET=.*/JWT_SECRET=$(gen)/" "$ENV_PATH"

# Entorno
sed -i "s/^ENV=.*/ENV=production/" "$ENV_PATH"
sed -i "s|^API_URL=.*|API_URL=https://${WCM_DOMAIN_API}|" "$ENV_PATH"
sed -i "s|^APP_URL=.*|APP_URL=https://${WCM_DOMAIN_DASHBOARD}|" "$ENV_PATH"

chown "${WCM_USER}:${WCM_USER}" "$ENV_PATH"
chmod 600 "$ENV_PATH"

wcm_log ".env generado en ${ENV_PATH} con modo 600."
wcm_log "PENDIENTE: rellenar a mano los siguientes campos:"
wcm_log "  DATABASE_URL, DATABASE_SYNC_URL  (output de 02-database.sh)"
wcm_log "  GOOGLE_MAPS_API_KEY"
wcm_log "  CLICKUP_API_TOKEN (opcional)"
wcm_log "  RESEND_API_KEY + RESEND_WEBHOOK_SECRET (opcional)"
wcm_log "  R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET (opcional)"
wcm_log "  SENTRY_DSN_API, SENTRY_DSN_WORKER, NEXT_PUBLIC_SENTRY_DSN (opcional)"
wcm_log "  LOGTAIL_SOURCE_TOKEN (opcional)"
wcm_log ""
wcm_log "Edita con: sudo -u ${WCM_USER} \$EDITOR ${ENV_PATH}"
