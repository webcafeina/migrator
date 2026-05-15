#!/usr/bin/env bash
# OBSOLETO desde 2026-05-15 (ADR-035 supersede ADR-016).
#
# El bug de los .pth marcados como UF_HIDDEN no era solo un comportamiento
# de macOS sobre directorios dotted: lo causaba la sincronización iCloud
# Drive del Desktop. iCloud Drive reaplicaba el flag hidden cada pocos
# segundos sobre cualquier fichero dentro de `.venv/`, haciendo este
# workaround inútil (el flag desaparecía y volvía antes de que arrancase
# uvicorn/celery).
#
# Solución actual:
#   1) El venv vive en `venv.nosync/` con un symlink `venv -> venv.nosync`
#      (sufijo .nosync = convención reconocida por iCloud para excluir).
#   2) El nombre sin punto evita la heurística "dot dir = hidden".
#
# Ver: docs/dev-local.md §1 + ADR-035.

cat <<'EOF' >&2
[fix-venv] OBSOLETO. Este script ya no es necesario.

El bug que arreglaba (UF_HIDDEN sobre .pth) era causado por iCloud Drive
sincronizando el Desktop. El venv vive ahora en venv.nosync/ con symlink
'venv', lo que excluye el directorio de iCloud y evita el problema raíz.

Si crees que tienes el bug, comprueba:
  ls -lO venv/lib/python3.14/site-packages/__editable__*.pth | head -1
Debe mostrar '-' en la columna de flags. Si muestra 'hidden', mira:
  - ¿El venv se llama venv (no .venv)? Renómbralo.
  - ¿El symlink venv apunta a venv.nosync? Recreálo:
      rm venv && mv venv venv.nosync && ln -s venv.nosync venv

Para crear un venv nuevo correctamente, sigue docs/dev-local.md §1.
EOF
exit 0
