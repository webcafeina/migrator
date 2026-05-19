# 05 — GLOSARIO Y REFERENCIA RÁPIDA

> Todos los términos, IDs, comandos, rutas y referencias que vas a necesitar tener a mano durante la construcción y operación.

---

## A. GLOSARIO DEL PROYECTO

| Término | Definición |
|---|---|
| **Webcafeína Migrator** | Nombre del producto interno. Nunca "Web Cafeína" ni variantes |
| **Migrator** | Forma corta aceptable internamente |
| **Builder origen** | Constructor de webs del que se migra: Wix, Hostinger AI Builder, Webflow |
| **Builder destino** | WordPress + Bricks Builder |
| **Fingerprinting** | Identificación automática del builder de una web |
| **Lead** | URL candidata para outreach, identificada por prospección |
| **Proyecto** | Migración activa de una web concreta a WordPress |
| **Bricks JSON** | Formato nativo de Bricks Builder para representar páginas |
| **Theme Styles** | Variables globales en Bricks (colores, fuentes, espaciados) |
| **Bloque** | Unidad mínima de contenido normalizado (`hero`, `text`, `image`, etc.) antes del transpilador |
| **Tarea residual** | Tarea de migración que el sistema no puede automatizar y queda en checklist humano |
| **Checklist residual** | Documento Markdown + PDF generado al final de cada migración con tareas humanas |
| **Visual diff** | Comparación pixel a pixel entre web origen y migrada |
| **Director de calidad** | Nombre interno del sistema de revisión orquestador + 25 subrevisiones |
| **Sandbox** | Instalación WordPress de pruebas usada durante construcción |
| **Outreach** | Secuencia de contactos comerciales generada por la herramienta |
| **Pipeline** | Cadena de subagentes que ejecutan una migración completa |
| **Dry-run** | Ejecución sin efectos secundarios (no escribe en BD destino) |

---

## B. NOMBRES E IDS CONOCIDOS

### B.1 ClickUp Webcafeína

| Recurso | ID / Valor |
|---|---|
| Workspace Team ID | `20483773` |
| Usuario Nacho | `32553086` |
| Lista Microtareas | `900102088242` |
| Lista Comercial | `900102088262` |
| Lista Sprint 10 | `901216772424` |

### B.2 Dominio y subdominios sugeridos

| Subdominio | Uso |
|---|---|
| `migrator.webcafeina.com` | Dashboard producción |
| `migrator-staging.webcafeina.com` | Dashboard staging |
| `api.migrator.webcafeina.com` | API producción |
| `sandbox-migrator.webcafeina.com` | WP sandbox para tests |

### B.3 Repositorios GitHub

| Repo | Visibilidad | Propósito |
|---|---|---|
| `webcafeina/webcafeina-migrator` | Privado | Código principal |
| `webcafeina/webcafeina-migrator-deploy` | Privado | Configs de despliegue sensibles (opcional, separado) |

---

## C. PALETA DE MARCA WEBCAFEÍNA — REFERENCIA OBLIGATORIA

```css
:root {
  --wc-bg-primary: #171009;
  --wc-bg-secondary: #2B1A0E;
  --wc-text-light: #F2E8D2;
  --wc-detail-brown: #5A3519;
  --wc-accent-lime: #B1F100;
}
```

**Reglas de uso del acento lima** `#B1F100`:
- CTAs principales
- Numeración importante
- Iconos clave
- Subrayados de enlaces hover
- Datos numéricos destacados (KPIs)
- **NUNCA** como background grande
- **NUNCA** para texto largo
- Sí para resaltar palabras puntuales

---

## D. COMANDOS DE REFERENCIA RÁPIDA

### D.1 Desarrollo local

```bash
# Setup inicial (una vez)
pnpm install
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head

# Levantar todo en dev
pnpm dev:all                    # Levanta api, dashboard, worker

# O por separado
pnpm dev:api                    # FastAPI con reload
pnpm dev:dashboard              # Next.js con turbopack
pnpm dev:worker                 # Celery worker

# Tests
pnpm test                       # Tests JS/TS
pytest                          # Tests Python
pytest --cov                    # Con cobertura

# Lint y format
pnpm lint
pnpm format
ruff check .
black .
mypy .
```

### D.2 Base de datos

```bash
# Nueva migración
alembic revision --autogenerate -m "descripcion"

# Aplicar
alembic upgrade head

# Rollback
alembic downgrade -1

# Reset completo (DEV)
dropdb webcafeina_migrator_dev
createdb webcafeina_migrator_dev
psql -d webcafeina_migrator_dev -c "CREATE EXTENSION vector;"
alembic upgrade head
```

