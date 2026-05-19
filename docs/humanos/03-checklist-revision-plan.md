# 03 — CHECKLIST DE REVISIÓN DEL PLAN

> Antes de aprobar el plan que te muestre Claude Code en modo plan, revisa esta checklist. Cualquier punto que falle, no apruebes: pide ajuste.

---

## A. REVISIÓN GENERAL DEL PLAN COMPLETO

### A.1 Estructura

- [ ] El plan está dividido en las 16 fases del prompt (0 a 15)
- [ ] El plan NO encadena fases automáticamente: cada fase requiere aprobación
- [ ] El plan NO incluye Docker, docker-compose, ni imágenes de contenedor en ninguna fase
- [ ] El plan menciona explícitamente "verificar versión última estable" en vez de fijar versiones inventadas
- [ ] El plan incluye commits convencionales por fase
- [ ] El plan incluye actualización de `STATE.md` tras cada fase

### A.2 Decisiones técnicas

- [ ] Python 3.12 y no otra versión
- [ ] Node 20 LTS y no otra
- [ ] PostgreSQL 16 y no otra
- [ ] pgvector mencionado explícitamente
- [ ] FastAPI, no Flask ni Django
- [ ] Next.js 15 App Router, no Pages Router
- [ ] shadcn/ui + Tailwind, no Material UI ni Chakra
- [ ] Celery + Redis, no RQ ni Dramatiq
- [ ] Playwright Python como scraper primario
- [ ] Puppeteer Node como sidecar SOLO para Webflow
- [ ] WPML como plugin multiidioma (no Polylang ni TranslatePress)
- [ ] Gravity Forms como plugin de formularios
- [ ] Bricks Builder como page builder destino
- [ ] WooCommerce como ecommerce destino
- [ ] systemd o Supervisor para procesos, NO Docker
- [ ] Nginx como reverse proxy

### A.3 Subagentes

- [ ] Aparecen los 20 subagentes listados en el prompt
- [ ] Cada uno tiene archivo propio en `.claude/agents/`
- [ ] Cada uno tiene descripción de responsabilidad
- [ ] El `orchestrator` está marcado como coordinador principal

### A.4 Skills

- [ ] Aparecen las 20 skills listadas en el prompt
- [ ] Cada skill tiene carpeta propia en `.claude/skills/`
- [ ] Cada skill tiene `SKILL.md` con frontmatter Anthropic correcto

### A.5 Estructura de monorepo

- [ ] `apps/api`, `apps/dashboard`, `apps/worker`
- [ ] `packages/bricks-transpiler`, `packages/scraper-core`, `packages/wp-client`, `packages/shared-types`, `packages/db-schema`, `packages/ui`
- [ ] `cli/`
- [ ] `infra/systemd/`, `infra/nginx/`, `infra/deploy/`, `infra/whm-setup/`
- [ ] `tests/`
- [ ] `docs/`
- [ ] `.github/workflows/`

### A.6 Cumplimiento legal

- [ ] Fase 9 incluye `apps/api/legal/` con plantillas RGPD/LSSI-CE
- [ ] Función `record_consent` y `process_opt_out` mencionadas
- [ ] Outreach incluye opt-out obligatorio
- [ ] Plantilla "tratamiento_datos_prospeccion.md" mencionada

### A.7 Calidad

- [ ] Tests mencionados en CADA fase, no como anexo final
- [ ] mypy strict y tsc strict mencionados
- [ ] ruff + black para Python
- [ ] eslint + prettier para TS
- [ ] Cobertura objetivo mencionada: 70% packages, 50% apps

### A.8 Cosas que NO deben aparecer

- [ ] NO aparece Docker, Dockerfile, docker-compose
- [ ] NO aparece "we'll use the latest version of X" sin verificación
- [ ] NO aparece "TODO: implement later" sin issue de GitHub
- [ ] NO aparece código de ejemplo en el plan: el plan describe tareas, no implementa
- [ ] NO aparece "estimated time" inventado: si lo pone, que sea conservador
- [ ] NO menciona "Web Cafeína", "Webcafeina" sin tilde, ni variaciones

---

## B. REVISIÓN ESPECÍFICA DE FASE 0

### B.1 Subtareas mínimas de Fase 0

