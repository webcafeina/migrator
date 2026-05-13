#!/usr/bin/env bash
# Instala prerrequisitos del sistema: Python 3.14, Node 22, Redis,
# PostgreSQL 16, pgvector, herramientas de build.
#
# Idempotente: si una pieza ya está instalada en la versión correcta,
# salta sin tocar nada. Ejecutar como root.
#
# Compatible con AlmaLinux 8/9 (base de WHM/cPanel). Para Debian/Ubuntu
# las rutas y nombres de paquete difieren — adaptar antes de usar.
set -euo pipefail
cd "$(dirname "$0")"
source ./00-env.sh

[[ $EUID -eq 0 ]] || wcm_die "Ejecutar como root (sudo)."

if [[ "$WCM_PKG_MGR" != "dnf" ]]; then
    wcm_warn "Plataforma no AlmaLinux/RHEL — revisa este script antes de seguir."
fi

# ---- 1) Repos y herramientas base ----
wcm_log "Instalando herramientas base..."
dnf install -y \
    epel-release \
    git curl wget jq \
    gcc gcc-c++ make \
    openssl openssl-devel \
    bzip2 bzip2-devel xz-devel zlib-devel \
    libffi-devel sqlite-devel readline-devel \
    cmake patch

# ---- 2) Python 3.14 ----
# AlmaLinux 9 no trae 3.14 en repos oficiales. Usamos pyenv-style desde
# fuente. Si ya está en /opt/python-$WCM_PYTHON_VERSION/bin/python3, skip.
PYTHON_PREFIX="/opt/python-${WCM_PYTHON_VERSION}"
if [[ ! -x "${PYTHON_PREFIX}/bin/python3" ]]; then
    wcm_log "Compilando Python ${WCM_PYTHON_VERSION} en ${PYTHON_PREFIX}..."
    PY_FULL="$(curl -s 'https://www.python.org/ftp/python/' | grep -Eo "${WCM_PYTHON_VERSION}\.[0-9]+/" | sort -V | tail -1 | tr -d '/')"
    [[ -n "$PY_FULL" ]] || wcm_die "No se pudo determinar última 3.14.x"
    wcm_log "Versión detectada: $PY_FULL"
    cd /tmp
    wget -q "https://www.python.org/ftp/python/${PY_FULL}/Python-${PY_FULL}.tgz"
    tar xf "Python-${PY_FULL}.tgz"
    cd "Python-${PY_FULL}"
    ./configure --prefix="$PYTHON_PREFIX" --enable-optimizations --enable-shared \
        LDFLAGS="-Wl,-rpath=${PYTHON_PREFIX}/lib"
    make -j"$(nproc)"
    make altinstall
    ln -sf "${PYTHON_PREFIX}/bin/python${WCM_PYTHON_VERSION}" "${PYTHON_PREFIX}/bin/python3"
    ln -sf "${PYTHON_PREFIX}/bin/pip${WCM_PYTHON_VERSION}"    "${PYTHON_PREFIX}/bin/pip3"
    cd /tmp && rm -rf "Python-${PY_FULL}" "Python-${PY_FULL}.tgz"
else
    wcm_log "Python ${WCM_PYTHON_VERSION} ya instalado: $("${PYTHON_PREFIX}/bin/python3" --version)"
fi

# ---- 3) Node.js 22 ----
if ! command -v node >/dev/null || [[ "$(node -v 2>/dev/null | cut -c2-3)" != "$WCM_NODE_VERSION" ]]; then
    wcm_log "Instalando Node.js ${WCM_NODE_VERSION}..."
    curl -fsSL "https://rpm.nodesource.com/setup_${WCM_NODE_VERSION}.x" | bash -
    dnf install -y nodejs
    corepack enable
else
    wcm_log "Node.js ya en versión correcta: $(node -v)"
fi

# pnpm via corepack (más fiable que npm i -g)
if ! command -v pnpm >/dev/null; then
    corepack prepare pnpm@latest --activate
fi

# ---- 4) Redis ----
if ! systemctl is-enabled redis &>/dev/null; then
    wcm_log "Instalando Redis..."
    dnf install -y redis
    systemctl enable --now redis
    # Bind a localhost only (no exponerlo)
    sed -i 's/^bind .*/bind 127.0.0.1 ::1/' /etc/redis/redis.conf || true
    systemctl restart redis
fi
wcm_log "Redis status: $(systemctl is-active redis)"

# ---- 5) PostgreSQL 16 + pgvector ----
if ! command -v psql &>/dev/null; then
    wcm_log "Instalando PostgreSQL ${WCM_POSTGRES_VERSION}..."
    dnf install -y "https://download.postgresql.org/pub/repos/yum/reporpms/EL-$(rpm -E %rhel)-x86_64/pgdg-redhat-repo-latest.noarch.rpm"
    dnf -qy module disable postgresql || true
    dnf install -y "postgresql${WCM_POSTGRES_VERSION}-server" "postgresql${WCM_POSTGRES_VERSION}-contrib" "postgresql${WCM_POSTGRES_VERSION}-devel"

    PG_BIN="/usr/pgsql-${WCM_POSTGRES_VERSION}/bin"
    "$PG_BIN/postgresql-${WCM_POSTGRES_VERSION}-setup" initdb
    systemctl enable --now "postgresql-${WCM_POSTGRES_VERSION}"
fi

# pgvector — compilar desde fuente si no está disponible como rpm
PGVECTOR_INSTALLED=$(sudo -u postgres psql -tAc \
    "SELECT 1 FROM pg_available_extensions WHERE name='vector'" 2>/dev/null || true)
if [[ "$PGVECTOR_INSTALLED" != "1" ]]; then
    wcm_log "Compilando pgvector..."
    dnf install -y git
    cd /tmp
    [[ -d pgvector ]] && rm -rf pgvector
    git clone --depth=1 --branch v0.7.0 https://github.com/pgvector/pgvector.git
    cd pgvector
    PATH="/usr/pgsql-${WCM_POSTGRES_VERSION}/bin:$PATH" make
    PATH="/usr/pgsql-${WCM_POSTGRES_VERSION}/bin:$PATH" make install
    cd /tmp && rm -rf pgvector
fi
wcm_log "PostgreSQL status: $(systemctl is-active "postgresql-${WCM_POSTGRES_VERSION}")"

# ---- 6) Usuario sistema y directorios ----
if ! id -u "$WCM_USER" &>/dev/null; then
    wcm_log "Creando usuario ${WCM_USER}..."
    useradd -m -s /bin/bash "$WCM_USER"
fi
install -d -o "$WCM_USER" -g "$WCM_USER" -m 750 \
    "$WCM_APP_DIR" \
    "$WCM_APP_DIR/.cache" \
    "$WCM_APP_DIR/logs" \
    "$WCM_APP_DIR/work"

# ---- 7) Swap (recomendado para builds Next.js si RAM <2GB) ----
TOTAL_MB=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
if (( TOTAL_MB < 2048 )) && [[ ! -f /swapfile ]]; then
    wcm_log "RAM<2GB. Creando swap de 2GB..."
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi

# ---- 8) fail2ban (opcional pero recomendado) ----
if ! command -v fail2ban-client &>/dev/null; then
    wcm_log "Instalando fail2ban..."
    dnf install -y fail2ban
    systemctl enable --now fail2ban
fi

wcm_log "Provisión base completada."
wcm_log "Siguiente paso: bash infra/whm-setup/02-database.sh"
