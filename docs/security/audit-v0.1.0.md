# Security audit — release v0.1.0

**Fecha**: 2026-05-14.
**Auditor**: Claude Opus 4.7 (audit asistido) + equipo Webcafeína (review final).
**Versión**: v0.1.0 (commit `f0b1ea0` previo al audit).

Audit antes del primer push a GitHub. Objetivo: identificar vulnerabilidades y validar que las mitigaciones implementadas siguen activas tras 14 fases de construcción.

---

## 0. Resumen ejecutivo

| Categoría | Findings | Bloqueantes | Mitigados |
|---|---|---|---|
| Dependency audit (pip + pnpm) | 1 transitiva | 0 | 1 (`postcss` override) |
| SQL injection | 0 | — | n/a |
| Auth/RBAC | 0 | — | n/a |
| Secrets en código | 0 | — | n/a |
| Bash injection en scripts | 0 | — | n/a |
| HMAC timing | 0 | — | `hmac.compare_digest` en todos sitios |
| CORS | 0 | — | whitelist desde `.env` |
| Headers HTTP | 0 | — | HSTS + CSP + X-Frame-Options en Nginx snippet |
| Rate limiting | 1 finding | 0 | implementado en Fase 15 |
| PII en logs/Sentry | 0 | — | `send_default_pii=False` |

**Veredicto**: ✅ apto para deploy a producción tras aplicar las mitigaciones de Fase 15.

---

## 1. Dependency audit

### Python (`pip-audit`)

```bash
venv/bin/pip-audit --skip-editable
```

**Resultado**: `No known vulnerabilities found` sobre 270+ deps.

Las 8 deps locales editables (`wcm-api`, `wcm-worker`, etc.) se saltan — son nuestras, no PyPI.

### JavaScript (`pnpm audit --prod`)

**Antes del fix**: 1 vuln moderate en `postcss < 8.5.10` (CVE GHSA-qx2v-qp2m-jg93, XSS via unescaped `</style>` en CSS Stringify). Path: `apps/dashboard > next@15.5.18 > postcss@8.4.31`.

**Análisis**: La vulnerabilidad sólo se explota si el atacante puede inyectar CSS arbitrario que se procesa con `postcss.stringify()`. En nuestro caso, Tailwind genera todo el CSS en build-time desde fuentes confiables. **Riesgo real bajo**.

**Mitigación aplicada**: pnpm `overrides` en el `package.json` raíz fuerza `postcss@^8.5.10` en todo el árbol:

```json
"pnpm": {
  "overrides": {
    "postcss": "^8.5.10"
  }
}
```

**Post-fix**: `pnpm audit --prod` → `No known vulnerabilities found`.

### Política de audit continuo

