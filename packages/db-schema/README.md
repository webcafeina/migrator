# packages/db-schema

Schema PostgreSQL del Webcafeína Migrator. Modelos SQLAlchemy 2.x + migraciones Alembic + extensión `pgvector`.

## Estado

Materializado en **Fase 1**. Incluye:

- 17 tablas (16 de dominio + `opt_out_log` para cumplimiento RGPD)
- Migración inicial `0001_initial_schema.py` escrita manualmente
- Extensión `pgvector` y índice `ivfflat` en `leads.embedding` (1024 dim, voyage-multilingual-2; ver ADR-010)
- Naming convention estable para constraints (`pk_*`, `ix_*`, `uq_*`, `fk_*`)

## Cómo aplicar la migración

```bash
# Requisitos: Postgres 16 corriendo, BD creada, usuario con permisos
export DATABASE_SYNC_URL=postgresql://webcafeina:CHANGE@localhost:5432/webcafeina_migrator

cd packages/db-schema
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]" -e ../shared-types
alembic upgrade head
```

## Tests

```bash
# Tests sin BD (siempre corren):
pytest

# Tests Postgres reales (skip si DATABASE_SYNC_URL no apunta a Postgres):
pytest -m postgres
```

## Estructura

```
src/wcm_db/
├── __init__.py        # exports públicos
├── base.py            # Base declarativa + TimestampMixin + naming convention
├── enums.py           # re-export desde wcm_types.enums
└── models/
    ├── users.py
    ├── leads.py             # Lead, LeadEnrichment, OptOutLog
    ├── outreach.py          # OutreachSequence, OutreachSend
    ├── projects.py          # Project, ProjectPhase
    ├── scraped_pages.py
    ├── assets.py
    ├── content_blocks.py
    ├── bricks_pages.py
    ├── woo_products.py
    ├── seo_redirects.py
    ├── residual_tasks.py
    └── audit.py             # AuditLog, ErrorLog

alembic/
├── alembic.ini
├── env.py
├── script.py.mako
└── versions/
    └── 0001_initial_schema.py
```

## Dependencias

- SQLAlchemy 2.x (async + sync; el modelo es agnóstico, las sesiones eligen)
- asyncpg + psycopg para async/sync
- Alembic 1.13+
- pgvector 0.3+
- `wcm-shared-types` (enums canónicos)

## Decisiones relacionadas

- [ADR-010](../../docs/decisiones.md): embedding 1024 dim con voyage-multilingual-2
- [ADR-011](../../docs/decisiones.md): enums viven en `wcm_types`, `wcm_db` re-exporta
