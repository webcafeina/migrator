# infra/systemd

Unit files de systemd generados por el skill `systemd-service-generator`.

## Estado

Vacío en Fase 0. Se materializa en **Fase 12 — Infra/Deploy**.

## Ficheros previstos

- `webcafeina-api.service`
- `webcafeina-worker.service`
- `webcafeina-beat.service`
- `webcafeina-dashboard.service`

Todos con hardening estándar (`NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `ReadWritePaths` restringido).

Se instalan en `/etc/systemd/system/` con el script `infra/whm-setup/07-systemd-units.sh`.

Ver [STATE.md](../../STATE.md) y skill [systemd-service-generator](../../.claude/skills/systemd-service-generator/SKILL.md).