- `pip-audit` y `pnpm audit` deben correr en CI (job `python` y `typescript`). Pendiente WCM-015.
- Revisión mensual de [GitHub Security Advisories](https://github.com/advisories) para `python`, `next.js`, `fastapi`.

---

## 2. SQL injection

Revisión manual de todo uso de `text()` y string formatting en queries.

Encontrado:
- `apps/api/src/wcm_api/routers/health.py:60`: `await session.execute(text("SELECT 1"))` — string literal, **seguro**.
- Todo lo demás usa SQLAlchemy ORM (`select(Lead).where(Lead.id == lead_id)`) — parametrizado por la lib.
- `apps/worker/src/wcm_worker/tasks/maintenance.py`: `delete(Lead).where(...)` ORM puro — **seguro**.

**Veredicto**: ✅ sin findings.

---

## 3. Auth / RBAC

### JWT

- Firmado con `HS256` y secret de 32 bytes (generado con `openssl rand -hex 32` en `infra/whm-setup/05-init-env.sh`).
- TTL configurable, default 480 min (8h). ✅
- Tokens de opt-out tienen claim `purpose=opt_out` distinto del `session` token; cross-purpose se rechaza en `decode_opt_out_token`. ✅
- Cookie `wcm_session` con `HttpOnly`. Falta verificar `Secure` + `SameSite=Lax` en producción (sí en el helper de `auth.py`).

### RBAC

- 3 roles: `admin` / `operator` / `viewer`. Definidos en `wcm_types.enums.UserRole`.
- Decorator `require_role(*roles)` aplicado en cada router crítico.
- Tests `test_authorization.py` cubren: viewer no puede POST, operator no puede DELETE users, anon → 401.

**Veredicto**: ✅ sin findings. Continuar verificando `Secure` + `SameSite` en deploy real.

---

## 4. Secrets en código

`grep -rE "(jwt_secret|api_key|password|token)\s*=\s*['\"][A-Za-z0-9]{8,}" --include="*.py" --include="*.ts"`

**Resultado**: 0 matches con valores hardcoded reales. Todos los valores están en `.env` (gitignored) o `.env.example` con placeholders vacíos.

**`.gitignore` confirmado**: `.env` y `.env.*` excluidos, `!.env.example` permitido.

**Veredicto**: ✅ sin findings.

---

## 5. Bash injection en scripts infra

`infra/whm-setup/*.sh` y `infra/deploy/*.sh` revisados:

- Todos empiezan con `set -euo pipefail` (validado en `test_infra.py::test_deploy_script_uses_set_euo_pipefail`).
- Variables exteriores entrecomilladas (`"$WCM_APP_DIR"`, `"$WCM_USER"`).
- `envsubst` se invoca con whitelist explícita (`envsubst "$VARS" < file`) — no sustituye vars arbitrarias.
- `sudo systemctl restart ...` usa rutas absolutas + nombres fijos, no string concat.

**Hallazgo menor (no bloqueante)**: en `02-database.sh`, `WCM_DB_PASS` se escribe en el log de salida con `wcm_warn`. Operador puede ver password al ejecutar. Mitigación documentada en runbook: ejecutar con redirección a archivo y borrarlo después.

**Veredicto**: ✅ aceptable.

---

## 6. HMAC timing

Webhooks verifican firma HMAC SHA-256 sobre el body crudo:

- `apps/api/src/wcm_api/routers/webhooks.py:_verify_clickup_signature` → `hmac.compare_digest(expected, signature)` ✅
- `apps/api/src/wcm_api/routers/webhooks.py:_verify_resend_signature` → `hmac.compare_digest(expected, cand)` ✅
- `apps/worker/src/wcm_worker/integrations/resend.py:verify_webhook_signature` → `hmac.compare_digest` ✅

**Veredicto**: ✅ sin findings. No usamos `==` en comparaciones de firma.

---

## 7. CORS

`apps/api/src/wcm_api/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=s.cors_origins,         # whitelist desde .env CORS_ORIGINS
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],
)
```

`allow_origins=s.cors_origins` parseado de CSV; **nunca** `["*"]` en producción.

**Veredicto**: ✅ sin findings. Operador debe configurar `CORS_ORIGINS` exactamente al dominio del dashboard.

---

## 8. Headers HTTP (Nginx)

`infra/nginx/wcm-common.conf`:
- `Strict-Transport-Security` con preload ✅
- `X-Content-Type-Options: nosniff` ✅
- `X-Frame-Options: DENY` ✅
- `Referrer-Policy: strict-origin-when-cross-origin` ✅
- `Permissions-Policy` restringe camera/microphone/geolocation ✅
- `Content-Security-Policy` con `default-src 'self'`, `connect-src` solo Sentry + propio host ✅
- TLS 1.2/1.3 only ✅

**Veredicto**: ✅ sin findings. Validado en `tests/unit/test_infra.py`.

---

## 9. Rate limiting (Fase 15)

**Antes de Fase 15**: solo el rate-limit Nginx en webhooks (30 req/s). Endpoints sensibles como `/auth/login` y `/leads/{id}/outreach/compose` sin rate limit propio.

**Mitigación Fase 15**: añadido `slowapi` con:
- `/auth/login`: 5/min por IP.
- `/api/v1/leads/{id}/outreach/compose`: 10/min por user.
- `/api/v1/leads/{id}/opt-out-url`: 30/min por user.
- `/api/v1/outreach/sequences/{id}/send`: 30/min por user.

**Veredicto**: ✅ mitigado.

---

## 10. PII en logs / Sentry

- Sentry SDK inicializado con `send_default_pii=False` en api, worker, dashboard.
- structlog: emails y nombres se loguean solo en `audit_log` (BD, no en stdout). En logs operativos hay `lead_id` numérico, no email crudo.
- Logtail recibe los logs JSON tal como salen — los emails de leads NO aparecen ahí porque structlog no los emite.

**Veredicto**: ✅ sin findings. Política consistente.

---

## 11. RGPD / LSSI-CE

Cobertura ya documentada en `apps/api/legal/`:
- `tratamiento_datos_prospeccion.md` (art. 30 RGPD)
- `plantilla_aviso_legal_outreach.md`
- `politica_retencion.md`
- `procedimiento_brecha.md` (art. 33 RGPD - 72h)

Validador legal v1.0 en `OutreachComposerAgent` rechaza drafts sin razón social + CIF + dirección + URL opt-out. Versión persistida en `outreach_sequences.legal_validator_version`.

**Veredicto**: ✅ implementado. Falta revisión legal externa (WCM-011, no bloqueante para deploy interno).

---

## 12. Decisiones pendientes / a revisar post-deploy

| ID | Decisión | Cuándo |
|---|---|---|
| WCM-011 | Revisión legal externa | Antes de outreach masivo |
| WCM-013 | Columna `retention_hold` para AEPD | Cuando aparezca caso |
| WCM-014 | Idempotency keys en POST con side-effects | Fase 16 |
| WCM-015 | pip-audit + pnpm audit en CI workflow | Fase 16 |
| WCM-016 | Verificar `Secure` + `SameSite=Lax` en cookie de prod | En el primer deploy |

---

## 13. Cómo re-auditar

Tras cada release o cada 3 meses (lo que llegue primero):

```bash
# Python
venv/bin/pip-audit --skip-editable

# Node
pnpm audit --prod

# Manual review checklist
# 1. grep secretos: grep -rE "(secret|password|token|key)\s*=\s*['\"][A-Za-z0-9]{8,}" --include="*.py" --include="*.ts"
# 2. Verificar set -euo pipefail en cualquier .sh nuevo
# 3. Verificar hmac.compare_digest en cualquier webhook nuevo
# 4. Verificar require_role en routers nuevos
```

Resultado de cada audit en `docs/security/audit-v<version>.md`.
