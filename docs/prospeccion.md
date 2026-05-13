# Prospección — guía del operador

Cómo lanzar una campaña, revisar los drafts de outreach generados y aprobar el envío. Pensado para el equipo comercial de Webcafeína.

> **Importante**: el sistema **nunca** envía outreach automáticamente. Cada secuencia requiere aprobación humana explícita antes de salir.

---

## 0. Modelo mental

Una campaña no es un objeto persistido — es un job Celery que genera leads. Los leads sí persisten en BD. El operador:

1. **Lanza** una campaña con `sector + región + objetivo`.
2. **Revisa** los leads cualificados que aparecen.
3. **Aprueba** drafts de outreach uno a uno (o por lote en el futuro).
4. **Espera** respuestas que llegan via webhook Resend.
5. **Maneja** opt-outs (automáticos vía link) y opt-outs manuales (alguien llama por teléfono pidiendo baja).

Ciclo de vida del lead:

```
DISCOVERED → FINGERPRINTED → ENRICHED → OUTREACH_PREPARED → OUTREACH_SENT → RESPONDED/CONVERTED
                                                              ↘ DISCARDED
                                                              ↘ OPTED_OUT (terminal)
                                                              ↘ MANUAL_REVIEW
```

---

## 1. Lanzar una campaña

### Desde el dashboard

1. Login en `https://migrator.webcafeina.com` con email y password.
2. Navega a **Campaigns** (icono megáfono en sidebar).
3. Rellena el formulario:
   - **Sector**: descripción libre (`restaurante`, `clínica dental`, `agencia inmobiliaria`).
   - **Región**: ciudad o provincia (`Cáceres`, `Madrid`, `Valencia`).
   - **Target count**: número objetivo de leads (1-500, default 50).
   - **Exclude domains**: dominios a excluir (uno por línea).
4. Click **"Lanzar campaña"**. Devuelve `task_id` Celery.

### Desde la CLI

```bash
wcm campaigns launch \
    --sector "agencia inmobiliaria" \
    --region "Madrid" \
    --target-count 30 \
    --exclude-domains "competencia1.com,competencia2.com"
```

### Qué pasa por dentro

```
1. ProspectorAgent monta query "{sector} en {region}" → Google Places legacy
2. Por cada place con website:
   - Normaliza URL (sin www, sin trailing slash)
   - Filtra blocked_types (gas_station, parking, hospital, etc.)
   - INSERT ON CONFLICT DO NOTHING en leads (dedupe por URL)
   - Persiste lead_enrichment con raw payload + legal_ground=6.1.f
   - AuditLog DISCOVER
3. FingerprinterAgent corre por cada lead nuevo
4. EnricherAgent corre tras fingerprinter:
   - Extrae emails/teléfonos/socials del HTML
   - Calcula embedding 1024d (sentence-transformers e5-large)
   - Score 0-100 según señales acumuladas
```

**Tiempo típico**: 30 leads tardan ~5-10 minutos según latencia Google Places y cuota.

**Coste**: Text Search legacy ~$32/1000 calls, Place Details ~$17/1000. Google da $200/mes gratis → cabe ~6000 leads/mes gratis.

---

## 2. Revisar leads

### Listado

`/leads` en el dashboard. Filtros:
- **Sector / región**: texto.
- **Builder detected**: `wix` / `hostinger_ai` / `webflow` / `wordpress` / `other` / `unknown`.
- **Status**: `discovered` / `fingerprinted` / `enriched` / `outreach_prepared` / ...
- **Min score**: 0-100. Para una primera revisión rápida: `score >= 60`.

Columnas: business_name, sector/región, builder, score, status, last_crawl_at.

### Detalle de un lead

`/leads/{id}` muestra 4 cards:
1. **Identificación**: business_name, URL, sector, región, country.
2. **Fingerprint**: builder + confidence + evidencia JSON (qué patterns dispararon).
3. **Contacto**: emails, phones, social_links.
4. **Embedding**: model + dim + fecha (para búsqueda semántica de similares).

### Score

