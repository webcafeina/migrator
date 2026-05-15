# Scripts — controles del stack local

Utilidades para operar el entorno de desarrollo en macOS sin Docker.
Documentación complementaria a [`docs/dev-local.md`](../docs/dev-local.md):
ese doc cubre el **setup inicial** (BD, migraciones, seed) — este README
cubre el **uso diario** una vez que el setup ya está hecho.

Los scripts asumen Bash o Zsh, Homebrew, `tmux 3.x` y el venv en `venv/`.

---

## Resumen

| Script | Qué hace |
|---|---|
| `dev-up.sh` | Arranca API + Worker + Beat + Dashboard en una sesión `tmux` con 4 ventanas. |
| `dev-down.sh` | Mata la sesión `tmux` y los procesos asociados. |
| `dev-status.sh` | Reporta el estado runtime de toda la stack (brew + tmux + procesos + HTTP). |
| `fix-venv-hidden-pth.sh` | **OBSOLETO** desde ADR-035. Imprime aviso y sale. La causa real era iCloud Drive sincronizando el Desktop; ahora el venv vive en `venv.nosync/` con symlink `venv` y el problema desaparece. |

---

## `scripts/dev-up.sh`

Arranca toda la stack en una sesión `tmux` llamada `wcm-dev`. Idempotente:
si la sesión ya existe, la mata y la recrea (es decir, **`dev-up.sh` también
sirve para "reiniciar"**).

### Uso

```bash
bash scripts/dev-up.sh             # arranca todo (api+worker+beat+dashboard)
bash scripts/dev-up.sh --no-beat   # salta beat (más rápido, sin retention sweep)
bash scripts/dev-up.sh --attach    # arranca y entra inmediatamente al tmux
bash scripts/dev-up.sh --help      # ayuda
```

### Qué hace, paso a paso

1. **Pre-checks**: existe `.env`, `venv/bin/uvicorn`, `venv/bin/celery`, `tmux`, `pnpm`.
2. **Brew services**: arranca `redis` y `postgresql@16` si no estuvieran corriendo.
3. **Verifica conectividad**: `redis-cli ping` y `pg_isready`.
4. **Recrea la sesión `tmux`** con las siguientes ventanas:

   | # | Ventana | Proceso | Puerto |
   |---|---|---|---|
   | 1 | `api` | `uvicorn wcm_api.main:app --reload` | 8000 |
   | 2 | `worker` | `celery -A wcm_worker.celery_app worker -c 2` | — |
   | 3 | `beat` | `celery -A wcm_worker.celery_app beat` (omitido con `--no-beat`) | — |
   | 4 | `dashboard` | `next dev -p 3000` | 3000 |

5. Imprime las URLs útiles y sugiere `wcm doctor` para validar.

> Cada ventana hace `set -a; source .env; set +a` antes del proceso, así
> que los cambios en `.env` se aplican tras un nuevo `dev-up.sh`. No hace
> hot-reload de variables.

### Lo que **no** hace

- No crea la BD ni aplica migraciones (eso lo cubre `docs/dev-local.md` una vez).
- No instala dependencias (`pip install` / `pnpm install` siguen siendo manuales).
- No parará automáticamente al cerrar la terminal — `tmux` mantiene los procesos.

---

## `scripts/dev-down.sh`

Para la stack. Por defecto **no** toca los `brew services` (Redis y
Postgres se quedan corriendo porque consumen poco y arrancan rápido la
próxima vez).

### Uso

```bash
bash scripts/dev-down.sh           # mata tmux + procesos huérfanos
bash scripts/dev-down.sh --all     # también para Redis y Postgres
bash scripts/dev-down.sh --help    # ayuda
```

### Qué hace

1. `tmux kill-session -t wcm-dev` (si existe).
2. `pkill -f` defensivo para huérfanos fuera de tmux: `uvicorn wcm_api`,
   `celery -A wcm_worker`, `next dev -p 3000`.
3. Con `--all`: `brew services stop redis` + `brew services stop postgresql@16`.

---

## `scripts/dev-status.sh`

Inspecciona el estado actual de la stack sin tocar nada. Pensado para
responder rápido a "¿qué tengo levantado y qué se ha caído?".
Complementa a `wcm doctor`, que valida `.env` y conectividad TCP/HTTP —
este script mira los procesos en sí.

### Uso

```bash
bash scripts/dev-status.sh           # tabla humana por secciones
bash scripts/dev-status.sh --quiet   # silencioso, solo exit code (útil en CI/cron)
bash scripts/dev-status.sh --json    # JSON para scripting
bash scripts/dev-status.sh --help
```

### Qué chequea

| Sección | Comprobaciones |
|---|---|
| Servicios base | `brew services` para `redis` y `postgresql@16` + `redis-cli ping` + `pg_isready` |
| Sesión tmux | Existencia de `wcm-dev` y nº/nombres de ventanas |
| Procesos del stack | Por cada uno (api, worker, beat, dashboard): ventana viva + pid del proceso vía `pgrep -f` + (api/dashboard) HTTP probe |
| Procesos sueltos | Duplicados de `uvicorn`/`celery worker`/`celery beat` fuera de tmux (Next no se chequea: arranca padre+hijo legítimos) |

### Estados

