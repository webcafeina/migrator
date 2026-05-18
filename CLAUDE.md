# CLAUDE.md — Memoria persistente del proyecto Webcafeína Migrator

> Este fichero se lee al inicio de cada sesión de Claude Code en este repositorio.
> Mantenerlo conciso, actualizado y veraz. Si una sección queda desactualizada, **arréglala antes de proceder**.

---

## 1. Identidad del proyecto

- **Nombre**: Webcafeína Migrator
- **Empresa**: Webcafeína S.L. (Cáceres, España, fundada 1997)
- **Equipo**: Webcafeína S.L. (9 personas en total). El proyecto se mantiene como un equipo único, sin roles individuales asignados nominalmente. Cualquier referencia operativa va a "Webcafeína" / "equipo" / "operador", nunca a personas concretas.
- **Tipo**: herramienta interna propietaria, no se distribuye fuera de Webcafeína
- **Misión**: automatizar dos procesos comerciales conectados — (a) prospección comercial de webs Wix/Hostinger/Webflow, (b) migración técnica a WordPress + Bricks Builder

> El nombre se escribe siempre **Webcafeína** (con tilde). Nunca "Web Cafeína", "Webcafeina" sin tilde, ni variaciones.

---

## 2. Restricciones no negociables

1. **NO Docker, bajo ninguna circunstancia.** Despliegue como procesos nativos gestionados por **systemd** (preferente) o Supervisor (fallback).
2. **Hosting destino**: WHM/cPanel con acceso SSH root. Stack instalable sin contenedores.
3. **Idiomas del producto** (UI dashboard y CLI): **español de España primario**, inglés secundario.
4. **Marca**: paleta y nombre estrictos (ver §3).
5. **Cumplimiento legal**: toda función que toque scraping prospectivo, outreach o datos personales debe incluir su capa de cumplimiento RGPD + LSSI-CE. **No es opcional.**
6. **No inventar versiones**. Si dudas, consulta el package registry oficial antes de fijar versión.
7. **Tests primero o tests inmediatos**. Cobertura objetivo: 70% en `packages/`, 50% en `apps/`.
8. **Verificación silenciosa**: ejecutar tests antes de afirmar que algo funciona. Sin narración previa.
9. **Sin TODOs huérfanos**: cada TODO debe enlazar un ID `WCM-NNN` de `ISSUES.md` (o issue GitHub cuando exista el remote).
10. **Secretos jamás en código**: todo a `.env`; `.env.example` es la referencia versionada.
11. **La carpeta docs/humanos/** es documentación operativa mantenida por el equipo humano. Claude Code no debe modificar, sobrescribir ni leer archivos de esa carpeta salvo petición explícita.

---

## 3. Marca y diseño

### Paleta obligatoria

Refactor 2026-05-14: se sustituyó la paleta marrón original por azul marino casi gris para mejorar contraste en tablas densas y dar look técnico (referencia visual: Linear / JetBrains dark). El acento lima se mantiene intacto.

| Uso | Hex |
|---|---|
| Background primario | `#0E1218` (azul marino casi negro) |
| Background secundario | `#1A222D` (azul marino oscuro) |
| Texto claro | `#E2E8F0` (gris claro azulado) |
| Detalle | `#3D4A5C` (azul gris medio — bordes, separadores) |
| Acento (lima) | `#B1F100` ← **solo para CTAs, numeración, iconos, subrayados, datos clave** |

### Tono visual

- Dashboard: **dark mode por defecto**, denso (tablas anchas, datos por encima de espaciado), sin gradientes innecesarios.
- Tipografía: sans-serif moderna (la concreta se decidirá en Fase 8; objetivo legibilidad de tablas densas).
- Componentes shadcn/ui customizados a la paleta. No usar los colores por defecto de Tailwind.

### Voz y copy

- Castellano de España, profesional, directo, sin frases hechas de marketing.
- Sin emojis en UI ni en docs internas.
- Errores de UI siempre explicativos + acción sugerida.

---

## 4. Stack técnico canónico

| Capa | Tecnología | Versión |
|---|---|---|
| Backend | Python | 3.12 |
| Framework API | FastAPI | última estable |
| Frontend | Next.js (App Router) + TypeScript | 15 / 5 |
| UI | shadcn/ui + Tailwind CSS | últimas |
| DB | PostgreSQL + pgvector | 16 / latest compat |
| Cola | Celery + Redis | últimas |
| Scraping | Playwright (Python) + Puppeteer sidecar (Node) | últimas |
| Anti-detección | playwright-stealth, fake-useragent | últimas |
| Proxies | Bright Data residencial (SDK oficial) | última |
| Captcha fallback | 2captcha API | última |
| Parser HTML | BeautifulSoup4 + lxml + trafilatura | últimas |
| Imágenes | Pillow + cwebp (binario) | últimas |
| PDF | WeasyPrint | última |
| ORM | SQLAlchemy 2.x + Alembic | últimas |
| CLI | Typer + Rich | últimas |
| WP | wordpress-xmlrpc + requests (REST) + paramiko (SSH→WP-CLI) | últimas |
| Email | Resend (SDK Python) | última |
| Observabilidad | Sentry + structlog + Logtail | últimas |
| Storage | Cloudflare R2 (boto3 compat) | n/a |
| Monorepo | pnpm workspaces + Turborepo | últimas |
| CI/CD | GitHub Actions | n/a |
| Tests | pytest + pytest-asyncio (Py) / Vitest + Playwright Test (TS) | últimas |
| Process mgr | systemd (preferente) / Supervisor (fallback) | n/a |
| Web server | Nginx (reverse proxy) | n/a |
| Builder destino | Bricks Builder | última |
| E-commerce | WooCommerce | última |
| Multilang | WPML (con flag para no instalarlo) | última |
| Forms | Gravity Forms | última |

---

## 5. Topología del monorepo

```
.claude/                     # Subagentes (20) y skills (20) de Claude Code
apps/
  api/                       # FastAPI backend
  dashboard/                 # Next.js 15 dashboard
  worker/                    # Celery workers
packages/
  bricks-transpiler/         # NÚCLEO: HTML/CSS → Bricks JSON
  scraper-core/              # Playwright wrapper, anti-detección
  wp-client/                 # REST + WP-CLI vía SSH
  shared-types/              # Tipos TS y Pydantic gemelos
  db-schema/                 # SQLAlchemy + Alembic
  ui/                        # Componentes shadcn compartidos
cli/                         # Typer CLI
infra/
  systemd/  nginx/  deploy/  whm-setup/
tests/
  unit/  integration/  e2e/
docs/
```

---

## 6. Reglas operativas para Claude (yo)

### Al iniciar cada sesión

1. Leer `CLAUDE.md` (este fichero) y `STATE.md`.
2. Identificar la fase actual y la siguiente tarea pendiente.
3. Antes de modificar código existente, **leer el archivo completo y los tests relacionados**.
4. Tras cada cambio significativo, **ejecutar tests**. Si fallan, no avanzar: arreglar.

### Al cerrar sesión

1. Actualizar `STATE.md` con:
   - Fase actual
   - Tareas completadas en la sesión
   - Tareas pendientes inmediatas
   - Bloqueos o decisiones humanas requeridas
2. Hacer commit con mensaje convencional. **No push automático** salvo instrucción explícita.

### Toma de decisiones

- **Reversibles, bajo impacto**: tomar decisión y documentar en `docs/decisiones.md` (ADR ligero).
- **Irreversibles o alto impacto**: **parar y preguntar** al humano (AskUserQuestion).

### Calidad de código

- Tipado estricto: `mypy --strict` en Python, `tsc --strict` en TS.
- Lint: `ruff` + `black` (Py), `eslint` + `prettier` (TS).
- Commits convencionales: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `perf`, `ci`.
- Logs: structlog (JSON en prod, plano en dev). **Nada de `print()`**.
- Errores tipados: cada subagente lanza excepciones de su jerarquía (`ProspectorError`, `BricksTranspileError`, etc.) capturables por el orchestrator.
- **Sin abstracciones prematuras**: tres líneas similares ≻ una abstracción inventada para un caso futuro.
- **Sin manejos de error para escenarios imposibles**: confiar en garantías internas; validar solo en fronteras (input usuario, APIs externas).

### Estilo de respuesta al usuario

- Castellano de España, conciso, sin emojis.
- Antes de la primera llamada a tool, **una frase** sobre qué voy a hacer.
- Updates breves en hitos: hallazgo, cambio de rumbo, bloqueo.
- Sin narración del proceso interno.

### Paridad funcional API ↔ CLI ↔ UI (obligatoria)

Cada nueva capacidad debe verificarse en las **tres** capas antes de marcarla completa:

1. **API endpoint** funcional con tests.
2. **CLI command** equivalente bajo `cli/src/wcm_cli/commands/`. Excepciones legítimas: webhooks, `/health`, `/metrics`, `/ready` (técnicos, no de usuario).
3. **UI dashboard** que lo dispare o muestre.

**Reglas duras:**

- **Prohibido** commitear botones disabled con copy tipo `"Implementación en Fase N"` o `"Endpoint pendiente"` apuntando a fases que ya pasaron. O se implementa, o se omite el botón, o se documenta en `ISSUES.md` como `WCM-NNN` con fecha objetivo concreta (no nombre de fase).
- **Prohibido** mencionar herramientas inexistentes en microcopy de UI (caso `wcm users` en OperationRunbook antes de v0.13.0 — doble engaño: prometía CLI inexistente + endpoint expuesto sin acceso).
- **Tras commit del bloque backend** de cualquier sprint: micro-audit obligatoria. Grep `apps/dashboard/src` y `cli/src/wcm_cli` por el recurso nuevo. Si falta, **añadir bloques UI + CLI al mismo sprint** o crear `WCM-NNN` explícito.
- **Antes de marcar una task como completed**: pregunta interna — *"¿este endpoint tiene botón visible? ¿comando CLI? Si no, ¿hay tracking?"*.
- **Auditorías de paridad completas** cuando el usuario las pida o cada 3-5 releases: matriz `Capacidad | API | CLI | UI` con GAPs marcados P0/P1/P2. P0 (vaporware) se cierran antes del siguiente release minor.

Causa raíz documentada: múltiples sprints (v0.12.0, v0.12.1, v0.13.0) se han gastado limpiando vaporwares acumulados ("Fase 7", "Fase 10", "Fase 14", `wcm users` inexistente). La auditoría sistemática los previene.

---

## 7. Flujo de migración (resumen)

```
1. Operador crea proyecto (CLI o dashboard)
2. orchestrator → scraper-origin (con builder ya detectado por fingerprinter)
3. content-extractor normaliza HTML → bloques semánticos
4. seo-preserver extrae meta/sitemap/hreflang
5. asset-optimizer descarga + optimiza imágenes/fonts
6. multilang-handler detecta idiomas
7. bricks-transpiler genera bricks_pages JSON
8. wp-deployer provisiona WP + instala plugins + importa páginas
9. woo-migrator (si has_ecommerce)
10. wpml-configurator (si is_multilang)
11. forms-rebuilder
12. visual-diff compara origen vs destino
13. qa-runner ejecuta batería de QA
14. checklist-generator compila tareas residuales
15. clickup-syncer crea tarea+subtareas en ClickUp
16. resend-notifier avisa al operador
```

## 8. Flujo de prospección (resumen)

```
1. Operador lanza campaña (sector + región + target)
2. prospector descubre URLs (Maps + directorios + dorks)
3. fingerprinter clasifica builder por URL
4. enricher añade contacto + datos empresa
5. outreach-composer prepara secuencia personalizada
6. Operador revisa, aprueba, exporta CSV o envía manualmente
```

> **El sistema nunca envía outreach automáticamente.** Siempre revisión humana previa.

---

## 9. Datos conocidos del workspace ClickUp

- Team ID: `20483773`
- Lista "Microtareas" (default): `900102088242`
- Sin assignee individual por defecto: residual_tasks se crean unassigned. El equipo Webcafeína decide en cada caso quién la toma.

---

## 10. Anti-detección en scraping prospectivo

Capas, configurables por entorno (ADR-017):

1. **Proxy layered**: NoProxy (dev) → Webshare free (10 IPs + 1GB/mes) → ScraperAPI free (5k calls/mes) → Bright Data (paid premium). `build_default_rotator()` elige automáticamente según env vars.
2. `playwright-stealth` activado siempre
3. UA rotation con pool curado estático + opcional `fake-useragent`
4. Rate limit: 1 req cada 3–8s aleatorios por dominio
5. Respeto de `robots.txt` (en prospección sí; en migración no, porque hay consentimiento)
6. Cache Redis TTL 7 días (o `InMemoryCache` en dev/tests)
7. Detección de captcha → ScraperAPI lo gestiona; 2captcha como fallback raro
8. Cooldown: 3 × `403/429/503` → pausa 24 h por dominio
9. Logs detallados para ajustar estrategia

---

## 11. Cumplimiento legal — implementación obligatoria

Vive en `apps/api/legal/`. Todo email de outreach debe incluir:

- Identificación: Webcafeína, CIF, dirección, email, web
- Motivo del contacto
- Base jurídica: interés legítimo (art. 6.1.f RGPD)
- Mecanismo de baja funcional
- Link a política de privacidad

Funciones obligatorias:

- `record_consent(lead_id, channel, evidence)`
- `process_opt_out(email)` — elimina lead + registra timestamp opt-out

---

## 12. Cómo añadir subagente o skill

1. Crear `.claude/agents/<nombre>.md` o `.claude/skills/<nombre>/SKILL.md` con frontmatter Anthropic.
2. Documentar contrato, dependencias, casos límite.
3. Añadir variables al `.env.example` si introduce nuevas.
4. Registrar en `STATE.md` y `docs/arquitectura.md` si afecta al flujo.

---

## 13. Criterios de éxito del MVP

1. `webcafeina-migrator new --source URL --client NAME` → WP+Bricks funcional en staging en < 90 min para una web Wix demo.
2. Visual diff ≥ 0.85 en home + ≥ 80% de páginas internas.
3. Checklist residual ejecutable por humano en < 4 h para web corporativa de 10 páginas.
4. Prospección: 50 leads cualificados con 80%+ fingerprint correcto en < 1 h.
5. Dashboard cubre todo el flujo sin tocar CLI.
6. QA pasa sin errores críticos.
7. Despliegue WHM via scripts sin intervención manual más allá de `.env`.

---

## 14. Referencias rápidas

- Estado actual: [`STATE.md`](./STATE.md)
- Issues abiertos: [`ISSUES.md`](./ISSUES.md)
- Decisiones arquitectónicas: [`docs/decisiones.md`](./docs/decisiones.md)
- Arquitectura: [`docs/arquitectura.md`](./docs/arquitectura.md)
- Despliegue: [`docs/despliegue.md`](./docs/despliegue.md)
- Playbook operativo: [`docs/playbook-operativo.md`](./docs/playbook-operativo.md)
