# packages/db-schema

Schema PostgreSQL del Webcafeína Migrator. Modelos SQLAlchemy 2.x + migraciones Alembic + extensión pgvector.

## Estado

Vacío en Fase 0. Se materializa en **Fase 1 — DB y modelos** (próxima).

## Qué contendrá

- Modelos SQLAlchemy 2.x estilo declarativo (`models/`).
- Configuración Alembic (`alembic.ini`, `versions/`).
- Migración inicial con todas las tablas (`leads`, `projects`, `scraped_pages`, ..., ver §5 del prompt maestro).
- Índice vectorial pgvector en `leads.embedding` para búsqueda semántica.
- Constraints, foreign keys, indices.
- Audit trigger genérico para `audit_log`.

## Tablas principales

| Tabla | Propósito |
|---|---|
| `leads` | Webs identificadas en prospección |
| `lead_enrichments` | Datos enriquecidos por lead |
| `outreach_sequences`, `outreach_sends` | Secuencias y envíos |
| `projects`, `project_phases` | Migraciones |
| `scraped_pages`, `assets`, `content_blocks` | Datos de scraping |
| `bricks_pages` | Páginas transpiladas |
| `woo_products`, `seo_redirects`, `residual_tasks` | Outputs de migración |
| `audit_log`, `error_log` | Trazabilidad |
| `users` | Operadores |

## Comandos

(A documentar en Fase 1)

```bash
alembic upgrade head            # aplicar migraciones
alembic revision --autogenerate -m "..."   # nueva migración
```

Ver [STATE.md](../../STATE.md).
