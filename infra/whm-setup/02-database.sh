#!/usr/bin/env bash
# Crea la base de datos PostgreSQL, el rol del worker, y habilita pgvector.
# Idempotente: si la DB/rol ya existen, no las recrea.
set -euo pipefail
cd "$(dirname "$0")"
source ./00-env.sh

[[ $EUID -eq 0 ]] || wcm_die "Ejecutar como root (sudo)."

DB_NAME="${WCM_DB_NAME:-webcafeina_migrator}"
DB_USER="${WCM_DB_USER:-webcafeina}"
DB_PASS="${WCM_DB_PASS:-}"

if [[ -z "$DB_PASS" ]]; then
    DB_PASS="$(openssl rand -base64 24 | tr -d /=+ | cut -c1-24)"
    wcm_warn "WCM_DB_PASS no estaba definida. Generada: ${DB_PASS}"
    wcm_warn "GUÁRDALA: actualiza DATABASE_URL en .env del servidor."
fi

PSQL="sudo -u postgres psql -v ON_ERROR_STOP=1"

# Crear rol si no existe
$PSQL -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1 || {
    wcm_log "Creando rol $DB_USER..."
    $PSQL -c "CREATE ROLE \"$DB_USER\" WITH LOGIN PASSWORD '$DB_PASS';"
}

# Crear DB si no existe
$PSQL -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || {
    wcm_log "Creando DB $DB_NAME..."
    $PSQL -c "CREATE DATABASE \"$DB_NAME\" OWNER \"$DB_USER\";"
}

# pgvector dentro de la DB
$PSQL -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;"

wcm_log "DB ${DB_NAME} lista. Rol: ${DB_USER}."
wcm_log ""
wcm_log "Añade a .env (server):"
wcm_log "DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}"
wcm_log "DATABASE_SYNC_URL=postgresql://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}"
