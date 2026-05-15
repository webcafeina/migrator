# Desarrollo local — Webcafeína Migrator

Quickstart para correr la stack completa en macOS (sin Docker). Validado el 2026-05-14 con Python 3.14.4, Node 25, pnpm 9.15, Postgres 16, Redis 8.

> Para deploy en servidor WHM, ver [`docs/despliegue.md`](./despliegue.md). Aquí solo cubrimos dev local en Mac.

---

## 1. Pre-requisitos del sistema (5 min, una sola vez)

```bash
brew install postgresql@16 redis pgvector
brew services start postgresql@16
brew services start redis
redis-cli ping  # PONG
pg_isready      # accepting connections
```

**`pgvector` para Postgres 16**: el bottle de brew solo trae binarios para @17/@18. Hay que compilar desde fuente contra @16:

```bash
cd /tmp && rm -rf pgvector
git clone --depth=1 --branch v0.8.0 https://github.com/pgvector/pgvector.git
cd pgvector
PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH" make
PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH" make install
```

**venv Python** (ADR-035: si el repo vive bajo `~/Desktop/` o `~/Documents/`, macOS lo sincroniza con iCloud Drive. Eso, combinado con un nombre de venv dotted (`.venv`), causa que iCloud reaplique el flag `UF_HIDDEN` sobre los `.pth` cada pocos segundos, dejando los editables no importables. Solución: nombrar el venv `venv.nosync` (sufijo reconocido por iCloud para excluir) y exponerlo como `venv` vía symlink):

```bash
cd /Users/alvaro/Desktop/webcafeina-migrator
python3 -m venv venv.nosync
ln -s venv.nosync venv             # symlink estable; los scripts usan `venv/...`
venv/bin/pip install --upgrade pip wheel
venv/bin/pip install \
  -e './packages/shared-types[dev]' \
  -e './packages/db-schema[dev]' \
  -e './packages/scraper-core[dev]' \
  -e './packages/bricks-transpiler[dev]' \
  -e './packages/wp-client[dev]' \
  -e './apps/api[dev]' \
  -e './apps/worker[dev]' \
  -e './cli[dev]' \
  greenlet                          # requerido por SQLAlchemy async
```

> Las comillas alrededor de `'./packages/...[dev]'` son obligatorias en zsh para que no interprete `[dev]` como glob.

**Verificación**:

```bash
venv/bin/python -c "import wcm_api, wcm_worker, wcm_db, wcm_cli; print('OK')"
ls -lO venv/lib/python3.14/site-packages/__editable__*.pth | head -3
# La columna de flags debe mostrar '-' (no 'hidden'). Si dice 'hidden':
# - ¿`ls -ld venv*` confirma que el real es venv.nosync?
# - ¿El repo está bajo iCloud sync? Si está fuera (p. ej. ~/code/), basta venv/ sin truco.
```

En Linux (servidor WHM) el bug no existe: `python -m venv venv` directamente.

**Node deps**:

```bash
pnpm install --frozen-lockfile
```

---

## 2. Crear BD + extensión (5 min, una sola vez)

`infra/whm-setup/02-database.sh` asume Linux + `sudo -u postgres`. En macOS brew, el superusuario es el usuario actual:

```bash
psql postgres -c "CREATE ROLE webcafeina WITH LOGIN PASSWORD 'changeme';"
psql postgres -c "CREATE DATABASE webcafeina_migrator OWNER webcafeina;"
psql webcafeina_migrator -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql webcafeina_migrator -tAc "SELECT 'pgvector ' || extversion FROM pg_extension WHERE extname='vector';"
```

---

## 3. `.env` para dev local (3 min, una sola vez)

`.env.example` es la plantilla. Para dev local el operador rellena al menos:

```bash
cp .env.example .env

# Edita .env con:
DATABASE_URL=postgresql+asyncpg://webcafeina:changeme@localhost:5432/webcafeina_migrator
DATABASE_SYNC_URL=postgresql+psycopg://webcafeina:changeme@localhost:5432/webcafeina_migrator   # ojo: +psycopg (v3), no plain
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET=$(openssl rand -hex 32)
GOOGLE_MAPS_API_KEY=<tu-key>
COMPANY_CIF=B10463990
COMPANY_ADDRESS=Santa Cristina, s/n – Edificio Embarcadero, 10195 Cáceres
COMPANY_PRIVACY_POLICY_URL=https://webcafeina.com/politica-privacidad/
```

Opcional (para validar integraciones — sin ellas, los agents devuelven `skipped` sin romper nada):

