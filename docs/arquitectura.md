# Arquitectura — Webcafeína Migrator

> Documento vivo. Última revisión: Fase 14 (2026-05-13).

---

## 1. Visión general

Webcafeína Migrator es un monorepo que combina dos productos sobre la misma infraestructura:

- **Prospección**: descubrir empresas con webs Wix/Hostinger AI/Webflow → enriquecer datos públicos → preparar drafts de outreach LSSI-CE compliant para revisión humana.
- **Migración**: convertir esas webs a WordPress + Bricks Builder, preservando contenido/SEO/assets, generando un checklist humano de tareas residuales.

Comparten: BD, scraping core, cumplimiento legal, dashboard, observabilidad.

```mermaid
flowchart LR
    subgraph "Productos"
      P[Prospección]
      M[Migración]
    end
    P -->|lead cualificado, opcional| M
    P --> O1[Audit log + opt-out RGPD]
    M --> O2[Checklist humano + WP listo]
```

---

## 2. Topología de ejecución (producción)

Single-server WHM/cPanel (ADR-031). Toda la stack en un nodo AlmaLinux con systemd.

```mermaid
flowchart TB
    subgraph "WHM/cPanel host"
      N[Nginx 443]
      subgraph "systemd units"
        API[wcm-api.service<br/>uvicorn :8000]
        W[wcm-worker.service<br/>celery worker]
        B[wcm-beat.service<br/>celery beat]
        D[wcm-dashboard.service<br/>node :3000]
      end
      PG[(PostgreSQL 16<br/>+ pgvector)]
      R[(Redis 7<br/>broker + cache)]
      J[journald → Logtail]
    end

    N -->|/| D
    N -->|/api| API
    API <--> PG
    API -->|enqueue| R
    R -->|consume| W
    B -->|schedule| R
    W <--> PG
    D -->|fetch| API

    subgraph "External"
      R2[Cloudflare R2]
      RES[Resend SMTP]
      ST[Sentry]
      LT[Logtail]
      GP[Google Places]
      CU[ClickUp]
    end

    W --> R2
    W --> RES
    W --> GP
    W --> CU
    API --> ST
    W --> ST
    J --> LT
```

---

## 3. Componentes lógicos del código

```mermaid
flowchart TB
    subgraph "apps/"
      DASH[dashboard<br/>Next.js 15 + shadcn]
      A[api<br/>FastAPI + JWT]
      WK[worker<br/>Celery + 20 agentes]
    end
    subgraph "packages/"
      DBS[db-schema<br/>SQLAlchemy + Alembic]
      ST[shared-types<br/>Pydantic + TS gemelos]
      SC[scraper-core<br/>Playwright + extractors]
      BT[bricks-transpiler<br/>HTML/CSS → Bricks JSON]
      WP[wp-client<br/>REST + WP-CLI/SSH]
      UI[ui<br/>shadcn compartido]
    end
    subgraph "cli/"
      CLI[wcm CLI<br/>Typer + Rich]
    end

    DASH --> ST
    DASH --> UI
    A --> ST
    A --> DBS
    WK --> ST
    WK --> DBS
    WK --> SC
    WK --> BT
    WK --> WP
    CLI --> A
```

---

## 4. Flujo de migración (15 fases del orchestrator)

Cada fase está implementada por un subagente que vive en `apps/worker/src/wcm_worker/agents/*.py`. El orchestrator (`pipeline.py`) las ejecuta en orden, con saltos condicionales por `condition_attr`.