### D.3 CLI del migrator

```bash
webcafeina-migrator setup
webcafeina-migrator prospect --sector "restauracion" --region "Andalucia" --target 50
webcafeina-migrator leads list
webcafeina-migrator leads show <id>
webcafeina-migrator new --source https://ejemplo.com --client "Cliente S.L."
webcafeina-migrator project status <id>
webcafeina-migrator project resume <id>
webcafeina-migrator project export-checklist <id>
webcafeina-migrator deploy --env staging
webcafeina-migrator deploy --env prod
webcafeina-migrator doctor
```

### D.4 Despliegue WHM (orden estricto)

```bash
# En el servidor WHM, como root
cd /opt/webcafeina-migrator
git pull origin main
sudo ./infra/whm-setup/01-system-deps.sh        # Solo primera vez
sudo ./infra/whm-setup/02-postgres-setup.sh     # Solo primera vez
sudo ./infra/whm-setup/03-app-user.sh           # Solo primera vez
./infra/whm-setup/05-install-deps.sh            # Cada release
./infra/whm-setup/06-migrations.sh              # Cada release con cambios DB
sudo systemctl restart webcafeina-api
sudo systemctl restart webcafeina-worker
sudo systemctl restart webcafeina-dashboard
./infra/whm-setup/10-smoke-test.sh              # Verificación post-deploy
```

### D.5 Git workflow

```bash
# Empezar nueva fase
git checkout develop
git pull
git checkout -b feature/fase-X-nombre

# Tras completar fase
git add .
git commit -m "feat(fase-X): descripcion conventional commit"
git push -u origin feature/fase-X-nombre
gh pr create --base develop --title "Fase X: Nombre" --body "..."

# Tras revisión y merge
git checkout develop
git pull
git branch -d feature/fase-X-nombre
```

### D.6 Diagnóstico rápido

```bash
# ¿Servicios levantados?
systemctl status webcafeina-api webcafeina-worker webcafeina-dashboard

# ¿Logs recientes?
journalctl -u webcafeina-api -n 100 --no-pager
journalctl -u webcafeina-worker -n 100 --no-pager

# ¿Conexión a DB?
psql -h localhost -U webcafeina -d webcafeina_migrator -c "SELECT 1"

# ¿Redis responde?
redis-cli ping

# ¿API responde?
curl https://api.migrator.webcafeina.com/health

# ¿Tasks en cola?
celery -A apps.worker inspect active
```

---

## E. ESTRUCTURA DE VARIABLES DE ENTORNO

`.env.example` (sin valores reales):

```env
# Entorno
ENV=development                                 # development | staging | production
DEBUG=true

# Base de datos
DATABASE_URL=postgresql://webcafeina:CHANGE@localhost:5432/webcafeina_migrator_dev
REDIS_URL=redis://localhost:6379/0

# Auth
JWT_SECRET=CHANGE-generate-with-openssl-rand-hex-32
JWT_ALGORITHM=HS256
JWT_EXPIRY_HOURS=24

# WordPress sandbox / target
WP_SANDBOX_URL=https://sandbox-migrator.webcafeina.com
WP_SANDBOX_USER=admin
WP_SANDBOX_APP_PASSWORD=CHANGE
WP_SSH_HOST=
WP_SSH_USER=
WP_SSH_KEY_PATH=

# Cloudflare R2
R2_ACCESS_KEY_ID=CHANGE
R2_SECRET_ACCESS_KEY=CHANGE
R2_BUCKET_NAME=webcafeina-migrator-assets
R2_ENDPOINT_URL=
R2_PUBLIC_URL=

# Bright Data
BRIGHTDATA_CUSTOMER_ID=CHANGE
BRIGHTDATA_ZONE=residential
BRIGHTDATA_PASSWORD=CHANGE

# 2captcha
TWOCAPTCHA_API_KEY=CHANGE

# Google APIs
GOOGLE_PLACES_API_KEY=CHANGE

# ClickUp
CLICKUP_API_TOKEN=CHANGE
CLICKUP_TEAM_ID=20483773
CLICKUP_LIST_MICROTAREAS=900102088242
CLICKUP_LIST_COMERCIAL=900102088262

# Resend
RESEND_API_KEY=CHANGE
RESEND_FROM_EMAIL=migrator@webcafeina.com
NOTIFICATIONS_TO_EMAIL=nacho@webcafeina.com

# Sentry
SENTRY_DSN_API=CHANGE
SENTRY_DSN_DASHBOARD=CHANGE

# Logtail
LOGTAIL_TOKEN=CHANGE

# GitHub (para CI/CD si aplica)
GITHUB_TOKEN=CHANGE

# WPML license
WPML_API_KEY=CHANGE

# Bricks license
BRICKS_LICENSE_KEY=CHANGE

# Gravity Forms license
GRAVITY_FORMS_LICENSE=CHANGE
```

