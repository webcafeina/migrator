# tests/e2e

Tests end-to-end del Webcafeína Migrator — Playwright Test sobre el dashboard.

## Estado

Vacío en Fase 0. Se materializa en **Fase 13 — Tests e2e**.

## Convenciones

- Playwright Test (Node).
- Entorno completo levantado (Postgres + Redis + API + Worker + Dashboard).
- Fixtures aisladas: cada test crea su proyecto/lead y los limpia al final.
- No tocar producción.

## Escenarios principales previstos

1. Auth flow (login, logout)
2. Crear proyecto manualmente → ver timeline → exportar checklist
3. Lanzar prospección dummy → ver leads → convertir uno a proyecto
4. Ver visual diff de un proyecto demo y abrir comparativa interactiva
5. Marcar tarea residual como completada → verificar sync a ClickUp (mock)

## Cómo ejecutar

(A documentar en Fase 13)

```bash
pnpm --filter @webcafeina/dashboard test:e2e
```

Ver [STATE.md](../../STATE.md).
