---
name: systemd-service-generator
description: Genera unit files systemd parametrizables para api/worker/beat/dashboard. Aplica hardening estándar (NoNewPrivileges, ProtectSystem, ReadWritePaths). Compatible con WHM/cPanel sin necesidad de Docker.
---

# Skill — SystemD Service Generator

## Propósito

Generar unit files de systemd consistentes para los procesos del Migrator, aplicando hardening por defecto.

## Contrato

```python
class SystemDGenerator:
    def __init__(self, app_user: str, app_path: str, env_file: str = "/etc/webcafeina-migrator/env"):
        ...

    def render(self, service: ServiceSpec) -> str:
        """Devuelve el contenido del unit file."""

    def write_all(self, services: list[ServiceSpec], output_dir: Path) -> list[Path]:
        """Escribe N units en infra/systemd/."""
```

`ServiceSpec`:
```python
@dataclass
class ServiceSpec:
    name: str                       # "webcafeina-api"
    description: str
    exec_start: str                 # comando completo
    working_directory: str
    requires_db: bool = True
    requires_redis: bool = True
    type: Literal["simple", "forking", "oneshot"] = "simple"
    restart: Literal["on-failure", "always", "no"] = "on-failure"
    restart_sec: int = 5
    read_write_paths: list[str] = []  # carpetas a las que el proceso puede escribir
    extra_env: dict[str, str] = {}
```

## Plantilla base

```ini
[Unit]
Description={description}
After=network.target {extra_after}
Wants={extra_wants}

[Service]
Type={type}
User={app_user}
Group={app_user}
WorkingDirectory={working_directory}
EnvironmentFile={env_file}
{extra_env_inline}
ExecStart={exec_start}
Restart={restart}
RestartSec={restart_sec}
StandardOutput=journal
StandardError=journal
SyslogIdentifier={name}

# Hardening (Anthropic + best-practice defaults)
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
RestrictNamespaces=true
LockPersonality=true
RestrictRealtime=true
SystemCallArchitectures=native
ReadWritePaths={read_write_paths_joined}

[Install]
WantedBy=multi-user.target
```

## Services Webcafeína Migrator

```python
services = [
    ServiceSpec(
        name="webcafeina-api",
        description="Webcafeína Migrator API (FastAPI)",
        exec_start=f"{venv}/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 4",
        working_directory=f"{app_path}/apps/api",
        read_write_paths=[f"{app_path}/logs", f"{app_path}/uploads", "/var/tmp"],
    ),
    ServiceSpec(
        name="webcafeina-worker",
        description="Webcafeína Migrator Worker (Celery)",
        exec_start=f"{venv}/bin/celery -A worker.app worker --loglevel=info --concurrency=4",
        working_directory=f"{app_path}/apps/worker",
        read_write_paths=[f"{app_path}/logs", f"{app_path}/uploads", "/var/tmp"],
    ),
    ServiceSpec(
        name="webcafeina-beat",
        description="Webcafeína Migrator Beat (Celery Beat)",
        exec_start=f"{venv}/bin/celery -A worker.app beat --loglevel=info",
        working_directory=f"{app_path}/apps/worker",
        read_write_paths=[f"{app_path}/logs", "/var/tmp"],
    ),
    ServiceSpec(
        name="webcafeina-dashboard",
        description="Webcafeína Migrator Dashboard (Next.js standalone)",
        exec_start=f"/usr/bin/node {app_path}/apps/dashboard/.next/standalone/server.js",
        working_directory=f"{app_path}/apps/dashboard",
        requires_db=False,
        requires_redis=False,
        extra_env={"PORT": "3000"},
        read_write_paths=[f"{app_path}/logs", "/var/tmp"],
    ),
]
```

## Dependencias inter-servicios

- `requires_db=True` añade `After=postgresql.service` + `Wants=postgresql.service`.
- `requires_redis=True` añade `After=redis.service` + `Wants=redis.service`.
- Workers dependen del API (en cierto sentido). No hard dependency en systemd: el API tampoco necesita workers para arrancar.

## Output

```
infra/systemd/
  webcafeina-api.service
  webcafeina-worker.service
  webcafeina-beat.service
  webcafeina-dashboard.service
```

## Script de instalación

`infra/whm-setup/07-systemd-units.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
APP_PATH="/opt/webcafeina-migrator"

for svc in api worker beat dashboard; do
  cp "${APP_PATH}/infra/systemd/webcafeina-${svc}.service" /etc/systemd/system/
done

systemctl daemon-reload
systemctl enable webcafeina-api webcafeina-worker webcafeina-beat webcafeina-dashboard
systemctl start webcafeina-api webcafeina-worker webcafeina-beat webcafeina-dashboard
systemctl status webcafeina-* --no-pager
```

## Verificación

`infra/whm-setup/10-smoke-test.sh` comprueba:

```bash
systemctl is-active webcafeina-api    || exit 1
systemctl is-active webcafeina-worker || exit 1
curl -sf http://127.0.0.1:8000/health | grep -q '"ok":true' || exit 2
curl -sf http://127.0.0.1:3000/       | grep -qi 'webcafe' || exit 3
```

## Tests

- Render de cada `ServiceSpec` debe matchear snapshot esperado
- Snapshot stored in `tests/fixtures/systemd/<service>.expected.service`

## Dependencias

- `jinja2` para plantillas
- stdlib `pathlib`