---

## F. RUTAS EN EL SERVIDOR (PRODUCCIÓN)

```
/opt/webcafeina-migrator/                       # Raíz del proyecto
├── .env                                        # Variables sensibles (chmod 600)
├── apps/
├── packages/
├── cli/
└── ...

/etc/systemd/system/
├── webcafeina-api.service
├── webcafeina-worker.service
├── webcafeina-beat.service
└── webcafeina-dashboard.service

/etc/nginx/conf.d/
├── migrator.webcafeina.com.conf
└── api.migrator.webcafeina.com.conf

/var/log/webcafeina-migrator/                   # Si decides logs en disco además de Logtail
├── api.log
├── worker.log
└── dashboard.log

/home/webcafeina/                               # Usuario del sistema
├── .ssh/
└── ...
```

---

## G. RESPONSABLES POR ÁREA

| Área | Responsable principal | Backup |
|---|---|---|
| Producto y decisiones de negocio | Nacho | Adrián |
| Desarrollo backend Python | Álvaro | Samuel |
| Desarrollo frontend Next.js | Samuel | Álvaro |
| Despliegue WHM y DevOps | Álvaro | Nacho |
| Pruebas de migración real | Adrián | Nacho |
| Outreach y prospección | Nacho | Adrián |
| Atención cliente piloto | Nacho | Adrián |

---

## H. ENLACES ÚTILES

| Recurso | URL |
|---|---|
| Documentación Bricks Builder | https://bricksbuilder.io/docs/ |
| API REST WordPress | https://developer.wordpress.org/rest-api/ |
| WP-CLI | https://wp-cli.org/ |
| Playwright Python | https://playwright.dev/python/ |
| FastAPI | https://fastapi.tiangolo.com/ |
| Next.js 15 | https://nextjs.org/docs |
| shadcn/ui | https://ui.shadcn.com/ |
| Celery | https://docs.celeryq.dev/ |
| Bright Data docs | https://docs.brightdata.com/ |
| 2captcha API | https://2captcha.com/api-docs |
| Resend | https://resend.com/docs |
| ClickUp API | https://clickup.com/api |
| WPML API | https://wpml.org/documentation/ |
| AEPD (RGPD) | https://www.aepd.es/ |
| Anthropic Claude Code | https://docs.claude.com/en/docs/claude-code |

---

## I. CONVENCIONES DE COMMIT

Conventional Commits estricto:

| Tipo | Cuándo usarlo |
|---|---|
| `feat:` | Nueva funcionalidad para el usuario |
| `fix:` | Corrección de bug |
| `chore:` | Cambios de infraestructura, dependencias, configs |
| `docs:` | Solo cambios de documentación |
| `test:` | Añadir o corregir tests |
| `refactor:` | Refactor sin cambio funcional |
| `perf:` | Mejora de rendimiento |
| `style:` | Formato, sin cambio de lógica |
| `ci:` | Cambios en CI/CD |

Formato:
```
<tipo>(<scope>): <descripción corta>

<descripción larga opcional>

<footer opcional, ej. closes #123>
```

Ejemplos:
```
feat(bricks): add transpiler for gallery blocks
fix(scraper): handle webflow data-w-id null edge case
chore(deps): bump playwright to 1.50.x
docs: complete deployment runbook
test(api): add integration tests for migrations endpoint
```

---

## J. POLÍTICA DE BRANCHES

- `main`: producción. Solo recibe merges desde `develop` vía PR con todos los checks verdes
- `develop`: integración. Recibe merges desde ramas `feature/*` y `fix/*`
- `feature/fase-N-nombre`: trabajo de cada fase
- `fix/descripcion-corta`: correcciones puntuales
- `hotfix/descripcion`: correcciones urgentes directas a main (raro)

Reglas:
- No push directo a `main` ni a `develop`
- PR obligatorio con al menos una revisión humana (Nacho o Álvaro)
- Todos los tests verdes obligatorios para mergear
- Mensaje de squash-merge respeta Conventional Commits