```
RESEND_API_KEY=re_...
CLICKUP_API_TOKEN=pk_...
R2_ACCOUNT_ID= ...   R2_ACCESS_KEY_ID= ...   R2_SECRET_ACCESS_KEY= ...   R2_BUCKET=wcm-dev
SENTRY_DSN_API= ...  (o usa GlitchTip hosted, compatible drop-in: https://app.glitchtip.com)
```

---

## 4. Migrar BD + seed admin (3 min, una sola vez)

```bash
set -a; source .env; set +a
cd packages/db-schema && /Users/alvaro/Desktop/webcafeina-migrator/venv/bin/alembic -c alembic.ini upgrade head
cd /Users/alvaro/Desktop/webcafeina-migrator
```

**Crear admin**: no hay aún `wcm users create` (WCM-022). Por ahora:

```bash
set -a; source .env; set +a
venv/bin/python <<'PY'
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from wcm_db.models.users import User
from wcm_types.enums import UserRole
from wcm_api.security import hash_password
engine = create_engine(os.environ["DATABASE_SYNC_URL"])
with Session(engine) as s:
    if not s.query(User).filter_by(email="ops@webcafeina.com").first():
        s.add(User(
            email="ops@webcafeina.com",
            name="Operador Webcafeína",
            hashed_password=hash_password("dev-password-cambiar"),
            role=UserRole.ADMIN, is_active=True,
        ))
        s.commit()
        print("Admin creado: ops@webcafeina.com / dev-password-cambiar")
    else:
        print("Admin ya existe")
PY
```

---

## 5. Arrancar la stack (4 terminales)

Sin Docker, cada servicio en su propio shell (`tmux` o iTerm tabs, lo que prefieras). **Lo de `set -a; source .env; set +a` es obligatorio en cada terminal nuevo** — sin `.env` exportado los procesos no encuentran credenciales.

```bash
# Terminal 1 — API
set -a; source .env; set +a
venv/bin/uvicorn wcm_api.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2 — Celery worker
set -a; source .env; set +a
venv/bin/celery -A wcm_worker.celery_app worker --loglevel=info --concurrency=2

# Terminal 3 — Celery beat (opcional para smoke; necesario si testeas retention sweep)
set -a; source .env; set +a
venv/bin/celery -A wcm_worker.celery_app beat --loglevel=info

# Terminal 4 — Dashboard Next.js
pnpm --filter @webcafeina/dashboard exec next dev -p 3000
```

WCM-023 (pendiente): script `scripts/dev-up.sh` que arranque todo con `concurrently`/`tmux`.

---

## 6. Validar arranque

```bash
set -a; source .env; set +a
venv/bin/wcm doctor                           # esperado: todo ✓
curl -s http://127.0.0.1:8000/health/deep | jq # esperado: status=ok, db+redis ok, r2 ok/skipped
```

Login dashboard: abrir http://localhost:3000/login con `ops@webcafeina.com` / `dev-password-cambiar`.

---

## 7. Smoke test del flujo prospección

```bash
venv/bin/wcm login --email ops@webcafeina.com --password dev-password-cambiar

# Lanzar campaña (sectores buenos: "restaurante", "clínica dental", "hotel" — tienen website)
venv/bin/wcm campaigns launch --sector "restaurante" --region "Cáceres" --target 5

# Ver tabla
psql webcafeina_migrator -c "SELECT id, business_name, url, status, score FROM leads ORDER BY id;"
```

**Limitación conocida v0.1.0** (WCM-026..028): la task `wcm.prospector.run_campaign` solo crea leads DISCOVERED — no encadena fingerprint + enrich. Tampoco hay `wcm leads enrich` ni task Celery `enricher.run`. Workaround actual:

```bash
venv/bin/python <<'PY'
import os
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from wcm_db.models.leads import Lead
from wcm_worker.agents.fingerprinter import FingerprinterAgent
from wcm_worker.agents.enricher import EnricherAgent
from wcm_worker.agents.base import AgentContext

engine = create_engine(os.environ["DATABASE_SYNC_URL"])
with Session(engine) as session:
    leads = session.execute(select(Lead).where(Lead.status == "DISCOVERED")).scalars().all()
    for lead in leads:
        FingerprinterAgent().run(AgentContext(session=session, lead_id=lead.id))
        session.commit()
        # skip_embedding=True para no descargar el modelo e5-large (2.2GB)
        # en dev — si quieres el embedding real, quita el flag.
        EnricherAgent().run(AgentContext(session=session, lead_id=lead.id, extra={"skip_embedding": True}))
        session.commit()
        print(f"lead {lead.id}: enriched")
PY
```