```mermaid
flowchart TD
    Start([Operador crea proyecto]) --> Orch[Orchestrator.run_project]
    Orch --> S1[scrape_origin<br/>ScraperOriginAgent]
    S1 --> S2[extract_content<br/>ContentExtractorAgent]
    S2 --> S3[preserve_seo<br/>SeoPreserverAgent]
    S2 --> S4[optimize_assets<br/>AssetOptimizerAgent<br/>opcional]
    S2 --> S5[detect_multilang<br/>MultilangHandlerAgent]
    S3 & S4 & S5 --> S6[transpile_bricks<br/>BricksTranspilerAgent]
    S6 --> S7[deploy_wp<br/>WpDeployerAgent]
    S7 --> S8a{has_ecommerce?}
    S8a -->|sí| S8[migrate_woo<br/>WooMigratorAgent]
    S8a -->|no| S9a
    S8 --> S9a{is_multilang?}
    S9a -->|sí| S9[configure_wpml<br/>WpmlConfiguratorAgent]
    S9a -->|no| S10
    S9 --> S10[rebuild_forms<br/>FormsRebuilderAgent<br/>opcional]
    S10 --> S11[visual_diff<br/>VisualDiffAgent<br/>opcional]
    S11 --> S12[qa<br/>QaRunnerAgent<br/>opcional]
    S12 --> S13[generate_checklist<br/>ChecklistGeneratorAgent<br/>opcional]
    S13 --> S14[sync_clickup<br/>ClickupSyncerAgent<br/>opcional]
    S14 --> S15[notify<br/>ResendNotifierAgent<br/>opcional]
    S15 --> End([COMPLETED o QA_FAILED])

    S6 -.->|fail required| Blocked([BLOCKED_HUMAN_INPUT])
    S7 -.->|fail required| Blocked
```

Estados posibles del proyecto al final:
- `COMPLETED`: todas las fases OK.
- `QA_FAILED`: alguna fase opcional falló (no bloquea pero hay revisión humana).
- `BLOCKED_HUMAN_INPUT`: alguna fase requerida falló → operador interviene.

---

## 5. Flujo de prospección

Independiente del flujo de migración; el lead cualificado puede (opcional) convertirse en proyecto.

```mermaid
flowchart LR
    A[Operador lanza campaña<br/>sector + región + target] --> B[ProspectorAgent<br/>Google Places legacy]
    B --> C[Lead.DISCOVERED]
    C --> D[FingerprinterAgent<br/>scraper-core/fingerprint]
    D --> E[Lead.FINGERPRINTED + builder_detected]
    E --> F[EnricherAgent<br/>emails, phones, socials,<br/>embedding e5-large 1024-dim]
    F --> G[Lead.ENRICHED + score]
    G --> H{Operador<br/>aprueba?}
    H -->|sí| I[OutreachComposerAgent<br/>Jinja2 + validador legal v1.0]
    H -->|no| Z[Lead.DISCARDED]
    I --> J[OutreachSequence.DRAFT_PENDING_REVIEW]
    J --> K[Operador revisa<br/>en dashboard]
    K -->|approve| L[Sequence.READY]
    L --> M[OutreachSenderAgent<br/>Resend]
    M --> N[OutreachSend.SENT<br/>message_id persistido]
    N --> O[Webhook Resend<br/>opens/bounces/replies]
    O --> P[Send.{OPENED,BOUNCED,REPLIED}]
```

> El envío real **nunca** es automático: cada secuencia requiere transición manual `DRAFT_PENDING_REVIEW → READY → IN_PROGRESS`. Validación legal LSSI-CE se aplica en cada body (razón social + CIF + dirección + URL opt-out).

---

## 6. Modelo de datos (tablas principales)

```mermaid
erDiagram
    PROJECTS ||--o{ PROJECT_PHASES : "ejecuta"
    PROJECTS ||--o{ SCRAPED_PAGES : "tiene"
    SCRAPED_PAGES ||--o{ CONTENT_BLOCKS : "compone"
    SCRAPED_PAGES ||--o{ BRICKS_PAGES : "traduce a"
    PROJECTS ||--o{ ASSETS : "incluye"
    PROJECTS ||--o{ RESIDUAL_TASKS : "genera"
    PROJECTS ||--o{ SEO_REDIRECTS : "preserva"
    RESIDUAL_TASKS }o--|| CLICKUP_TASKS : "clickup_task_id"

    LEADS ||--o{ LEAD_ENRICHMENTS : "enriquece"
    LEADS ||--o{ OUTREACH_SEQUENCES : "campaign"
    OUTREACH_SEQUENCES ||--o{ OUTREACH_SENDS : "steps"
    OPT_OUT_LOG }o--|| LEADS : "email match"

    USERS ||--o{ AUDIT_LOG : "actor"
    AUDIT_LOG }o--|| LEADS : "entity"
    AUDIT_LOG }o--|| PROJECTS : "entity"

    PROJECTS {
        int id PK
        string client_name
        string source_url
        string target_domain
        bool has_ecommerce
        bool is_multilang
        enum status
    }
    LEADS {
        int id PK
        string url UK
        string business_name
        enum builder_detected
        float builder_confidence
        array emails
        enum status
        int score
        vector embedding "1024 dim"
    }
    OUTREACH_SEQUENCES {
        int id PK
        int lead_id FK
        json steps_json
        enum status
        bool legal_validation_passed
    }
    OPT_OUT_LOG {
        int id PK
        string email
        datetime opted_out_at "NEVER deleted"
    }
```

