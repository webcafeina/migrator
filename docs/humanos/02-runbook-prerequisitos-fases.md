# 02 — RUNBOOK DE PREREQUISITOS POR FASE

> Para cada fase, lo que necesitas tener listo ANTES de iniciar esa sesión con Claude Code. Si algo falta, Claude Code se va a bloquear o va a generar código basado en suposiciones que después tendrás que rehacer.

---

## FASE 0 — Bootstrap

### Prerequisitos humanos

| # | Tarea | Cómo |
|---|---|---|
| 1 | Repo GitHub `webcafeina/webcafeina-migrator` creado | gh repo create webcafeina/webcafeina-migrator --private |
| 2 | SSH key configurada en GitHub | Probar `ssh -T git@github.com` |
| 3 | Carpeta local vacía creada | `mkdir ~/proyectos/webcafeina-migrator && cd $_` |
| 4 | Git config global con nombre y email correcto | `git config --global user.name "Tu Nombre"` |
| 5 | Antigravity abierto en esa carpeta | — |

### Qué obtendrás al final de Fase 0

- Estructura completa de carpetas
- Todos los `.claude/agents/*.md` generados
- Todos los `.claude/skills/*/SKILL.md` generados
- `CLAUDE.md` con memoria del proyecto
- `STATE.md` con estado actual
- `README.md` inicial
- `.gitignore`, `.env.example`, `package.json` raíz, `pnpm-workspace.yaml`, `turbo.json`
- `docs/decisiones.md` vacío con plantilla ADR
- Commit inicial y push a `main`

### Qué revisas al terminar

- Que NO haya placeholders sin resolver (`TODO`, `XXX`, `FIXME` sin issue asociado)
- Que cada agente tenga descripción clara de su responsabilidad
- Que cada skill tenga ejemplos concretos
- Que `STATE.md` refleje "Fase 0 completada, próxima Fase 1"

### Bloqueos comunes

- "No puede hacer push": faltó SSH key o repo no creado
- "No tengo permisos": directorio creado con sudo, hazlo como usuario normal
- "El plan incluye Docker": ALTO. Recházalo y recuerda la restricción

---

## FASE 1 — DB y modelos

### Prerequisitos humanos

| # | Tarea | Cómo |
|---|---|---|
| 1 | PostgreSQL 16 local corriendo | `pg_isready` debe devolver "accepting connections" |
| 2 | Extensión `pgvector` instalada localmente | `psql -c "CREATE EXTENSION IF NOT EXISTS vector;"` |
| 3 | Usuario y DB locales creados | `webcafeina_migrator_dev`, usuario `webcafeina`, password en `.env.local` |
| 4 | Redis local corriendo | `redis-cli ping` → PONG |

### Qué obtendrás

- `packages/db-schema/` con todos los modelos SQLAlchemy
- Migración Alembic inicial
- Seeds opcionales para desarrollo
- `packages/shared-types/` con tipos TS gemelos
- Tests unitarios de modelos

### Qué revisas

- Que los nombres de tablas y campos coincidan con lo definido en sección 5 del prompt maestro
- Que las relaciones tengan los `ON DELETE` correctos (CASCADE solo donde tenga sentido)
- Que haya índices en campos de búsqueda frecuente: `leads.url`, `projects.source_url`, `assets.hash`
- Que `pgvector` esté usado en `leads` para embeddings

### Bloqueos comunes

- "No conecta a Postgres": revisa `pg_hba.conf` permita conexiones locales con password
- "pgvector no existe": no instalaste la extensión en el sistema antes de en la DB

---

## FASE 2 — Bricks transpiler (CRÍTICA)

### Prerequisitos humanos

| # | Tarea | Cómo |
|---|---|---|
| 1 | WordPress sandbox instalado con Bricks activado | Subdominio en tu WHM |
| 2 | Export JSON de Bricks de página con variedad de elementos | Bricks → Templates → Export |
| 3 | Export JSON de Bricks con Theme Styles configurados | Bricks → Settings → Theme Styles → Export |
| 4 | Documentación oficial Bricks consultada | bricksbuilder.io/docs/ |
| 5 | Al menos 5 ejemplos de webs Wix/Hostinger/Webflow URLs reales como fixtures | Lista en `tests/fixtures/source-urls.txt` |

### Qué obtendrás

- `packages/bricks-transpiler/` con:
  - Tipos TypeScript del schema Bricks
  - Generador de IDs únicos
  - Transformadores por bloque (heading, text, image, gallery, button, section, container, form, etc.)
  - Generador de Theme Styles desde CSS origen
  - Función principal `transpile(contentBlocks, themeContext) → bricksJson`
  - Tests con fixtures: dado HTML X, esperado JSON Y

