#!/usr/bin/env bash
# Genera packages/shared-types/ts/index.d.ts a partir de los schemas Pydantic
# en packages/shared-types/python/wcm_types/.
#
# Requisitos:
#   - python -m venv .venv && source .venv/bin/activate && pip install -e
#     "./packages/shared-types[dev]"
#   - node (cualquier 20+) — pydantic2ts shellea contra json-schema-to-typescript
#
# Uso:
#   bash packages/shared-types/scripts/gen-ts.sh
#
# La salida es estable (orden alfabético). Diff vacío en CI valida que no haya
# drift entre Python y TS.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../../.." && pwd)"

OUT="${ROOT}/packages/shared-types/ts/index.d.ts"
MODULE="wcm_types"

mkdir -p "$(dirname "${OUT}")"

echo "[gen-ts] python module = ${MODULE}"
echo "[gen-ts] output       = ${OUT}"

# pydantic2ts toma un módulo Python y produce un fichero .d.ts único.
# Requiere `json2ts` (json-schema-to-typescript) accesible. Si no lo tienes:
#   pnpm add -g json-schema-to-typescript      # o npx vía --json2ts-cmd
JSON2TS_CMD="${JSON2TS_CMD:-json2ts}"
pydantic2ts --module "${MODULE}" --output "${OUT}" --json2ts-cmd "${JSON2TS_CMD}"

# Inyectar cabecera con timestamp UTC y marca de generación
TMP="$(mktemp)"
{
  echo "// AUTO-GENERATED FILE. DO NOT EDIT MANUALLY."
  echo "// Source: packages/shared-types/python/wcm_types/"
  echo "// Regenerate with: pnpm gen:types  (or bash scripts/gen-ts.sh)"
  echo "// Generated at: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  echo ""
  cat "${OUT}"
} >"${TMP}"
mv "${TMP}" "${OUT}"

echo "[gen-ts] ok"