Detalle completo en `packages/db-schema/src/wcm_db/models/` y migraciones Alembic en `packages/db-schema/alembic/versions/`.

---

## 7. Observabilidad (ADR-028/029)

```mermaid
flowchart LR
    subgraph "API + Worker + Dashboard"
      L[structlog JSON]
      M[prometheus-client]
      S[sentry-sdk]
    end
    L --> J[journald]
    J --> LT[Logtail<br/>Better Stack]
    M --> P["/metrics<br/>endpoint"]
    P --> GA[Grafana Agent<br/>scrape]
    GA --> GC[Grafana Cloud]
    S --> Sentry[Sentry<br/>3 proyectos:<br/>api/worker/dashboard]

    HD["/health/deep<br/>db + redis + r2"] --> Probe[Monitoring probe]
```

- **Logs estructurados**: JSON en prod, ConsoleRenderer en dev. Stdlib puenteado para que uvicorn/sqlalchemy/httpx también emitan JSON.
- **Errores**: Sentry con `send_default_pii=False`. PII off por defecto.
- **Métricas**: HTTP requests + latency, Celery tasks + agent runs, custom counters.
- **Health**: `/health` simple (process up), `/ready` (db ping), `/health/deep` (db + redis + r2).

Todo perezoso: sin DSN/token, no se inicializa nada. Permite levantar la app en dev sin cuentas externas.

---

## 8. Cumplimiento legal

```mermaid
flowchart TD
    Discovery[Lead.DISCOVERED<br/>via Google Places] --> Legal{Base jurídica}
    Legal -->|art. 6.1.f RGPD<br/>+ art. 21.2 LSSI-CE| OK[OK contactar B2B]
    OK --> Compose[OutreachComposerAgent]
    Compose --> Validate{Validador legal v1.0}
    Validate -->|falta razón social/<br/>CIF/dirección/opt-out| Reject[Reject draft]
    Validate -->|todo OK| Persist[OutreachSequence<br/>DRAFT_PENDING_REVIEW]
    Persist --> Review[Operador revisa]
    Review --> Send[OutreachSenderAgent]
    Send --> DC[Doble check opt_out_log]
    DC -->|email en log| Abort[Abort + AuditLog]
    DC -->|email limpio| Resend[Resend API]
    Resend --> Persist2[OutreachSend.SENT<br/>+ AuditLog SEND<br/>legal_ground=6.1.f]

    Resend -.->|email link| Recipient[Receptor]
    Recipient -->|un clic| OptOut[/opt-out?token=...]
    OptOut --> Delete[Lead borrado<br/>+ opt_out_log forever]
```

Docs legales: `apps/api/legal/{tratamiento_datos_prospeccion,plantilla_aviso_legal_outreach,politica_retencion,procedimiento_brecha}.md`.

Retención automática vía Celery beat (`wcm.maintenance.retention_sweep` diario 03:30 Europe/Madrid):
- Leads DISCOVERED sin outreach > 12 meses → DELETE.
- Leads OUTREACH_SENT sin respuesta > 24 meses → DISCARDED → DELETE +6 meses.
- `opt_out_log` NUNCA se borra.
- `error_log` > 90 días → DELETE.

