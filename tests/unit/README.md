# tests/unit

Tests unitarios.

## Estado

Vacío en Fase 0. Se materializa progresivamente desde la **Fase 1**.

## Convenciones

- **Python**: `pytest` + `pytest-asyncio`. Fixtures en `conftest.py` por paquete.
- **TS**: `vitest`. Mocks con `vi.mock`.
- Cobertura mínima objetivo: 70% en `packages/`, 50% en `apps/`.

## Estructura prevista

```
tests/unit/
├── packages/
│   ├── bricks-transpiler/      # Fase 2
│   ├── scraper-core/           # Fase 3
│   ├── wp-client/              # Fase 4
│   └── db-schema/              # Fase 1
├── apps/
│   ├── api/                    # Fase 5
│   ├── worker/                 # Fase 6
│   └── cli/                    # Fase 7
└── fixtures/
    ├── html/                   # snapshots HTML por builder
    ├── bricks/                 # JSON expected
    └── ...
```

Ver [STATE.md](../../STATE.md).