### Qué revisas

- **Importas el JSON generado a tu sandbox Bricks** y compruebas que se renderiza correctamente
- Que cada tipo de bloque tiene su transformador y test
- Cobertura mínima 80% en este paquete (es el más crítico)
- Que los IDs generados son únicos por proyecto (no colisionan entre páginas)

### Bloqueos comunes

- "El JSON importa pero se ve mal": el schema no está bien inferido, vuelve a exportar de Bricks una página más simple y compárala
- "Bricks no acepta el JSON": versión de Bricks diferente entre fixture y sandbox
- "Las variables CSS no aplican": Theme Styles tiene que importarse por separado, no en el JSON de página

### Decisión irreversible

El formato del Bricks JSON output queda fijado aquí. Cambiarlo después implica revisar todas las webs migradas. Revisa con calma antes de cerrar la fase.

---

## FASE 3 — Scraper core

### Prerequisitos humanos

| # | Tarea | Cómo |
|---|---|---|
| 1 | Playwright instalado con browsers | `pnpm exec playwright install chromium` |
| 2 | Node sidecar con Puppeteer instalado | Parte del bootstrap, verificar |
| 3 | Lista de URLs de prueba REALES por constructor | 5+ por cada uno: Wix, Hostinger AI, Webflow |
| 4 | Permiso explícito (mismo si son demos públicas) | Documentado en `tests/fixtures/scraping-permissions.md` |
| 5 | Espacio en disco para HTML + screenshots | 5GB libres mínimo |

### Qué obtendrás

- `packages/scraper-core/` con Playwright wrapper
- Sidecar Node específico para Webflow
- Skills `wix-extraction`, `hostinger-ai-extraction`, `webflow-extraction` completas
- Tests que scrapean fixtures reales y comparan output con expected

### Qué revisas

- Que el HTML extraído sea HTML hidratado (no el shell vacío de un SPA)
- Que se descarguen todas las imágenes referenciadas
- Que screenshots full-page no estén cortados
- Que el rate limiting funcione (no martillea servidores)
- Que respete `robots.txt` cuando proceda

### Bloqueos comunes

- "Playwright timeout": aumenta timeout y revisa si necesitas esperar `networkidle`
- "Wix devuelve página de error": detección anti-bot. Activa `playwright-stealth`
- "Webflow falla la extracción de animaciones": esperado, no es objetivo del MVP. Documenta como tarea residual

---

## FASE 4 — WP client

### Prerequisitos humanos

| # | Tarea | Cómo |
|---|---|---|
| 1 | WordPress sandbox accesible vía REST | `https://sandbox-migrator.webcafeina.com/wp-json/wp/v2/` debe responder |
| 2 | Application Password creado para usuario admin | WP Users → Edit → Application Passwords |
| 3 | SSH acceso al servidor donde está sandbox WP (para WP-CLI) | Verificar `ssh user@server "wp --info"` |
| 4 | Credenciales en `.env.local` | `WP_URL`, `WP_USER`, `WP_APP_PASSWORD`, `WP_SSH_HOST`, `WP_SSH_USER` |

### Qué obtendrás

- `packages/wp-client/` con cliente REST + CLI SSH
- Tests de operaciones CRUD contra sandbox real
- Skills `wp-rest-bulk`, `wpcli-ssh`

### Qué revisas

- Que se puedan crear 100 posts en menos de 30 segundos (test de bulk)
- Que las imágenes se suban correctamente y se vinculen a posts
- Que ACF fields se asignen si están instalados
- Que rollback funcione si falla a mitad de importación

### Bloqueos comunes

- "401 unauthorized": Application Password mal copiado (sin espacios)
- "SSH connection refused": puerto cambiado en WHM, usar puerto correcto
- "WP-CLI no encontrado": no está instalado en el sandbox, instalarlo

---

## FASE 5 — API backend

### Prerequisitos humanos

| # | Tarea | Cómo |
|---|---|---|
| 1 | Fases 1-4 completadas y verdes | Verificar tests |
| 2 | Secret JWT generado | `openssl rand -hex 32` |
| 3 | Credenciales SMTP para auth opcional | Solo si vas a usar magic links |

### Qué obtendrás

- `apps/api/` con FastAPI, endpoints, auth JWT, integración Celery
- OpenAPI auto-generado en `/docs`
- Tests de endpoints

### Qué revisas

- `/docs` accesible y endpoints documentados
- Health check funciona: `/health` y `/health/db`
- Auth flujo completo: login → token → request autenticado
- Rate limiting en endpoints públicos

---

## FASE 6 — Worker y subagentes operativos

