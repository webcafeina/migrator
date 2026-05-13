#!/usr/bin/env bash
# Variables compartidas por los scripts de provisión y deploy.
# Source-ar (no ejecutar): `source infra/whm-setup/00-env.sh`.
#
# Sobreescribir si tu instalación difiere.

set -u

export WCM_USER="${WCM_USER:-webcafeina}"
export WCM_APP_DIR="${WCM_APP_DIR:-/home/${WCM_USER}/migrator}"
export WCM_PORT_API="${WCM_PORT_API:-8000}"
export WCM_PORT_DASHBOARD="${WCM_PORT_DASHBOARD:-3000}"
export WCM_WORKER_CONCURRENCY="${WCM_WORKER_CONCURRENCY:-2}"
export WCM_DOMAIN_API="${WCM_DOMAIN_API:-api.migrator.webcafeina.com}"
export WCM_DOMAIN_DASHBOARD="${WCM_DOMAIN_DASHBOARD:-migrator.webcafeina.com}"

# Versiones objetivo. Cambiarlas dispara re-instalación al ejecutar 01-system-prereqs.
export WCM_PYTHON_VERSION="${WCM_PYTHON_VERSION:-3.14}"
export WCM_NODE_VERSION="${WCM_NODE_VERSION:-22}"
export WCM_POSTGRES_VERSION="${WCM_POSTGRES_VERSION:-16}"

# Detección de plataforma (RHEL/AlmaLinux/CloudLinux en WHM, Debian en otros)
if [[ -f /etc/redhat-release ]]; then
    export WCM_PKG_MGR="dnf"
elif [[ -f /etc/debian_version ]]; then
    export WCM_PKG_MGR="apt-get"
else
    export WCM_PKG_MGR=""
fi

# Helpers (idempotentes)
wcm_log()   { printf '\033[36m[wcm-setup]\033[0m %s\n' "$*"; }
wcm_warn()  { printf '\033[33m[wcm-setup WARN]\033[0m %s\n' "$*"; }
wcm_error() { printf '\033[31m[wcm-setup ERROR]\033[0m %s\n' "$*" >&2; }
wcm_die()   { wcm_error "$*"; exit 1; }
