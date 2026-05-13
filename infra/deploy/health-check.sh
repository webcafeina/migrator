#!/usr/bin/env bash
# Verifica post-deploy: /health, /ready y /health/deep responden 200 y
# todas las deps críticas reportan ok.
set -euo pipefail
cd "$(dirname "$0")"
source ../whm-setup/00-env.sh

API_LOCAL="http://127.0.0.1:${WCM_PORT_API}"
DASH_LOCAL="http://127.0.0.1:${WCM_PORT_DASHBOARD}"

curl_check() {
    local url="$1"
    local expected="${2:-200}"
    local code
    code="$(curl -sS -o /tmp/wcm-health.body -w '%{http_code}' --max-time 10 "$url")"
    if [[ "$code" != "$expected" ]]; then
        wcm_error "FAIL ${url} → ${code} (esperado ${expected})"
        cat /tmp/wcm-health.body
        return 1
    fi
    wcm_log "OK   ${url} → ${code}"
}

curl_check "${API_LOCAL}/health"
curl_check "${API_LOCAL}/ready"
curl_check "${API_LOCAL}/health/deep"

# /health/deep devuelve un JSON con `status`. Si es "fail", lo marcamos.
if command -v jq >/dev/null; then
    overall="$(jq -r '.status' /tmp/wcm-health.body)"
    if [[ "$overall" == "fail" ]]; then
        wcm_error "Health deep status=fail. Detalle:"
        jq '.' /tmp/wcm-health.body
        exit 1
    fi
    wcm_log "Health deep: ${overall}"
fi

curl_check "${DASH_LOCAL}/" 200 || curl_check "${DASH_LOCAL}/login"

wcm_log "Health check completo."
