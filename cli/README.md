# cli/

CLI de operador `webcafeina-migrator` basada en **Typer** + Rich.

## Estado

Vacío en Fase 0. Se materializa en **Fase 7 — CLI**.

## Comandos previstos

```bash
webcafeina-migrator setup                            # setup interactivo
webcafeina-migrator prospect --sector X --region Y   # campaña de prospección
webcafeina-migrator leads list                       # listar leads
webcafeina-migrator new --source URL --client NAME   # nueva migración
webcafeina-migrator project status ID                # estado proyecto
webcafeina-migrator project resume ID                # reanudar tras error
webcafeina-migrator project export-checklist ID      # exportar MD + PDF
webcafeina-migrator deploy --env prod                # deploy a producción
webcafeina-migrator doctor                           # diagnóstico del entorno
```

## Estilo

- Output enriquecido con Rich (tablas, progress bars, spinners).
- Confirmaciones explícitas antes de operaciones destructivas.
- Logs JSON con `--json` para integración con scripts.

## Cómo se instala

(Documentar en Fase 7)

```bash
pip install -e ./cli
webcafeina-migrator --help
```

Ver [STATE.md](../STATE.md).
