"""Entrypoint del CLI. Construye `app` (Typer) y ensambla los subcomandos.

Compatible con `webcafeina-migrator` (oficial) y `wcm` (alias).
"""

from __future__ import annotations

import typer

from wcm_cli import output
from wcm_cli.commands import (
    auth,
    campaigns,
    deploy,
    doctor,
    leads,
    outreach,
    projects,
    residual_tasks,
    setup_cmd,
    users,
)

app = typer.Typer(
    name="webcafeina-migrator",
    help=(
        "Webcafeína Migrator — herramienta interna de prospección + migración.\n\n"
        "Uso típico:\n"
        "  wcm setup       # crear .env\n"
        "  wcm doctor      # comprobar entorno\n"
        "  wcm login       # iniciar sesión\n"
        "  wcm projects new --source URL --client NAME\n"
        "  wcm projects start <id>"
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@app.callback()
def _root(
    json_output: bool = typer.Option(
        False, "--json", help="Salida en JSON (suprime Rich, machine-readable)."
    ),
) -> None:
    """Opciones globales."""
    if json_output:
        output.set_json_mode(True)


# Comandos top-level (verbo simple)
app.add_typer(setup_cmd.app, name="setup")
app.add_typer(doctor.app, name="doctor")
app.add_typer(deploy.app, name="deploy")

# Subcomandos (recurso + verbo)
app.add_typer(auth.app, name="auth")
app.add_typer(leads.app, name="leads")
app.add_typer(projects.app, name="projects")
app.add_typer(campaigns.app, name="campaigns")
app.add_typer(outreach.app, name="outreach")
app.add_typer(residual_tasks.app, name="residual-tasks")
app.add_typer(users.app, name="users")


# Atajos de uso frecuente: `wcm login` además de `wcm auth login`
@app.command("login", hidden=False, help="Atajo de `wcm auth login`")
def login_shortcut(
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
) -> None:
    """Inicia sesión (atajo de `wcm auth login`)."""
    auth.login(email=email, password=password)


@app.command("logout", hidden=False, help="Atajo de `wcm auth logout`")
def logout_shortcut() -> None:
    """Cierra sesión (atajo de `wcm auth logout`)."""
    auth.logout()


def main() -> None:
    """Entrypoint. CliError hereda de click.ClickException, así que Typer
    la captura automáticamente y aplica exit_code + `CliError.show()` sin
    necesidad de wrapper try/except.
    """
    app()


if __name__ == "__main__":
    main()