- `OK` — todo bien.
- `WARN` — proceso vivo pero algo raro (HTTP 4xx/5xx, no responde, duplicado).
- `FAIL` — proceso esperado pero ausente (ventana tmux viva con proceso muerto, brew started pero no responde, etc.).
- `SKIP` — no aplica (p. ej. ventana `beat` ausente porque arrancaste con `--no-beat`).

### Exit codes

- `0` — ningún `FAIL` (los `WARN` y `SKIP` no cuentan).
- `1` — uno o más `FAIL`.
- `2` — flag desconocido.

### Caso típico de diagnóstico

Si `dev-status.sh` reporta `[FAIL] worker  ventana tmux viva pero proceso no encontrado`, el flujo de resolución es:

```bash
tmux capture-pane -p -t wcm-dev:worker | tail -30   # ver el error real
```

Casos comunes:

- **`ModuleNotFoundError: No module named 'wcm_worker'`** → el venv está mal montado. Verifica que `venv` es un symlink a `venv.nosync` y que `venv/lib/python3.14/site-packages/__editable__*.pth` no tienen el flag `hidden` (`ls -lO venv/lib/.../*.pth`). Si tienen `hidden`, mira ADR-035: el repo está bajo iCloud sync y necesita el sufijo `.nosync`.
- **Error de conexión a Redis o Postgres** → mira `wcm doctor`.
- **Error de import de un paquete del repo** → reinstala el editable en cuestión: `venv/bin/pip install -e ./packages/<nombre>[dev]`.

---

## Atajos `tmux` imprescindibles

Una vez dentro de la sesión (`tmux attach -t wcm-dev`):

| Atajo | Acción |
|---|---|
| `Ctrl+B` → `N` | Ventana siguiente |
| `Ctrl+B` → `P` | Ventana anterior |
| `Ctrl+B` → `0..3` | Ir directo a la ventana por número |
| `Ctrl+B` → `W` | Listado interactivo de ventanas |
| `Ctrl+B` → `[` | Modo scroll (flechas / PgUp / PgDn; `q` para salir) |
| `Ctrl+B` → `D` | **Detach** (procesos siguen corriendo) |
| `Ctrl+C` (dentro de una ventana) | Mata **ese** proceso (no la sesión) |

Listar y enviar comandos sin entrar:

```bash
tmux list-windows -t wcm-dev
tmux capture-pane -p -t wcm-dev:api | tail -40     # leer últimos logs del API
tmux send-keys -t wcm-dev:api C-c                  # mandar Ctrl+C al API
```

---

## Patrones de uso típicos

### Sesión de desarrollo de un día

```bash
bash scripts/dev-up.sh           # mañana, arrancar
venv/bin/wcm doctor             # verificar verde
# ...trabajo...
bash scripts/dev-down.sh         # fin del día (Redis/PG siguen)
```

### Reiniciar solo el API tras tocar deps Python

`tmux` permite reiniciar un proceso sin tirar el resto:

```bash
tmux send-keys -t wcm-dev:api C-c           # parar uvicorn
sleep 1
tmux send-keys -t wcm-dev:api \
  'set -a; source .env; set +a && venv/bin/uvicorn wcm_api.main:app --host 127.0.0.1 --port 8000 --reload' C-m
```

Equivalente con `dev-up.sh` completo (más fácil pero reinicia los 4 procesos):

```bash
bash scripts/dev-up.sh           # mata la sesión y la recrea
```

### Smoke test sin beat (más ligero)

```bash
bash scripts/dev-up.sh --no-beat
```

Recomendado cuando no estás probando la limpieza por retención RGPD.

### Liberar memoria al final de la semana

```bash
bash scripts/dev-down.sh --all   # también para Redis y Postgres
```

---

## Troubleshooting

| Síntoma | Causa probable | Solución |
|---|---|---|
| `ERROR: tmux no instalado` | Falta tmux | `brew install tmux` |
| `ERROR: venv/bin/uvicorn no existe` | venv vacío o no creado | Reinstalar el venv (ver `docs/dev-local.md §1`) |
| `ERROR: redis no responde a ping` | brew services dice "started" pero el socket está roto | `brew services restart redis` |
| `pg_isready` falla pero `brew services` dice "started" | Postgres arrancando aún | Esperar 3–5 s y reintentar |
| Dashboard arranca pero `http://localhost:3000` da 404 | Next.js aún compilando | Esperar (primera build ~30 s); ver ventana `dashboard` |
| Worker no procesa tareas | Cola Redis distinta a la del API | Verificar `CELERY_BROKER_URL` igual en ambas ventanas |
| `wcm doctor` rojo en DB tras `dev-up.sh` | `.env` con `postgresql://` (asume psycopg2) | Cambiar a `postgresql+psycopg://` (WCM-029) |
| Procesos siguen tras `dev-down.sh` | Lanzados fuera de la sesión `tmux` | `pkill -f uvicorn`, `pkill -f celery`, `pkill -f "next dev"` |
| `tmux: command not found` después de `brew install` | Shell sin recargar | Abrir terminal nueva o `exec $SHELL -l` |

---

## Referencias

- [`docs/dev-local.md`](../docs/dev-local.md) — setup inicial completo.
- [`docs/playbook-operativo.md`](../docs/playbook-operativo.md) — runbooks de incidente (los `INC-NN`).
- [`CLAUDE.md`](../CLAUDE.md) §10 — restricciones de stack (sin Docker, systemd en producción).
- ADR-016 — bug `.pth` ocultos del venv en macOS.
- WCM-023 — issue que motivó estos scripts.
