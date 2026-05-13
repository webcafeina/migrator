#!/usr/bin/env bash
# fix-venv-hidden-pth.sh
#
# Workaround para un bug environmental en macOS + Python 3.14:
# - El venv vive en `.venv/` (directorio "dot")
# - Cuando setuptools instala paquetes con `pip install -e`, los archivos
#   `__editable__.*.pth` heredan el flag `UF_HIDDEN` del filesystem macOS
# - Python 3.14 introdujo en `site.py` un skip explícito de archivos `.pth`
#   con flag hidden (commit cpython c1a89a6, abril 2026)
# - Resultado: los paquetes editable se "instalan" pero no son importables
#
# Este script quita el flag hidden de cualquier `.pth` dentro del venv.
# Ejecutar tras CUALQUIER `pip install`, `pip install -e`, o reinstalación.
#
# Issue tracking interno: WCM-008.
# Tracking upstream: ver discussion en cpython issue tracker
# (filtrar por "UF_HIDDEN .pth").
#
# Plataformas: macOS only. En Linux/Windows este flag no existe; el script
# es un no-op.

set -euo pipefail

VENV_DIR="${1:-.venv}"

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "[fix-venv] no encuentro ${VENV_DIR}/ — pasa la ruta como argumento si no es la default" >&2
  exit 1
fi

# Solo macOS tiene chflags. En Linux no hace falta.
if [[ "$(uname)" != "Darwin" ]]; then
  echo "[fix-venv] no-op fuera de macOS"
  exit 0
fi

count=0
while IFS= read -r -d '' pth; do
  chflags nohidden "${pth}"
  count=$((count + 1))
done < <(find "${VENV_DIR}" -name "*.pth" -print0)

echo "[fix-venv] ${count} ficheros .pth desocultados en ${VENV_DIR}"