Componer outreach (sí tiene endpoint API):

```bash
TOKEN=$(cat ~/.config/wcm/credentials.json | python3 -c "import json,sys; print(json.load(sys.stdin)['token'])")
curl -s -X POST http://127.0.0.1:8000/api/v1/leads/<lead_id>/outreach/compose \
    -H "Authorization: Bearer $TOKEN" | jq
```

Verificar la sequence:

```bash
psql webcafeina_migrator -c "
  SELECT id, lead_id, status, legal_validation_passed, legal_validator_version
  FROM outreach_sequences;
"
psql webcafeina_migrator -tAc "
  SELECT body_rendered FROM outreach_sends WHERE sequence_id=<seq_id> AND step_index=0;
"
```

El body debe contener: razón social, CIF B10463990, dirección, URL opt-out con JWT firmado.

---

## 8. Validaciones post-test

```bash
# Audit log (toda acción RGPD-relevante con legal_ground=6.1.f)
psql webcafeina_migrator -c "
  SELECT actor, action::text, entity_type, legal_ground, at::timestamp(0)
  FROM audit_log ORDER BY at DESC LIMIT 15;
"

# Métricas Prometheus
curl -s http://127.0.0.1:8000/metrics | grep -E "^wcm_(http|agent|celery)" | head -10

# GlitchTip — enviar evento test
venv/bin/python -c "
import sentry_sdk, os
sentry_sdk.init(dsn=os.environ['SENTRY_DSN_API'], environment='local-test')
print(sentry_sdk.capture_message('hello', level='info'))
sentry_sdk.flush(timeout=5)
"
```

---

## 9. Cleanup

```bash
# Parar procesos (Ctrl+C en cada terminal) o:
pkill -f "uvicorn wcm_api"
pkill -f "celery -A wcm_worker"
pkill -f "next dev"

# Servicios brew se pueden dejar corriendo (consumen poco) o parar:
brew services stop redis
brew services stop postgresql@16

# Limpiar BD si quieres empezar de cero:
psql postgres -c "DROP DATABASE webcafeina_migrator;"
# Y volver al paso 2.
```

---

## 10. Bugs y limitaciones descubiertos en el primer smoke (2026-05-14)

Trackeados en `ISSUES.md`:

- **WCM-022**: `wcm users create` para no usar script Python ad-hoc.
- **WCM-023**: `scripts/dev-up.sh` para arrancar las 4 terminales con `tmux`.
- **WCM-024**: `infra/whm-setup/02-database.sh` con flag `--macos-local`.
- **WCM-025**: ADR-034 documentando GlitchTip como backend.
- **WCM-026** (crítico): `ProspectorAgent` no encadena fingerprint+enrich tras crear leads. Pipeline incompleto en producción.
- **WCM-027** (crítico): no existe task Celery `wcm.enricher.run` ni endpoint `/leads/{id}/enrich` ni CLI `wcm leads enrich`.
- **WCM-028**: el comando CLI `wcm campaigns launch` imprime warning estático "ProspectorAgent es stub en Fase 6" — texto obsoleto (es real desde Fase 9).
- **WCM-029**: `DATABASE_SYNC_URL` requiere prefix `postgresql+psycopg://` para psycopg v3 (no plain `postgresql://`). `.env.example` debería usar el prefix correcto.
- **WCM-030**: `greenlet` no estaba en deps explícitas — `/health/deep` rompía hasta instalarlo a mano. Añadir a `apps/api/pyproject.toml`.
- **WCM-031**: bug real en `ProspectorAgent` (fix aplicado en sesión): Text Search legacy NO devuelve `website`, hay que llamar `place_details` por place. Sin el fix, **ninguna campaña producía leads** en producción.

---

## 11. Tour mínimo para confirmar que funciona

5 minutos manuales tras el setup:

1. `wcm doctor` → todo verde.
2. `curl http://127.0.0.1:8000/health/deep` → `status: ok`.
3. Login en http://localhost:3000/login.
4. Lanzar campaña restaurante/Cáceres con `target=5`.
5. Workaround Python: fingerprint+enrich.
6. Componer outreach por API.
7. Inspeccionar `outreach_sends.body_rendered` en BD: ver que el opt-out URL y el bloque legal LSSI-CE están bien.

Si los 7 pasos pasan, la herramienta funciona end-to-end en local para iterar sobre Fase 16+.
