# Playbook operativo

Runbooks para incidentes y operaciones recurrentes. Cada sección sigue el formato: **Síntoma → Diagnóstico → Acción → Verificación → Escalación**.

Audiencia: equipo Webcafeína. **Convención**: las escalaciones se dirigen al equipo en conjunto (canal interno habitual), no a personas concretas. El equipo decide internamente quién toma cada incidente.

---

## Índice rápido

- [INC-01: Proyecto atascado en RUNNING](#inc-01-proyecto-atascado-en-running)
- [INC-02: Lead duplicado](#inc-02-lead-duplicado)
- [INC-03: Solicitud RGPD por canal no-email](#inc-03-solicitud-rgpd-por-canal-no-email)
- [INC-04: Brecha de seguridad](#inc-04-brecha-de-seguridad)
- [INC-05: Deploy fallido en producción](#inc-05-deploy-fallido-en-producción)
- [INC-06: Worker no consume tareas](#inc-06-worker-no-consume-tareas)
- [INC-07: Resend rebota emails (>5%)](#inc-07-resend-rebota-emails-5)
- [INC-08: /metrics o /health/deep accesibles públicamente](#inc-08-metrics-o-healthdeep-accesibles-públicamente)
- [INC-09: Migración Alembic falló en producción](#inc-09-migración-alembic-falló-en-producción)
- [INC-10: ClickUp webhook no actualiza residual_tasks](#inc-10-clickup-webhook-no-actualiza-residual_tasks)

---

## INC-01: Proyecto atascado en RUNNING

**Síntoma**: `project.status = RUNNING` durante >1 hora sin actualizar `project_phases`.

**Diagnóstico**:
```bash
# Última fase persistida
psql -c "SELECT id, phase_name, status, started_at, updated_at FROM project_phases WHERE project_id=42 ORDER BY id DESC LIMIT 5;"

# Logs del worker en esa ventana temporal
journalctl -u wcm-worker --since '90 minutes ago' | grep "project_id=42"

# Cola Redis
redis-cli -n 1 llen webcafeina    # tareas pendientes
redis-cli -n 1 lrange webcafeina 0 -1 | head -3
```

Causas habituales:
- Worker murió mid-task. La fase quedó en RUNNING sin acks. `task_acks_late=true` hace que Celery reasigne, pero si nadie reinicia el worker, queda colgado.
- Sandbox WP cayó en mitad del deploy.
- Bright Data proxy banneado.

**Acción**:
```bash
# 1. Asegurar worker arriba
sudo systemctl status wcm-worker
sudo systemctl restart wcm-worker

# 2. Si el worker arrancó pero no recoge, forzar resume
wcm projects resume 42

# 3. Si tras 15 min sigue parado: cancelar y empezar de nuevo desde el último estado bueno
psql -c "UPDATE projects SET status='BLOCKED_HUMAN_INPUT' WHERE id=42;"
wcm projects resume 42
```

**Verificación**: `project_phases.updated_at` avanza en los próximos 5 minutos.

**Escalación**: Si tras dos resumes sigue atascado, abrir incidente en Sentry y avisar al equipo Webcafeína.

---

## INC-02: Lead duplicado

**Síntoma**: Dos rows en `leads` con URL casi idéntica (`example.com` y `www.example.com/`).

**Diagnóstico**:
```sql
SELECT id, url, created_at FROM leads
WHERE url ILIKE '%example.com%'
ORDER BY created_at;
```

Causas:
- El normalizador (`_normalize_url` en prospector) no manejó algún edge case (puerto, query string).
- Lead importado manualmente vía API con URL no normalizada.

**Acción**:
1. **Antes de borrar nada**: comprobar si alguno tiene `outreach_sequences` activas:
   ```sql
   SELECT s.id, s.status FROM outreach_sequences s WHERE s.lead_id IN (101, 202);
   ```
2. Si uno tiene secuencia activa y otro no: borrar el sin secuencia.
3. Si ambos tienen secuencia: cancelar la más reciente, mover sus sends al lead más antiguo, borrar el duplicado.
4. Registrar la decisión en `audit_log` (CREATE entity=incident).

**Verificación**: no quedan dos rows para la misma empresa.

**Prevención**: si el caso es nuevo, actualizar `_normalize_url` y añadir test en `test_prospector.py::test_normalize_url_*`.

---

## INC-03: Solicitud RGPD por canal no-email

**Síntoma**: cliente llama por teléfono / WhatsApp / formulario web pidiendo acceso / rectificación / supresión / oposición.

**Diagnóstico**: identificar el lead/usuario afectado y la base jurídica de su tratamiento.

**Acción**:

### Derecho de acceso (art. 15 RGPD)
1. Buscar el lead:
   ```sql
   SELECT * FROM leads WHERE 'cliente@empresa.com' = ANY(emails);
   ```
2. Exportar todo a JSON:
   ```bash
   wcm leads export <id> --format json --include-enrichments --include-audit > export.json
   ```
3. Enviar al solicitante por canal seguro (email cifrado o entrega física firmada).
4. Registrar en `audit_log` (action=UPDATE, payload={request_type=access, fulfilled_at=...}).

### Derecho de oposición (art. 21 RGPD)
```bash
wcm leads consent <id> --action objection_received --note "Llamada del 2026-05-13"
# Además, añadir email a opt_out_log para bloqueos futuros
wcm optout add cliente@empresa.com
```

### Derecho de supresión (art. 17 RGPD)
Más estricto que opt-out. Borrar TODO rastro:
```bash
wcm leads delete <id> --reason "art. 17 RGPD"
# Anonimizar también en audit_log (mantener entrada pero quitar PII)
wcm audit anonymize --entity lead --entity-id <id>
```

**Verificación**: el solicitante no debe aparecer en `SELECT * FROM leads WHERE ...`. En `audit_log` queda el trail anonimizado.

**Escalación**: si el solicitante invoca AEPD o exige plazos cortos, avisar al equipo Webcafeína inmediatamente.

**Plazo legal**: máximo 1 mes desde la solicitud (extensible a 2 meses con justificación).

---

## INC-04: Brecha de seguridad

**Síntoma**: cualquiera de:
- Alerta Sentry crítica afectando endpoints de leads/outreach.
- Acceso no autorizado detectado en `audit_log`.
- Filtración de credencial (.env, JWT_SECRET, API key Google).
- Pérdida de backup que contenía `leads`/`opt_out_log`.

**Procedimiento completo**: [`apps/api/legal/procedimiento_brecha.md`](../apps/api/legal/procedimiento_brecha.md).

**T+0 (primeros 30 min)**:
1. Notificar al DPO interno (equipo Webcafeína, decisión colegiada hasta nombramiento formal).
2. Pausar el worker si el vector incluye prospección activa:
   ```bash
   sudo systemctl stop wcm-worker
   ```
3. Rotar secrets afectados:
   ```bash
   # JWT_SECRET
   NEW_SECRET=$(openssl rand -hex 32)
   sed -i "s/^JWT_SECRET=.*/JWT_SECRET=$NEW_SECRET/" /home/webcafeina/migrator/.env
   sudo systemctl restart wcm-api
   # Invalida todas las sesiones activas → operadores tendrán que re-login.
   ```

**T+1h → T+72h**: notificación AEPD obligatoria si afecta a >100 titulares (gravedad A/B). Plazo art. 33 RGPD: 72 horas desde T+0.

**Post-mortem T+7 días**: documento blameless con timeline + causa raíz + correctivas con due date a 30 días en ClickUp.

---

## INC-05: Deploy fallido en producción

**Síntoma**: `infra/deploy/deploy.sh` salió con código != 0 (o GitHub Actions failed).

**Diagnóstico**:
```bash
# En el servidor
journalctl -u wcm-api --since '10 minutes ago' | tail -50
journalctl -u wcm-worker --since '10 minutes ago' | tail -50
cat /home/webcafeina/migrator/.cache/last-deploy-sha   # SHA al que volver
```

**Acción**:
1. Rollback inmediato:
   ```bash
   sudo -u webcafeina bash /home/webcafeina/migrator/infra/deploy/rollback.sh
   ```
2. Si la migración Alembic ya corrió y rompió compat:
   ```bash
   cd /home/webcafeina/migrator
   sudo -u webcafeina venv/bin/alembic -c packages/db-schema/alembic.ini downgrade -1
   ```
3. Verificar:
   ```bash
   bash infra/deploy/health-check.sh
   ```

**Verificación**: `/health/deep` devuelve `status=ok`, dashboard accesible.

**Prevención**: el `deploy.sh` ya guarda SHA previo automáticamente. Si esto pasa repetidamente, revisar el job CI `python` — debería bloquear merges que rompan tests.

---

## INC-06: Worker no consume tareas

**Síntoma**: tareas encoladas en Redis no avanzan.

**Diagnóstico**:
```bash
sudo systemctl status wcm-worker
redis-cli -n 1 llen webcafeina            # tamaño de la cola
ps aux | grep celery                       # procesos worker activos
journalctl -u wcm-worker --since '5 minutes ago' | tail -30
```

Causas:
- Worker crashed por OOM (vigilar swap si RAM < 2GB).
- Redis caído (raro pero pasa).
- Worker bloqueado en una tarea que nunca termina (deadlock).

**Acción**:
```bash
# Restart worker
sudo systemctl restart wcm-worker

# Si la cola es enorme y bloquea: drenarla y re-encolar las críticas
redis-cli -n 1 del webcafeina

# Si Redis está caído
sudo systemctl restart redis
```

**Verificación**: `redis-cli -n 1 llen webcafeina` baja en los próximos 5 min.

**Escalación**: si pasa más de una vez por semana, abrir issue para investigar memory leak en el agente sospechoso.

---

## INC-07: Resend rebota emails (>5%)

**Síntoma**: en el dashboard, ratio `bounced_at IS NOT NULL / total sends` > 5%.

**Diagnóstico**:
```sql
SELECT
  COUNT(*) FILTER (WHERE status='bounced') AS bounced,
  COUNT(*) FILTER (WHERE status='sent') AS sent,
  ROUND(100.0 * COUNT(*) FILTER (WHERE status='bounced') / COUNT(*), 2) AS bounce_pct
FROM outreach_sends
WHERE sent_at > now() - interval '7 days';
```

Causas:
- SPF/DKIM/DMARC mal configurado en `webcafeina.com` → Resend marca bounces.
- Lista de leads con emails inventados o muy antiguos.
- Subject/contenido marcados como spam por filtros.

**Acción**:
1. Verificar en Resend dashboard → Domains → `webcafeina.com` está `verified`.
2. Si SPF/DKIM rojo: actualizar registros DNS según instrucciones Resend.
3. Si bounces por emails inválidos: pausar campañas afectadas:
   ```bash
   # Pausar todas las sequences IN_PROGRESS de una campaña sospechosa
   wcm outreach pause-by-sector "agencia inmobiliaria"
   ```
4. Limpiar los emails que han bounceado del lead pool:
   ```sql
   UPDATE leads SET status='discarded'
   WHERE id IN (SELECT DISTINCT lead_id FROM outreach_sends WHERE status='bounced');
   ```

**Verificación**: bounce rate baja del 5% en las próximas 48h.

**Escalación**: si Resend amenaza con suspender la cuenta por reputation, escalar al equipo Webcafeína.

---

## INC-08: /metrics o /health/deep accesibles públicamente

**Síntoma**: alguien externo puede hacer `curl https://api.migrator.webcafeina.com/metrics` y obtener respuesta.

**Diagnóstico**:
```bash
# Verificar config Nginx
sudo grep -A8 "location = /metrics" /etc/nginx/conf.d/api.migrator.webcafeina.com.conf
sudo grep -A8 "location = /health/deep" /etc/nginx/conf.d/api.migrator.webcafeina.com.conf
```

Debería incluir `deny all` + `allow 127.0.0.1`.

**Acción**:
```bash
# Si falta el ACL, restaurar desde el repo
sudo bash /home/webcafeina/migrator/infra/whm-setup/04-install-nginx.sh

# Verificar
sudo nginx -t
sudo systemctl reload nginx

# Confirmar desde fuera
curl -sI https://api.migrator.webcafeina.com/metrics    # debe ser 403
```

**Verificación**: 403 desde IP externa, 200 desde el servidor.

**Escalación**: registrar en log de incidentes; si la exposición duró >24h, considerar rotar JWT_SECRET y forzar re-login.

---

## INC-09: Migración Alembic falló en producción

**Síntoma**: `alembic upgrade head` durante deploy salió con error.

**Diagnóstico**:
```bash
cd /home/webcafeina/migrator
sudo -u webcafeina venv/bin/alembic -c packages/db-schema/alembic.ini current
sudo -u webcafeina venv/bin/alembic -c packages/db-schema/alembic.ini history --indicate-current
```

Causas típicas:
- Conflict en columna que ya tiene datos (NOT NULL sin default).
- pgvector extension no instalada en la DB.
- Lock en una tabla por una transacción larga abierta.

**Acción**:
1. Si es un lock:
   ```sql
   SELECT pid, query, state FROM pg_stat_activity WHERE state='active' AND xact_start < now() - interval '5 minutes';
   -- Si encuentras una transacción colgada del operador, kill:
   SELECT pg_terminate_backend(<pid>);
   ```
2. Si es schema conflict, downgrade y arreglar la migración en código:
   ```bash
   sudo -u webcafeina venv/bin/alembic -c packages/db-schema/alembic.ini downgrade -1
   ```
3. Si es pgvector ausente (raro):
   ```bash
   sudo -u postgres psql -d webcafeina_migrator -c "CREATE EXTENSION IF NOT EXISTS vector;"
   ```

**Verificación**: `alembic current` muestra el head correcto.

**Escalación**: si la migración corrió a medias y dejó la DB inconsistente, restaurar desde backup pg_dump del día.

---

## INC-10: ClickUp webhook no actualiza residual_tasks

**Síntoma**: el operador marca complete en ClickUp pero `residual_tasks.status` sigue `OPEN`.

**Diagnóstico**:
```bash
# ¿Llegan webhooks?
sudo grep "clickup_webhook" /var/log/nginx/wcm-access.log | tail -10

# ¿Falla la firma HMAC?
journalctl -u wcm-api --since '10 minutes ago' | grep "clickup_webhook"
```

Causas:
- `CLICKUP_WEBHOOK_SECRET` no configurado o mismatch con el secret en ClickUp.
- ClickUp deshabilitó el webhook por demasiados fallos consecutivos.
- El `clickup_task_id` en la `residual_task` apunta a un ID que el webhook no pasa correctamente.

**Acción**:
1. Verificar webhook activo en ClickUp dashboard → Settings → Apps → Webhooks.
2. Re-generar secret si hay sospecha:
   ```
   ClickUp Dashboard → Webhooks → Regenerate Secret
   .env del servidor → actualizar CLICKUP_WEBHOOK_SECRET
   sudo systemctl restart wcm-api
   ```
3. Forzar sync manual mientras tanto:
   ```bash
   wcm clickup sync-residuals <project_id>
   ```

**Verificación**: marcar una tarea complete en ClickUp y verificar que `residual_tasks.status = DONE` en <30 segundos.

---

## Tareas recurrentes (no incidentes)

### Rotación de credenciales (cada 6 meses)

```bash
# 1. Generar nuevo JWT_SECRET
NEW=$(openssl rand -hex 32)

# 2. Editar .env del servidor
sudo -u webcafeina sed -i "s/^JWT_SECRET=.*/JWT_SECRET=$NEW/" /home/webcafeina/migrator/.env

# 3. Restart (invalida todas las sesiones activas)
sudo systemctl restart wcm-api

# 4. Notificar al equipo que tendrán que re-login
```

Para API keys externas (Google, Resend, etc.): generar la nueva, añadir como segunda válida, swap en `.env`, restart, revocar la antigua.

### Backup manual de la DB

Programado: cron diario 03:00 + retención 14 días (ver `docs/despliegue.md` §8).

Manual:
```bash
sudo -u webcafeina pg_dump webcafeina_migrator | gzip > ~/backup-$(date +%F-%H%M).sql.gz
```

### Auditoría mensual de `audit_log`

Revisar el primer lunes de cada mes:
```sql
-- Acciones inusuales el último mes
SELECT actor, action, COUNT(*)
FROM audit_log
WHERE at > now() - interval '30 days'
GROUP BY actor, action
ORDER BY 3 DESC;

-- Opt-outs del mes
SELECT email, opted_out_at FROM opt_out_log
WHERE opted_out_at > now() - interval '30 days'
ORDER BY opted_out_at DESC;
```

Anotar en `apps/api/legal/registro_incidentes.md` cualquier cosa que llame la atención.