---

## 9. Subagentes runtime (worker) vs descriptors (.claude/)

Distinción importante (ADR-020):

| Carpeta | Propósito | Tipo |
|---|---|---|
| `.claude/agents/*.md` | Descriptores para Claude Code en build-time (con frontmatter Anthropic) | Markdown |
| `apps/worker/src/wcm_worker/agents/*.py` | Implementaciones runtime Python que ejecuta Celery | Código |

Los nombres coinciden por convención, pero viven en planos distintos.

**20 subagentes** runtime, todos heredando de `BaseAgent`:

| # | Nombre | Phase | Estado | Notas |
|---|---|---|---|---|
| 1 | orchestrator | (meta) | real | `pipeline.py` |
| 2 | scraper-origin | scrape_origin | real | BFS interno + httpx |
| 3 | content-extractor | extract_content | real | Wix/Hostinger/Webflow |
| 4 | seo-preserver | preserve_seo | real | meta+OG+canonical+hreflang |
| 5 | asset-optimizer | optimize_assets | **real Fase 10** | Pillow→WebP→R2 |
| 6 | multilang-handler | detect_multilang | real | `<html lang>` + counts |
| 7 | bricks-transpiler | transpile_bricks | real | wraps `packages/bricks-transpiler` |
| 8 | wp-deployer | deploy_wp | real | REST + WP-CLI/SSH |
| 9 | woo-migrator | migrate_woo | stub | Fase post-MVP |
| 10 | wpml-configurator | configure_wpml | stub | Fase post-MVP |
| 11 | forms-rebuilder | rebuild_forms | stub | Fase post-MVP |
| 12 | visual-diff | visual_diff | stub | Fase post-MVP |
| 13 | qa-runner | qa | stub | Fase post-MVP |
| 14 | checklist-generator | generate_checklist | stub | Fase post-MVP |
| 15 | clickup-syncer | sync_clickup | **real Fase 10** | REST v2 |
| 16 | resend-notifier | notify | **real Fase 10** | SDK Resend |
| 17 | prospector | (campaña) | **real Fase 9** | Google Places legacy |
| 18 | fingerprinter | (lead) | real | `scraper-core.fingerprint` |
| 19 | enricher | (lead) | **real Fase 9+10** | + embedding e5-large 1024d |
| 20 | outreach-composer | (lead) | **real Fase 9** | Jinja2 + validador legal |
| 21 | outreach-sender | (send) | **real Fase 10** | Resend + double-check opt-out |

(Sí, 21 — añadimos OutreachSender en Fase 10 como complemento del Composer.)

---

## 10. Decisiones arquitectónicas

32 ADRs vivos en [docs/decisiones.md](./decisiones.md). Más relevantes para entender la arquitectura:

- **ADR-001**: sin Docker.
- **ADR-010** (superseded por ADR-023): embeddings con sentence-transformers + e5-large 1024d.
- **ADR-017**: proxy layered free→paid.
- **ADR-019**: versionado `/api/v1/*` + opt-out fuera del prefijo.
- **ADR-020**: subagentes runtime vs descriptors `.claude/`.
- **ADR-022**: JetBrains Mono en toda la UI.
- **ADR-024**: Google Places API legacy (no New).
- **ADR-025/26/27**: Resend, R2 vía boto3, ClickUp `clickup_task_id`.
- **ADR-028/29**: observabilidad perezosa + Prometheus registry propio.
- **ADR-030/31**: systemd nativo + single-server WHM.
- **ADR-032**: e2e Playwright + pipeline test + visual regression.

---

## 11. Referencias

- Estado actual y avance: [`../STATE.md`](../STATE.md)
- Issues abiertos: [`../ISSUES.md`](../ISSUES.md)
- Despliegue: [`./despliegue.md`](./despliegue.md)
- Playbook operativo: [`./playbook-operativo.md`](./playbook-operativo.md)
- Migración (op): [`./migracion.md`](./migracion.md)
- Prospección (op): [`./prospeccion.md`](./prospeccion.md)
- Glosario: [`./glossary.md`](./glossary.md)
