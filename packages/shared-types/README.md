# packages/shared-types

Tipos compartidos entre Python (Pydantic v2) y TypeScript 5. Fuente única de la verdad para el contrato de datos del sistema.

## Estado

Materializado en **Fase 1**. Incluye:

- 16 enums StrEnum en `wcm_types/enums.py`
- Schemas Pydantic v2 por entidad en `wcm_types/schemas/*.py`
- Script `scripts/gen-ts.sh` que produce `ts/index.d.ts` con `pydantic2ts`
- Validaciones estrictas: `extra="forbid"`, `str_strip_whitespace=True`, `from_attributes=True`

## Estructura

```
python/wcm_types/
├── __init__.py
├── enums.py                  # fuente única de los enums
└── schemas/
    ├── _base.py              # WcmModel + TimestampedRead
    ├── users.py
    ├── leads.py              # LeadCreate, LeadUpdate, LeadRead, LeadEnrichment*, OptOutLogRead
    ├── outreach.py
    ├── projects.py
    ├── scraped_pages.py
    ├── assets.py
    ├── content_blocks.py
    ├── bricks_pages.py
    ├── woo_products.py
    ├── seo_redirects.py
    ├── residual_tasks.py
    └── audit.py

ts/index.d.ts                 # generado, NO editar a mano
scripts/gen-ts.sh
```

## Generar tipos TS

```bash
# Desde la raíz del monorepo:
pnpm gen:types

# O directo:
bash packages/shared-types/scripts/gen-ts.sh
```

Requiere venv Python con `pydantic-to-typescript` instalado:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e "./packages/shared-types[dev]"
```

## Tests

```bash
cd packages/shared-types
pip install -e ".[dev]"
pytest
```

## Decisiones relacionadas

- [ADR-011](../../docs/decisiones.md): enums viven aquí, no en wcm_db
- [ADR-012](../../docs/decisiones.md): Pydantic v2 → TS automático con pydantic2ts (no manual)