Heurística MVP (`apps/worker/.../enricher.py:_compute_score`):
- +20 si builder detectado con confianza ≥ 0.7
- +15 si tiene al menos un email
- +10 si tiene teléfono
- +5 si tiene perfiles sociales
- +10 si tiene sector definido
- Máximo 100

Score < 30 = lead débil, probablemente no merece la pena.
Score 50-70 = buen candidato para outreach.
Score > 70 = excelente, contactar prioritariamente.

---

## 3. Generar el draft de outreach

Para un lead con `status=ENRICHED` y al menos un email:

### Dashboard

Botón **"Componer outreach"** en `/leads/{id}` → encola `OutreachComposerAgent`.

### CLI

```bash
wcm leads compose-outreach 123
```

### Qué genera

Una `OutreachSequence` con status `DRAFT_PENDING_REVIEW`, conteniendo 2 steps por defecto:
1. **`wix_intro_es`**: email inicial, 0 días delay.
2. **`followup_es`**: seguimiento, 5 días delay.

Ambos pasan por el **validador legal v1.0**:
- Razón social Webcafeína S.L. presente.
- CIF B10463990 presente.
- Dirección postal completa presente.
- URL opt-out funcional presente.

Si falta cualquiera, la composición falla con `OutreachComposerError` y NO se persiste la sequence.

---

## 4. Aprobar y enviar

### Dashboard

`/outreach/sequences/{id}` muestra:
- Status actual de la sequence.
- Preview de cada step (subject + body markdown-rendered).
- Botones: **Approve** / **Pause** / **Cancel** / **Send next step**.

Transiciones permitidas:

| Desde | Approve | Pause | Cancel |
|---|---|---|---|
| `DRAFT_PENDING_REVIEW` | → `READY` | — | → `COMPLETED` |
| `READY` | — | → `PAUSED` | → `COMPLETED` |
| `IN_PROGRESS` | — | → `PAUSED` | — |
| `PAUSED` | → `READY` | — | → `COMPLETED` |

> No se puede aprobar una sequence con `legal_validation_passed=false`. El sistema lo impide en el endpoint.

### Enviar el primer step

Una vez en `READY`, click **Send next step** (o `POST /api/v1/outreach/sequences/{id}/send`). Esto:
1. Encola `wcm.outreach.send_step` con el primer `OutreachSend` QUEUED.
2. El `OutreachSenderAgent`:
   - Vuelve a verificar `opt_out_log` (doble check anti-spam).
   - Llama a Resend.
   - Persiste `provider_message_id` y `sent_at`.
   - Promueve la sequence a `IN_PROGRESS`.
   - Escribe `AuditLog SEND` con `legal_ground=6.1.f`.
3. Webhook Resend va actualizando `opened_at`, `bounced_at` según eventos.

---

## 5. Gestionar respuestas y opt-outs

### Opt-out automático

El receptor pulsa el link al pie del email. Llega a `/opt-out?token=<jwt>`:
1. Valida el JWT (purpose=opt_out, firmado con JWT_SECRET).
2. Inserta en `opt_out_log` (UNIQUE email+channel, idempotente).
3. Borra el lead (cascade limpia enrichments + sequences).
4. Muestra HTML de confirmación con la paleta Webcafeína.

`opt_out_log` **nunca se borra**. Es la base jurídica para no recontactar.

### Opt-out manual

Cliente llama por teléfono o responde por email pidiendo baja. Operador:

```bash
# Vía CLI
wcm leads consent 123 --action objection_received --note "Llamó pidiendo baja"

# Vía dashboard
# /leads/123 → botón "Registrar oposición"
```

Esto:
- Marca el lead como `OPTED_OUT`.
- AuditLog `OPT_OUT` con el operador como actor.
- El email NO se añade a `opt_out_log` automáticamente (porque venía por canal no-email). Hazlo manual si quieres bloquear futuros recontactos por email:

```bash
wcm optout add cliente@empresa.com
```

### Manual review

Si dudas (cliente "no estoy seguro", o el lead parece sensible), marcar `manual_review`:

```bash
wcm leads consent 123 --action manual_review --note "Llamar antes de enviar"
```

