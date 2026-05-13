#!/usr/bin/env bash
# Renderiza e instala los vhosts Nginx. Asume Nginx ya instalado por
# cPanel/WHM. Hace `nginx -t` antes de recargar.
set -euo pipefail
cd "$(dirname "$0")"
source ./00-env.sh

[[ $EUID -eq 0 ]] || wcm_die "Ejecutar como root (sudo)."
command -v nginx >/dev/null || wcm_die "Nginx no encontrado. Instala con WHM > Service Manager."

SRC="$(cd ../nginx && pwd)"
SNIPPETS_DIR="/etc/nginx/snippets"
CONF_DIR="/etc/nginx/conf.d"

mkdir -p "$SNIPPETS_DIR"

VARS='${WCM_APP_DIR} ${WCM_PORT_API} ${WCM_PORT_DASHBOARD} ${WCM_DOMAIN_API} ${WCM_DOMAIN_DASHBOARD}'

# Snippet común (sin variables propias salvo el _SSL session cache)
install -m 644 "${SRC}/wcm-common.conf" "${SNIPPETS_DIR}/wcm-common.conf"

for host in api.migrator.webcafeina.com migrator.webcafeina.com; do
    wcm_log "Renderizando vhost ${host}..."
    envsubst "$VARS" < "${SRC}/${host}.conf" > "${CONF_DIR}/${host}.conf"
done

wcm_log "nginx -t ..."
nginx -t

wcm_log "Recargando Nginx..."
systemctl reload nginx
wcm_log "Vhosts instalados. Verifica certificados SSL en cPanel AutoSSL."
