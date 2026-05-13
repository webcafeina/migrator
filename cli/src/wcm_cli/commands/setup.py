"""Comando `wcm setup` — onboarding interactivo.

Si `.env` no existe, ofrece copiarlo desde `.env.example` con prompts
para las vars críticas. Si existe, muestra qué vars críticas están
vacías y propone editarlas manualmente (no auto-modifica un .env existente
porque puede tener secretos).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import typer

from wcm_cli import output

app = typer.Typer(help="Setup inicial del entorno")


_ENV_PATH = Path.cwd() / ".env"
_ENV_EXAMPLE_PATH = Path.cwd() / ".env.example"


@app.callback(invoke_without_command=True)
def setup() -> None:
    """Onboarding interactivo. Crea .env si no existe."""
    output.header("Setup Webcafeína Migrator")

    if _ENV_PATH.exists():
        output.info(f"Ya existe {_ENV_PATH}")
        output.info("Para forzar regenerarlo, bórralo manualmente y vuelve a ejecutar setup.")
        output.info("")
        output.info("Comprueba qué falta con: [accent]wcm doctor[/]")
        return

    if not _ENV_EXAMPLE_PATH.exists():
        output.error(
            f".env.example no encontrado en {Path.cwd()}",
            hint="Ejecuta `wcm setup` desde la raíz del repo.",
        )
        raise typer.Exit(code=2)

    if not typer.confirm(f"¿Crear .env desde .env.example en {_ENV_PATH}?", default=True):
        output.warning("Setup cancelado por el usuario")
        raise typer.Exit(code=0)

    shutil.copy(_ENV_EXAMPLE_PATH, _ENV_PATH)
    _ENV_PATH.chmod(0o600)
    output.success(f"Creado {_ENV_PATH} con permisos 600")
    output.info("")
    output.info("Próximos pasos:")
    output.info("  1. Edita .env con tus credenciales reales")
    output.info("  2. Ejecuta [accent]wcm doctor[/] para validar el entorno")
    output.info("  3. Ejecuta [accent]wcm login[/] para autenticarte contra el API")