### Prerequisitos humanos

| # | Tarea | Cómo |
|---|---|---|
| 1 | Redis local funcional | Mismo de Fase 1 |
| 2 | Celery configurado | Generado en Fase 5 |
| 3 | Una URL de prueba "barata" para dry-run e2e | Una web Wix simple |

### Qué obtendrás

- `apps/worker/` con tasks Celery por cada subagente
- Pipeline completo ejecutable en dry-run
- Logs estructurados

### Qué revisas

- Lanza un dry-run completo: el pipeline termina sin errores
- Cada fase del pipeline emite eventos a la BD
- Si una fase falla, las siguientes no se ejecutan y el error queda registrado

### Bloqueos comunes

- "Celery no recoge tasks": revisa que el worker esté ejecutándose con el queue correcto
- "Tasks se cuelan": revisa imports circulares y configuración Celery
- "Memory leak en Playwright": añadir `browser.close()` en finally

---

## FASE 7 — CLI

### Prerequisitos humanos

| # | Tarea | Cómo |
|---|---|---|
| 1 | API levantada localmente | `uvicorn ...` corriendo |
| 2 | Worker levantado | `celery worker ...` corriendo |

### Qué obtendrás

- `cli/` con Typer, todos los comandos del prompt
- Tests de CLI con CliRunner

### Qué revisas

- Cada comando del listado funciona
- `--help` da info clara en cada comando
- Output con Rich es legible

---

## FASE 8 — Dashboard

### Prerequisitos humanos

| # | Tarea | Cómo |
|---|---|---|
| 1 | API estable | Endpoints de Fase 5 funcionando |
| 2 | Decidir si dashboard tiene auth propia o usa la API | Recomendado: usa la API |
| 3 | Paleta Webcafeína documentada en `tailwind.config.ts` | Generado en Fase 0 |

### Qué obtendrás

- `apps/dashboard/` Next.js 15 con todas las páginas
- shadcn/ui customizado con paleta Webcafeína
- Conexión a API real, no mocks

### Qué revisas

- Dark mode por defecto, paleta correcta
- Cada página listada en el prompt está implementada
- Login funciona
- Datos en tiempo real (no estáticos)
- Mobile responsive aceptable

---

## FASE 9 — Módulo prospección

### Prerequisitos humanos

| # | Tarea | Cómo |
|---|---|---|
| 1 | Google Places API key obtenida | Google Cloud Console |
| 2 | Lista de sectores objetivo | Ej. restauración, dental, formación, ecommerce nicho |
| 3 | Lista de directorios sectoriales relevantes | Documentar URLs y estructura |
| 4 | Texto base para registros RGPD | Tu asesor legal o plantilla AEPD |
| 5 | Cuenta Brevo o Lemlist creada | Para envío manual posterior |
| 6 | Política de privacidad actualizada en webcafeina.com | Con mención al tratamiento de leads B2B |

### Qué obtendrás

- Subagentes `prospector`, `enricher`, `outreach-composer` operativos
- Skill `gdpr-compliance` con plantillas
- Endpoint de opt-out funcional con URL pública
- Registro de actividades de tratamiento

### Qué revisas

- Lanza prospección de prueba: 10 leads en sector restauración Andalucía
- Verifica que detecta correctamente builders
- Verifica que outreach incluye TODOS los elementos legales requeridos
- Verifica que opt-out funciona

### Atención legal

Antes de empezar prospección real:
- Consulta con tu asesor legal sobre la base jurídica de interés legítimo
- Inscribe el tratamiento en tu registro RGPD (art. 30)
- Actualiza la política de privacidad
- Configura un email dedicado para opt-outs

---

## FASE 10 — Integraciones externas

### Prerequisitos humanos

| # | Tarea | Cómo |
|---|---|---|
| 1 | ClickUp API Token + IDs de listas | Token + Team ID `20483773` + Microtareas `900102088242` |
| 2 | Resend API key + dominio verificado | resend.com |
| 3 | Sentry DSN para api y dashboard | Dos proyectos en Sentry |
| 4 | Cloudflare R2 credenciales | Access Key + Secret + endpoint URL |
| 5 | Bright Data SDK credentials | Customer ID + zone password |
| 6 | 2captcha API key | 2captcha.com |

### Qué obtendrás

- Skills `clickup-task-creator`, `resend-notifier`, `r2-uploader`, `proxy-rotation`, `captcha-handling`
- Configuración de Sentry en api y dashboard
- Smoke tests de cada integración

### Qué revisas

- Lanza una notificación de prueba → llega a tu email
- Crea una tarea de prueba en ClickUp → aparece en la lista correcta
- Sube un archivo a R2 → es accesible por URL pública
- Lanza un scraping con proxy → la IP es residencial española
- Resuelve un captcha manual → 2captcha responde