Lead pasa a `MANUAL_REVIEW`. No se envía outreach hasta que cambies el status manualmente.

---

## 6. Búsqueda semántica de leads similares (futura)

Cada lead tiene un embedding 1024-dim guardado en columna pgvector. Esto permite (en el dashboard, Fase 16+):

> "Mostrar leads parecidos a este Bar Pepe en otras ciudades"

Implementado a futuro con `SELECT ... ORDER BY embedding <-> '<vec>' LIMIT 10`. El modelo es `intfloat/multilingual-e5-large` (ADR-023).

---

## 7. Auditoría: leer `audit_log`

Cada acción crítica sobre un lead queda en `audit_log`. Consulta desde dashboard `/audit?entity=lead&entity_id=123` o:

```bash
wcm audit list --entity lead --entity-id 123
```

Acciones típicas:
- `DISCOVER`: prospector descubrió el lead.
- `FINGERPRINT`: builder detectado.
- `ENRICH`: emails/phones/embedding calculados.
- `CREATE` (entity=outreach_sequence): composer generó draft.
- `UPDATE` (entity=outreach_sequence): operador aprobó/pausó.
- `SEND` (entity=outreach_send): mensaje enviado vía Resend.
- `UPDATE` (entity=outreach_send, payload.event=email.opened): receptor abrió.
- `OPT_OUT`: lead opted-out (auto o manual).

Cada entrada incluye `legal_ground=6.1.f` y, donde aplique, `operator_role`.

---

## 8. Política de retención (automática)

Cron Celery beat `wcm.maintenance.retention_sweep` diario 03:30 Europe/Madrid (`apps/worker/.../tasks/maintenance.py`):

- Lead `DISCOVERED` sin outreach > 12 meses → DELETE (cascade limpia enrichments).
- Lead `OUTREACH_SENT` sin respuesta > 24 meses → status = `DISCARDED`.
- Lead `DISCARDED` > 6 meses adicionales → DELETE.
- `opt_out_log` **nunca** se borra.
- `error_log` > 90 días → DELETE.

Cada ejecución del cron escribe un `audit_log` con stats.

Para excepciones AEPD (lead congelado en expediente): WCM-013 abierto, columna `retention_hold` pendiente.

---

## 9. Métricas a vigilar

| Métrica | Dónde | Healthy range |
|---|---|---|
| Leads descubiertos/mes | `/leads/count` en dashboard | depende del volumen comercial objetivo |
| Tasa fingerprint correcto | manual sample | > 80% |
| Coste Google Places mes | Google Cloud Console | < €200 (free tier) |
| Open rate outreach | Sentry events email.opened | > 25% indica buen subject |
| Bounce rate | webhook bounces | < 5% (si más, revisar lista) |
| Opt-out rate | count opt_out_log / SENT mes | < 2% (si más, ajustar tono) |

---

## 10. Troubleshooting

| Síntoma | Diagnóstico | Acción |
|---|---|---|
| Campaña encolada pero sin leads en 30 min | `wcm campaigns status <task_id>` | Si `OVER_QUERY_LIMIT`: esperar reset cuota (next day). Si `REQUEST_DENIED`: API key sin permisos → revisar Google Cloud Console. |
| Lead con `builder_detected=unknown` | revisar fingerprint evidence | El patterns.yml del scraper-core no tiene huella para esa tecnología. Añadir patterns y re-ejecutar `wcm leads refingerprint <id>`. |
| Compose falla con "Datos legales ausentes" | `.env` server | Rellenar `COMPANY_CIF`, `COMPANY_ADDRESS`, `COMPANY_PRIVACY_POLICY_URL`. |
| Compose falla con "previously opted-out" | `opt_out_log` | Bien — el sistema está protegiendo. No insistir. |
| Send falla con `OutreachSenderError: Resend send falló` | Sentry worker | Si dominio no verificado: configurar SPF/DKIM/DMARC en Resend. |
| Webhook Resend no actualiza opens | logs nginx + sentry | Verificar `RESEND_WEBHOOK_SECRET` configurado y firma `svix-signature` válida. |

Más en [docs/playbook-operativo.md](./playbook-operativo.md).
