# Webcafeína Migrator

Herramienta interna de **Webcafeína** (Cáceres, España) para:

1. **Prospección comercial automatizada** — descubrir, identificar y enriquecer leads de empresas cuyas webs están construidas con Hostinger AI Builder, Wix o Webflow, y preparar listas + secuencias de outreach personalizadas (con revisión humana antes de envío).
2. **Migración técnica automatizada** — convertir esas webs origen a **WordPress + Bricks Builder** (+ WooCommerce + WPML cuando proceda), preservando estructura, contenido, SEO y assets, y generando un checklist de tareas residuales para lo no automatizable.

> ⚠️ Esta herramienta es de uso interno y propietario. Ver [`LICENSE`](./LICENSE).

---

## Tabla de contenidos

- [Estado del proyecto](#estado-del-proyecto)
- [Arquitectura](#arquitectura)
- [Stack técnico](#stack-técnico)
- [Setup local](#setup-local)
- [Setup en servidor (WHM/cPanel)](#setup-en-servidor-whmcpanel)
- [Convenciones de desarrollo](#convenciones-de-desarrollo)
- [Branches y releases](#branches-y-releases)

---

## Estado del proyecto

Ver siempre [`STATE.md`](./STATE.md) para el cursor de avance entre sesiones de construcción.

La construcción está dividida en 16 fases (0–15). **Fases 0–10 completadas** a 2026-05-13: bootstrap, DB+modelos, Bricks transpiler, scraper core, WP client, API backend, worker+subagentes, CLI, dashboard, prospección RGPD/LSSI-CE compliant, **integraciones externas (ClickUp/Resend/R2)** con sync residuales bidireccional, envío de outreach, optimización de assets a WebP y purga automática de retención. Próxima fase: 11 — Observabilidad (Sentry, structlog, Logtail).

Test suite total: **325 tests Python + 15 TS** pasando.

---

## Arquitectura

Resumen rápido (detalle completo en [`docs/arquitectura.md`](./docs/arquitectura.md)):

```
                            ┌────────────────────────┐
   Operador  ───────►       │  Dashboard (Next.js)   │
   (Webcafeína)             │  /  CLI (Typer)        │
                            └───────────┬────────────┘
                                        │ HTTP / IPC
                                        ▼
                            ┌────────────────────────┐
                            │  API (FastAPI)         │
                            └───────────┬────────────┘
                                        │ Celery
                                        ▼
                            ┌────────────────────────┐
                            │  Worker (subagentes)   │
                            │  ┌──────┐  ┌────────┐  │
                            │  │Prosp │  │Migrate │  │
                            │  └──────┘  └────────┘  │
                            └─┬─────┬─────┬────────┬─┘
                              │     │     │        │
                              ▼     ▼     ▼        ▼
                          Postgres Redis  R2     WP target
                          + pgvec
```

---

## Stack técnico

| Capa | Tecnología |
|---|---|
| Lenguaje backend | Python 3.12 |
| Framework API | FastAPI |
| Frontend | Next.js 15 (App Router) + TypeScript 5 |
| UI | shadcn/ui + Tailwind CSS (paleta Webcafeína) |
| DB | PostgreSQL 16 + pgvector |
| Cola | Celery + Redis |
| Scraping | Playwright (Python) + Puppeteer sidecar (Node) + playwright-stealth |
| Proxies | Bright Data residencial |
| Builder destino | WordPress + Bricks Builder |
| Monorepo | pnpm workspaces + Turborepo |
| Despliegue | WHM/cPanel con systemd + Nginx — **sin Docker** |

Detalle exhaustivo en [`CLAUDE.md`](./CLAUDE.md).

---

## Setup local

> **Disponibilidad real**: Fase 0 deja solo la estructura. Los pasos abajo se irán materializando entre las Fases 1–8.

### Prerequisitos

- Python 3.12
- Node 20+ y pnpm 9+
- PostgreSQL 16 local con extensión `pgvector`
- Redis 7+
- (Opcional) cwebp binario para optimización de imágenes

### Pasos (cuando estén disponibles)

```bash
# Clonar
git clone <REMOTE_TBD> webcafeina-migrator
cd webcafeina-migrator

# Variables de entorno
cp .env.example .env
$EDITOR .env

# Dependencias
pnpm install
python -m venv .venv && source .venv/bin/activate
pip install -e ./apps/api -e ./apps/worker -e ./cli

# Base de datos
createdb webcafeina_migrator
alembic upgrade head

# Desarrollo
pnpm dev       # arranca api, worker y dashboard en paralelo
```

---

## Setup en servidor (WHM/cPanel)

**No usamos Docker**. Despliegue como procesos nativos gestionados por systemd. Ver [`infra/whm-setup/`](./infra/whm-setup/) y [`docs/despliegue.md`](./docs/despliegue.md).

Resumen:

```bash
ssh root@servidor.webcafeina.com
cd /opt && git clone <REMOTE_TBD> webcafeina-migrator
cd webcafeina-migrator
bash infra/whm-setup/01-system-deps.sh
# ... 02 → 10
```

systemd units que se levantan:

- `webcafeina-api.service`
- `webcafeina-worker.service`
- `webcafeina-beat.service`
- `webcafeina-dashboard.service`

---

## Convenciones de desarrollo

### Commits

Conventional Commits estrictos:

```
feat:     nueva funcionalidad
fix:      corrección de bug
chore:    tareas de mantenimiento, dependencias, configuración
docs:     documentación
test:     añadir o modificar tests
refactor: refactor sin cambio de comportamiento
perf:     mejora de rendimiento
ci:       cambios en CI/CD
```

Cada commit asistido por Claude lleva al final:
```
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

### Estilo de código

- **Python**: `ruff` + `black`, `mypy --strict`
- **TypeScript**: `eslint` + `prettier`, `tsc --strict`
- **Tests**: pytest + pytest-asyncio (Python), Vitest + Playwright Test (TS)

### Cobertura objetivo

- `packages/`: 70% mínimo
- `apps/`: 50% mínimo

### TODOs

Prohibidos los TODOs sin issue. Hasta tener el repo en GitHub:

- Decisiones arquitectónicas → [`docs/decisiones.md`](./docs/decisiones.md) (ADR ligero)
- Pendientes técnicos → [`ISSUES.md`](./ISSUES.md) con IDs `WCM-NNN`

### Secretos

- Nunca commitear `.env`.
- `.env.example` es el inventario versionado.
- En servidor, secretos en `/etc/webcafeina-migrator/env` con permisos `0600`.

---

## Branches y releases

- `main` → producción
- `develop` → staging
- `feature/<slug>` → trabajo en curso
- `hotfix/<slug>` → arreglos urgentes sobre `main`

Releases por tags semver (`v0.1.0`, `v0.2.0`, ...) sobre `main`. Deploy a producción se dispara con el workflow `deploy-production.yml` (a crear en Fase 12).

---

## Cómo añadir un nuevo subagente o skill

1. Crear fichero en `.claude/agents/<nombre>.md` o `.claude/skills/<nombre>/SKILL.md`.
2. Respetar el frontmatter Anthropic (`name`, `description`, `tools`, `model` cuando proceda).
3. Documentar inputs/outputs esperados, dependencias y casos límite.
4. Si introduce dependencias nuevas, añadirlas al `.env.example`.
5. Registrar en `STATE.md` y, si aplica, en `docs/arquitectura.md`.

---

## Contacto

- **Email proyecto**: info@webcafeina.com
- **Equipo**: Álvaro, Samuel, Adrián, Nacho
