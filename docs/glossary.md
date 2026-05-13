# Glosario — Webcafeína Migrator

Términos que aparecen en el producto, código, dashboard y documentación.

Pensado para que un nuevo miembro del equipo (o un desarrollador externo) entienda el vocabulario sin tener que abrir el código.

---

## A

### Agent / Subagente
Clase Python que hereda de `BaseAgent` y vive en `apps/worker/src/wcm_worker/agents/*.py`. Cada uno representa una fase del pipeline de migración o un paso del flujo de prospección. **No confundir** con los descriptors `.claude/agents/*.md`, que son para Claude Code en build-time (ADR-020).

Lista completa de los 21 agentes en [`docs/arquitectura.md §9`](./arquitectura.md#9-subagentes-runtime-worker-vs-descriptors-claude).

### Asset
Recurso binario (imagen, PDF, vídeo) descargado del sitio origen y subido a Cloudflare R2. Tabla `assets`. Optimizado a WebP por `AssetOptimizerAgent`.

### AssetStatus
Enum: `PENDING → DOWNLOADED → OPTIMIZED → UPLOADED → READY`. El agente cambia el estado según avanza el procesado.

### AuditLog
Tabla append-only con todas las acciones críticas del sistema. Cada entrada incluye `actor`, `action`, `entity_type`, `entity_id`, `payload`, `legal_ground`. Se conserva 5 años (política de retención).

---

## B

### BricksPage
Representación de una página WordPress importable directamente por Bricks Builder. Contenido en `bricks_pages.bricks_json` como JSON validado contra el schema de Bricks. Generada por `BricksTranspilerAgent` a partir de `ContentBlock`s.

### Bricks Builder
Page builder comercial para WordPress (https://bricksbuilder.io). Builder destino exclusivo del MVP (ADR-002). Toda migración termina en una instalación WP con Bricks como tema activo.

### Builder (origen)
La tecnología con la que está construida la web del cliente: `wix`, `hostinger_ai`, `webflow`, `wordpress`, `squarespace`, `shopify`, `other`, `unknown`. Detectado por `FingerprinterAgent`.

---

## C

### Celery
Framework Python de task queue. Worker + Beat. Tareas serializadas en JSON, broker Redis. Ver `apps/worker/src/wcm_worker/celery_app.py`.

### Checklist (residual)
Conjunto de tareas que el sistema NO puede automatizar y deben hacerse manualmente para que la migración esté lista para go-live. Persistido en `residual_tasks` con categoría `BLOCKING_GO_LIVE | CLIENT_CONFIG | VISUAL_CONTENT | POST_GO_LIVE | OTHER`.

### ClickUp
Herramienta de gestión de tareas externa donde el equipo Webcafeína trabaja. Sync bidireccional con `residual_tasks` vía `ClickupSyncerAgent` (saliente) + webhook (entrante).

### ContentBlock
Unidad mínima semántica extraída del HTML del builder origen. Ejemplos: `hero`, `section`, `text`, `image`, `cta`, `form`, `gallery`. Persistido en `content_blocks`. Generado por `ContentExtractorAgent`.

### Cookie wcm_session
Cookie http-only que el dashboard usa para autenticación. Contiene un JWT firmado con `JWT_SECRET`. Configurable: `SESSION_COOKIE_NAME` en `.env`.

---

## D

### Dashboard
Aplicación Next.js 15 que viven en `apps/dashboard/`. UI para operadores. JetBrains Mono en toda la UI (ADR-022). Paleta WCM estricta.

### Diff visual
Comparación pixel-a-pixel entre el screenshot del origen y el screenshot del WP destino, por página. Score 0-1. Threshold mínimo `VISUAL_DIFF_THRESHOLD=0.85`. (Implementación post-MVP por `VisualDiffAgent`.)

### DPO
Data Protection Officer. Webcafeína no tiene uno formalmente designado todavía; Álvaro asume la función internamente.

---

## E

### Embedding
Vector de 1024 dimensiones (float32) que representa semánticamente el texto de un lead. Generado por `sentence-transformers` con modelo `intfloat/multilingual-e5-large` (ADR-023). Almacenado en columna `pgvector` `leads.embedding`. Permite búsqueda de leads similares con `<->` operator.

### EnricherAgent
Subagente que pobla `lead.emails`, `lead.phones`, `lead.social_links`, `lead.score` y calcula el embedding. Tras `FingerprinterAgent` en el flujo de prospección.

---

## F

### Fase
Cada paso del pipeline de migración. 15 fases en `_DEFAULT_PHASES` (ver `apps/worker/.../pipeline.py`). Estado individual en `project_phases.status`: `PENDING → RUNNING → COMPLETED | FAILED | SKIPPED`.

### FingerprinterAgent
Subagente que toma la URL y devuelve `builder_detected` + `builder_confidence` + `builder_evidence`. Usa `wcm_scraper_core.fingerprint` con `patterns.yml`.

---

## G

### GDPR / RGPD
Reglamento General de Protección de Datos. Base jurídica del tratamiento en Webcafeína Migrator: **art. 6.1.f** (interés legítimo). Documentos en `apps/api/legal/`.

---

## H

### Health checks
- `/health`: el proceso responde. Sin tocar DB.
- `/ready`: la DB responde a `SELECT 1`.
- `/health/deep`: db + redis + r2 con status individual. Solo accesible internamente (ACL Nginx).

### Hardening
Directivas systemd que restringen lo que el proceso puede hacer: `NoNewPrivileges`, `ProtectSystem=strict`, `PrivateTmp`, `SystemCallFilter=@system-service`, etc. Aplicado a las 4 units (ADR-030).

---

## I

### Idempotente
Una operación es idempotente si ejecutarla N veces produce el mismo resultado que ejecutarla una sola vez. Casi todas las operaciones del worker son idempotentes (UPSERT con `ON CONFLICT DO NOTHING`, retention sweep, sync ClickUp). Importante porque `task_acks_late=true` permite re-ejecución tras crash.

### Interés legítimo (art. 6.1.f RGPD)
Base jurídica del tratamiento. Aplicada al contacto comercial B2B sobre datos profesionales públicos. Documentada en `apps/api/legal/tratamiento_datos_prospeccion.md`. Combinada con art. 21.2 LSSI-CE.

---

## J

### JetBrains Mono
Tipografía monospace usada en toda la UI del dashboard (ADR-022). Por preferencia del operador y por coherencia con la naturaleza terminal-friendly de la herramienta.

### JWT (JSON Web Token)
Token firmado usado para autenticación (cookie `wcm_session`) y para opt-out (link en email). Dos tipos distinguibles por claim `purpose`: `session` o `opt_out`. Firmado con `JWT_SECRET`.

---

## L

### Lead
Empresa descubierta por `ProspectorAgent` con potencial de ser cliente. Tabla `leads`. Estados: `DISCOVERED → FINGERPRINTED → ENRICHED → OUTREACH_PREPARED → OUTREACH_SENT → RESPONDED/CONVERTED/DISCARDED/OPTED_OUT/MANUAL_REVIEW`.

### LSSI-CE
Ley de Servicios de la Sociedad de la Información y Comercio Electrónico (España). Art. 21.2 permite contacto comercial B2B sobre productos relacionados con la actividad profesional del receptor, incluso por email, sin consentimiento previo.

### Logtail / Better Stack
Servicio de log aggregation. El handler `LogtailHandler` se añade al root logger si `LOGTAIL_SOURCE_TOKEN` está configurado.

---

## M

### Multilang
Atributo `project.is_multilang`. Si true, el pipeline ejecuta la fase `configure_wpml` (post-MVP).

---

## O

### Opt-out
Mecanismo por el que un receptor de outreach se da de baja. Implementación:
- **Automático**: link `/opt-out?token=<jwt>` en cada email → un clic → borra lead + persiste email en `opt_out_log` para siempre.
- **Manual**: operador registra opt-out por canal no-email vía `wcm leads consent --action objection_received`.

### `opt_out_log`
Tabla append-only. **Nunca se borra**. Base jurídica para no recontactar (interés legítimo). UNIQUE(email, channel). Idempotente.

### Orchestrator
`apps/worker/src/wcm_worker/pipeline.py`. State machine que recorre las 15 fases de un proyecto en orden, instanciando cada subagente. Captura errores tipados y decide skip/abort según `required` + tipo de error.

### OutreachSequence / OutreachSend
- **Sequence**: una "campaña" de outreach para un lead específico. Compuesta de N `OutreachSend` (steps). Status: `DRAFT_PENDING_REVIEW → READY → IN_PROGRESS → COMPLETED/PAUSED/OPTED_OUT`.
- **Send**: un email concreto a enviar dentro de la sequence. Status: `QUEUED → SENT → OPENED/REPLIED/BOUNCED/FAILED`.

---

## P

### pgvector
Extensión PostgreSQL para tipos vector + operadores de similitud (`<->`, `<#>`, `<=>`). Usada en `leads.embedding` para búsqueda semántica.

### Pipeline
Sinónimo de "orchestrator + 15 fases". Lo que ejecuta una migración completa.

### Playwright
Framework de e2e testing usado en el dashboard (`apps/dashboard/tests/e2e/`). Browsers headless Chromium en CI.

### Prometheus
Sistema de métricas pull-based. Endpoint `/metrics` en la API expone formato OpenMetrics. Registry propio (ADR-029) para evitar contaminación entre tests.

### Project
Una migración. Tabla `projects`. Status: `QUEUED → RUNNING → COMPLETED | QA_FAILED | BLOCKED_HUMAN_INPUT | CANCELLED`.

### Prospección
Proceso de descubrir leads cualificados. Independiente del pipeline de migración. Fases: prospect → fingerprint → enrich → compose → review → send.

---

## R

### Redis
Broker Celery (DB 1) + result backend (DB 2) + cache (DB 0).

### Resend
Proveedor de email transaccional. SDK Python oficial. ADR-025: único proveedor email saliente. Webhook entrante con HMAC para opens/bounces/replies.

### ResidualTask
Tarea generada por `ChecklistGeneratorAgent` que requiere intervención humana. Se sincroniza con ClickUp.

### Retención
Política de borrado automático por TTL. Cron `wcm.maintenance.retention_sweep` diario 03:30 Europe/Madrid (ADR-027). Documentada en `apps/api/legal/politica_retencion.md`.

### Rollback
- **Deploy**: `infra/deploy/rollback.sh` vuelve al SHA guardado en `.cache/last-deploy-sha`.
- **Migración Alembic**: `alembic downgrade -1` baja una migración.
- **Proyecto migración**: si el cliente cambia de opinión, `wcm projects cancel <id>`.

---

## S

### ScrapedPage
Una página HTML del sitio origen, scrapeada por `ScraperOriginAgent`. Tabla `scraped_pages`. Padre lógico de los `ContentBlock`s extraídos.

### Sentry
APM + error tracking. 3 proyectos separados: `migrator-api`, `migrator-worker`, `migrator-dashboard`. PII off por defecto (`send_default_pii=False`).

### Skill
Documento `.md` con frontmatter Anthropic en `.claude/skills/*/SKILL.md`. Conocimiento reutilizable para Claude Code en build-time. **No es código ejecutable**.

### structlog
Librería Python de logging estructurado. JSON renderer en producción, ConsoleRenderer (sin colores) en dev. Stdlib `logging` puenteado para que libs externas también emitan JSON.

### systemd
Sistema de gestión de procesos en Linux. 4 unit files + 1 target en `infra/systemd/` (ADR-030).

---

## T

### Transpilar / Transpiler
`BricksTranspilerAgent` toma `ContentBlock`s + estilos + assets y genera el JSON estructura que Bricks Builder importa nativamente. Lógica en `packages/bricks-transpiler/`.

---

## U

### Uvicorn
ASGI server que sirve FastAPI. 2 workers por defecto en `wcm-api.service`. Logs en stdout → journald.

---

## V

### Validador legal (v1.0)
Función en `apps/worker/.../outreach_composer.py` que verifica que cada step de outreach contiene:
- Razón social Webcafeína S.L.
- CIF B10463990
- Dirección postal completa
- URL opt-out funcional

Si falta cualquiera, `OutreachComposerError` y no se persiste la sequence. La versión se incrementa cuando cambian las reglas y se guarda en `outreach_sequences.legal_validator_version`.

### Visual diff
Ver "Diff visual" arriba.

---

## W

### WCM
Prefijo de identificadores internos. `WCM-NNN` en `ISSUES.md`, `wcm_*` en código Python, `@webcafeina/*` en packages npm, `wcm-*` en clases CSS.

### Webhook
Endpoints públicos (sin auth de operador) que reciben notificaciones de servicios externos. Validación HMAC sobre body crudo.
- `/api/v1/webhooks/clickup`: status updates de ClickUp.
- `/api/v1/webhooks/resend`: opens/bounces/replies.

### WP-CLI
Herramienta CLI oficial de WordPress. Usada vía SSH (paramiko) para operaciones bulk en el WP destino (importar bricks_pages, instalar plugins). `wcm_wp_client.ssh_cli`.

### WPML
Plugin WP de multi-idioma. Configurado por `WpmlConfiguratorAgent` solo si `project.is_multilang=true`.

---

## Y

### Yoast SEO
Plugin WP siempre instalado en destino. SEO meta + sitemap + redirects 301 (junto con Redirection).

---

## Z

(Sin entradas todavía.)

---

## Referencias cruzadas

- Arquitectura general: [`./arquitectura.md`](./arquitectura.md)
- Decisiones: [`./decisiones.md`](./decisiones.md)
- Despliegue: [`./despliegue.md`](./despliegue.md)
- Operación migración: [`./migracion.md`](./migracion.md)
- Operación prospección: [`./prospeccion.md`](./prospeccion.md)
- Runbooks: [`./playbook-operativo.md`](./playbook-operativo.md)