---

## FASE 11 — Observabilidad

### Prerequisitos humanos

| # | Tarea | Cómo |
|---|---|---|
| 1 | Logtail source creado | betterstack.com → Logs → Create source |
| 2 | Email destino de alertas confirmado | nacho@webcafeina.com |
| 3 | Decidir niveles de severidad que disparan email | Default: ERROR y CRITICAL |

### Qué obtendrás

- Logs estructurados a Logtail
- Dashboard de errores en la app
- Notificaciones por email automáticas

### Qué revisas

- Provoca un error en dev → aparece en Sentry y en Logtail
- Provoca un error CRITICAL → llega email
- El panel `/errors` del dashboard muestra los últimos 100

---

## FASE 12 — Infra/Deploy

### Prerequisitos humanos

| # | Tarea | Cómo |
|---|---|---|
| 1 | Acceso SSH root al WHM confirmado | `ssh root@tu-whm` |
| 2 | Subdominios apuntados | DNS de staging y producción apuntando al servidor |
| 3 | Decidir distro y versión exacta del servidor | AlmaLinux 9 / CloudLinux 8 / etc. |
| 4 | Espacio en disco | Mínimo 50GB libres |
| 5 | Backup del servidor reciente | Snapshot WHM o backup manual |

### Qué obtendrás

- Scripts en `infra/whm-setup/` numerados del 01 al 10
- Systemd unit files
- Configs Nginx
- GitHub Actions workflows
- Documentación de despliegue

### Qué revisas

- Ejecuta los scripts en staging primero
- Verifica con `systemctl status` que todos los servicios están active
- Accede al dashboard de staging desde fuera
- Lanza una migración pequeña en staging para validar end-to-end

### Decisiones irreversibles

- Estructura de directorios en `/opt/webcafeina-migrator/` — difícil cambiar después
- Usuario del sistema que corre la app — difícil cambiar después
- Estrategia de logs en disco vs solo Logtail — afecta storage

---

## FASE 13 — Tests e2e

### Prerequisitos humanos

| # | Tarea | Cómo |
|---|---|---|
| 1 | Sandbox WP limpio y dedicado a tests e2e | Distinto del sandbox de desarrollo |
| 2 | Web origen real con permiso explícito | Una web Webcafeína antigua sirve |
| 3 | CI con runner suficientemente potente | GitHub Actions free o self-hosted |

### Qué obtendrás

- Suite Playwright Test contra dashboard
- Suite pytest-asyncio pipeline completo en sandbox
- Workflow CI corriendo tests en cada PR

---

## FASE 14 — Documentación

### Prerequisitos humanos

Solo tu tiempo. Esto lo hace mayormente Claude Code pero requiere validación tuya.

### Qué obtendrás

- `docs/arquitectura.md` con diagramas Mermaid
- `docs/prospeccion.md` operacional
- `docs/migracion.md` operacional
- `docs/despliegue.md`
- `docs/playbook-operativo.md` para tu equipo
- `docs/troubleshooting.md`

### Qué revisas

- Que un humano del equipo pueda operar el sistema solo con la documentación
- Que los diagramas reflejan la realidad del código

---

## FASE 15 — Hardening

### Prerequisitos humanos

| # | Tarea | Cómo |
|---|---|---|
| 1 | Decidir política de rate limits | Ej. 60 req/min por IP en endpoints públicos |
| 2 | Decidir si añades 2FA al dashboard | Recomendado: sí |
| 3 | Audit log retention policy | Ej. 1 año en BD, después archivar a R2 |

### Qué obtendrás

- Rate limits implementados
- CSRF protection
- Dependencias auditadas con `pip-audit` y `pnpm audit`
- Secret rotation documentado
- 2FA opcional

### Qué revisas

- Lanza un escaneo de seguridad básico con OWASP ZAP en staging
- Revisa que no haya secretos en el código (`gitleaks`)
- Revisa que CORS esté bien configurado

---

## DESPUÉS DE FASE 15 — PILOTO

No es una fase de Claude Code. Es tuya.

| # | Tarea |
|---|---|
| 1 | Elegir web interna Webcafeína a migrar como piloto |
| 2 | Ejecutar migración completa con la herramienta |
| 3 | Medir tiempos contra criterios de éxito |
| 4 | Ejecutar tareas residuales y medir tiempo humano |
| 5 | Comparar resultado visual y funcional con original |
| 6 | Documentar fricciones en `docs/aprendizajes-piloto.md` |
| 7 | Decidir qué iterar antes de aceptar cliente real |