- [ ] Inicializar git + crear primer commit
- [ ] Conectar remoto GitHub
- [ ] Crear estructura completa de carpetas
- [ ] Generar `package.json` raíz con scripts orquestadores
- [ ] Generar `pnpm-workspace.yaml`
- [ ] Generar `turbo.json`
- [ ] Generar `.gitignore` completo (Python + Node + IDE)
- [ ] Generar `.env.example` con todas las variables documentadas (sin valores reales)
- [ ] Generar 20 archivos `.claude/agents/*.md` con frontmatter y contenido completo
- [ ] Generar 20 carpetas `.claude/skills/*/SKILL.md` con frontmatter y contenido completo
- [ ] Generar `CLAUDE.md` con memoria del proyecto
- [ ] Generar `STATE.md` con plantilla
- [ ] Generar `README.md` con setup local y descripción
- [ ] Generar `LICENSE` propietaria Webcafeína
- [ ] Generar `docs/decisiones.md` con plantilla ADR ligero
- [ ] Configurar pre-commit hooks (ruff, black, prettier, eslint, mypy, tsc)
- [ ] Commit inicial + push a `main`
- [ ] Crear rama `develop`
- [ ] Pausar y pedir revisión humana

### B.2 Lo que debe contener `CLAUDE.md`

- [ ] Identidad del proyecto (Webcafeína Migrator)
- [ ] Equipo y roles
- [ ] Stack técnico definitivo
- [ ] Convenciones de código
- [ ] Convenciones de commit (Conventional Commits)
- [ ] Política de branches
- [ ] Cómo añadir nuevo subagente o skill
- [ ] Paleta de marca completa
- [ ] Recordatorio "no Docker"
- [ ] Recordatorio "tests primero o tests inmediatos"

### B.3 Lo que debe contener `STATE.md`

- [ ] Sección "Fase actual"
- [ ] Sección "Tareas completadas"
- [ ] Sección "Tareas pendientes inmediatas"
- [ ] Sección "Bloqueos / decisiones humanas pendientes"
- [ ] Sección "Próxima sesión: por dónde empezar"
- [ ] Plantilla de cómo se actualiza

---

## C. REVISIÓN DE PRESUPUESTO DE TIEMPO

Si Claude Code te da estimaciones de tiempo, valida que sean realistas:

| Fase | Tiempo razonable (sesión Claude Code) |
|---|---|
| 0 | 30-60 min |
| 1 | 30-60 min |
| 2 | 2-4 horas (varias sesiones) |
| 3 | 2-3 horas |
| 4 | 1-2 horas |
| 5 | 2-3 horas |
| 6 | 2-3 horas |
| 7 | 1-2 horas |
| 8 | 3-5 horas (varias sesiones) |
| 9 | 2-3 horas |
| 10 | 2-3 horas |
| 11 | 1-2 horas |
| 12 | 2-3 horas |
| 13 | 2-3 horas |
| 14 | 2-3 horas |
| 15 | 1-2 horas |

Si te dice "Fase 2 en 30 minutos" → no es realista. Pide replanificación.

---

## D. CÓMO PEDIR AJUSTES AL PLAN

Si encuentras un problema, no apruebes y di algo así:

```
He revisado el plan y encuentro estos problemas:

1. [Problema concreto] — ej. "La Fase 2 estima 1 hora, no es realista para el transpilador"
2. [Problema concreto] — ej. "Falta mencionar la generación de Theme Styles en bricks-transpiler"
3. [Problema concreto]

Por favor:
- Replanifica corrigiendo estos puntos
- No empieces a ejecutar todavía
- Cuando esté listo, muéstrame el plan ajustado para volver a revisar
```

---

## E. SEÑALES DE QUE EL PLAN ESTÁ BIEN

- Es largo (80-150 tareas individuales en total)
- Cada fase termina con "commit + push + actualizar STATE.md + pausar para revisión humana"
- Menciona explícitamente prerequisitos humanos al inicio de cada fase
- Hay tareas de tests en cada fase de implementación
- Tiene referencias claras al prompt maestro (no inventa cosas nuevas)
- Las dependencias entre fases están explícitas

---

## F. SEÑALES DE QUE EL PLAN ESTÁ MAL

- Es corto (menos de 50 tareas) → falta detalle
- Las fases se ejecutan en cadena sin checkpoints humanos
- No menciona STATE.md ni CLAUDE.md
- Da estimaciones precisas que parecen optimistas
- Menciona tecnologías que NO están en el prompt (ej. "vamos a usar Vite", "usaremos Bun")
- Falta el cumplimiento legal en Fase 9
- Hay placeholders sin resolver
- Tests están como una fase final, no en cada fase
