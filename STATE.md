# STATE.md — Cursor de avance Webcafeína Migrator

> Este fichero se actualiza al final de cada sesión de construcción.
> Lo lee Claude al iniciar cada nueva sesión para retomar exactamente donde quedó.

---

## Fase actual

- **Fase 0 — Bootstrap**: ✅ COMPLETADA (esta sesión)
- **Próxima fase**: Fase 1 — DB y modelos (`packages/db-schema` + `packages/shared-types`)

> 🟡 **Antes de iniciar Fase 1**, el humano debe revisar el bootstrap y confirmar.

---

## Tabla de progreso

| Fase | Nombre | Estado | Notas |
|---|---|---|---|
| 0 | Bootstrap | ✅ Completada | Estructura + agentes + skills + memoria |
| 1 | DB y modelos | ⏳ Pendiente | Bloqueada por revisión humana de Fase 0 |
| 2 | Bricks transpiler | ⏳ Pendiente | Bloqueada por WCM-001 (export Bricks real) |
| 3 | Scraper core | ⏳ Pendiente | Bloqueada por credenciales Bright Data |
| 4 | WP client | ⏳ Pendiente | Bloqueada por credenciales WP sandbox |
| 5 | API backend | ⏳ Pendiente | |
| 6 | Worker + subagentes | ⏳ Pendiente | |
| 7 | CLI | ⏳ Pendiente | |
| 8 | Dashboard | ⏳ Pendiente | |
| 9 | Prospección | ⏳ Pendiente | Bloqueada por WCM-002 (datos legales) |
| 10 | Integraciones externas | ⏳ Pendiente | |
| 11 | Observabilidad | ⏳ Pendiente | |
| 12 | Infra/Deploy | ⏳ Pendiente | |
| 13 | Tests e2e | ⏳ Pendiente | |
| 14 | Documentación | ⏳ Pendiente | |
| 15 | Hardening | ⏳ Pendiente | |

---

## Tareas completadas en la última sesión (Fase 0)

- [x] Estructura completa de carpetas creada
- [x] `.gitignore` (Python + Node + macOS + IDEs + env)
- [x] `.env.example` con todas las variables necesarias agrupadas por sección
- [x] `pnpm-workspace.yaml`, `turbo.json`, `package.json` raíz
- [x] `LICENSE` propietario
- [x] `README.md` completo
- [x] `ISSUES.md` local con 6 issues iniciales (WCM-001 a WCM-006)
- [x] `CLAUDE.md` con memoria persistente (paleta, stack, reglas)
- [x] `STATE.md` (este fichero)
- [x] 20 subagentes en `.claude/agents/`
- [x] 20 skills en `.claude/skills/`
- [x] READMEs en cada subcarpeta de `apps/`, `packages/`, `cli/`, `infra/`, `tests/`
- [x] Stubs en `docs/`: arquitectura, prospeccion, migracion, despliegue, playbook-operativo, decisiones
- [x] `git init` + commit `chore: bootstrap monorepo structure`

---

## Próximas tareas inmediatas (Fase 1)

Cuando el humano apruebe la Fase 0, ejecutar en orden:

1. Diseñar modelos SQLAlchemy 2.x para todas las tablas listadas en §5 del prompt maestro:
   `leads`, `lead_enrichments`, `outreach_sequences`, `outreach_sends`, `projects`, `project_phases`, `scraped_pages`, `assets`, `content_blocks`, `bricks_pages`, `woo_products`, `seo_redirects`, `residual_tasks`, `audit_log`, `error_log`, `users`.
2. Configurar Alembic, migración inicial.
3. Crear índice vectorial pgvector en `leads`.
4. Generar tipos TS gemelos en `packages/shared-types` (con generador automático o duplicación supervisada).
5. Tests unitarios de modelos (constraints, relaciones, defaults).
6. Commit: `feat(db): initial schema and models`.

---

## Bloqueos / decisiones humanas pendientes

| ID | Descripción | Necesario para fase | Dueño |
|---|---|---|---|
| WCM-001 | Export JSON real de Bricks Builder mínimo | 2 | humano |
| WCM-002 | Datos legales Webcafeína S.L. (CIF, dirección, URL privacidad) | 9 | humano |
| WCM-003 | URLs reales para calibrar skills extracción Wix/Hostinger/Webflow | 3 | humano |
| WCM-005 | Confirmar lista ClickUp por defecto para tareas residuales | 10 | humano |

(detalle en [`ISSUES.md`](./ISSUES.md))

---

## Decisiones tomadas en esta sesión

- Git: `git init` local sin remote. Push y creación de repo GitHub se difieren.
- TODOs: `docs/decisiones.md` (ADR) + `ISSUES.md` local con IDs `WCM-NNN`.
- Identidad commit: `user.email=info@webcafeina.com`, `user.name=Webcafeína`.
- Modelos de agentes: Opus para `orchestrator` y `bricks-transpiler` (críticos), Sonnet por defecto para el resto.

---

## Notas para la próxima sesión

- Antes de tocar nada, leer este fichero y `CLAUDE.md`.
- Si el humano ha añadido issues nuevos, integrarlos en la planificación.
- La Fase 1 no requiere credenciales externas: solo Postgres local con extensión `pgvector`.
- Si Postgres no está disponible localmente, parar y pedir al humano antes de seguir.
