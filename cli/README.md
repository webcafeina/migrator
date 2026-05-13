# cli/

CLI de operador del Webcafeína Migrator. Construido con **Typer + Rich**.

## Estado

Materializado en **Fase 7**. 17 tests con `CliRunner` + `respx`. Dos entrypoints:
- `webcafeina-migrator` (oficial, documentado en el prompt maestro)
- `wcm` (alias corto para uso diario)

## Instalación

```bash
# desde la raíz del repo
source .venv/bin/activate
pip install -e ./cli
# ya están disponibles `wcm` y `webcafeina-migrator` en el PATH del venv
```

## Comandos

```
wcm setup                                    # crea .env desde .env.example
wcm doctor                                   # diagnóstico end-to-end del entorno
wcm login                                    # iniciar sesión
wcm logout                                   # cerrar sesión local
wcm auth me                                  # usuario actual
wcm leads list [--sector] [--region] [--builder] [--status] [--min-score]
wcm leads get ID
wcm leads refingerprint ID
wcm projects list [--status]
wcm projects new --source URL --client NAME [--ecommerce] [--multilang]
wcm projects get|status ID                   # detalle + fases
wcm projects start|resume|cancel ID
wcm projects export-checklist ID --out PATH  # stub (Fase 10)
wcm campaigns launch --sector X --region Y [--target N]
wcm residual-tasks list [--project-id] [--category] [--status]
wcm residual-tasks done ID
wcm deploy --env {staging|production}        # stub (Fase 12)
```

## Modo JSON

Cualquier comando admite `--json` para emitir JSON machine-readable a stdout (los mensajes informativos van a stderr):

```bash
wcm --json leads list | jq '.[] | .url'
wcm --json projects get 42 | jq '.project.status'
```

## Autenticación

Tres formas, en orden de prioridad:

1. **Variable de entorno** `WCM_TOKEN` — útil en CI.
2. **Cache local** en `~/.config/wcm/credentials.json` (creado por `wcm login`, permisos `0600`).
3. Si no hay token y el comando lo requiere → `CliAuthError` con hint para ejecutar `wcm login`.

El cliente envía `Authorization: Bearer <token>` automáticamente.

## Configuración

`API_URL` se lee de `.env` (cwd) o de la env del shell. Default: `http://localhost:8000`.

Variables relevantes:
- `API_URL` — URL del backend (default `http://localhost:8000`)
- `WCM_TOKEN` — JWT para auth (override del cache local)
- `WCM_JSON=1` — equivalente a `--json` global
- `WCM_CLI_TIMEOUT_S` — timeout HTTP en segundos (default 30)

## Errores

Cada error termina con un mensaje humano + `exit_code` específico:

| Exit | Tipo | Cuándo |
|---|---|---|
| 1 | `CliError` genérico | Caso por defecto |
| 2 | `CliConfigError` | Falta `.env`, API inaccesible |
| 3 | `CliAuthError` | No autenticado / 401 / 403 |
| 4 | `CliApiError` | API devolvió 5xx tras retries |
| 5 | `CliInputError` | Input del usuario inválido |

En modo `--json`, el mensaje va a stderr para mantener stdout JSON-limpio.

## Tests

```bash
pytest cli -q
```

17 tests cubren: help/subcomandos visibles, login flow con respx, logout limpia cache, leads list/refingerprint, projects new/start/get 404 friendly error, campaigns launch, API connect error con hint.

## Setup recomendado del operador

```bash
wcm setup       # crea .env
$EDITOR .env    # rellena credenciales
wcm doctor      # comprueba que todo está accesible
wcm login       # auth contra el API
wcm projects new --source https://demo-wix-real.com/ --client "Demo S.L."
wcm projects start <id>
wcm projects status <id>
```

## ADRs relacionados

- ADR-021 — Doble entrypoint `webcafeina-migrator` + `wcm`; CliError hereda de ClickException para integración nativa
