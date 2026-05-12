# tests/integration

Tests de integración — tocan servicios reales (DB local, Redis local, WP sandbox, mocks de APIs externas).

## Estado

Vacío en Fase 0. Se materializa desde la **Fase 4 — WP client** en adelante.

## Convenciones

- DB de tests: `webcafeina_migrator_test` (separada de la de dev).
- Redis DB 15 reservada para tests.
- WP sandbox: instancia local o staging compartida (a definir en Fase 4).
- Cleanup obligatorio entre tests (truncate tables, flush redis).

## Estructura prevista

```
tests/integration/
├── db/                       # tests sobre Postgres real
├── wp/                       # tests contra WP sandbox
├── scraper/                  # tests contra fixtures de páginas servidas localmente
├── pipeline/                 # tests del pipeline e2e en modo dry-run
└── conftest.py               # fixtures compartidas
```

## Cómo ejecutar

(A documentar en Fase 4)

```bash
pytest tests/integration --integration
```

(El flag `--integration` evita correr estos tests por defecto en CI rápido.)

Ver [STATE.md](../../STATE.md).
