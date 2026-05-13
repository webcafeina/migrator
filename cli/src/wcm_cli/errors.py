"""Errores del CLI.

`CliError` hereda de `click.ClickException` para que Click/Typer lo
maneje automáticamente: detecta la excepción al ejecutar un comando,
llama a `show()` para imprimir el mensaje, y aplica `exit_code`. Funciona
tanto en ejecución real (binario) como en tests con `CliRunner`.

`show()` se sobrescribe para escribir a stdout (no stderr por defecto
de Click) — facilita inspección en tests vía `result.output`. En modo
`--json` (donde stdout debe quedar JSON-limpio), `show()` redirige a stderr.
"""

from __future__ import annotations

import os
import sys

import click


def _is_json_mode() -> bool:
    return os.environ.get("WCM_JSON", "").lower() in ("1", "true", "yes")


class CliError(click.ClickException):
    """Raíz. exit_code = 1 por defecto."""

    exit_code: int = 1

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint

    def show(self, file=None) -> None:  # type: ignore[override]
        if file is None:
            file = sys.stderr if _is_json_mode() else sys.stdout
        click.echo(f"✕ {self.message}", file=file)
        if self.hint:
            click.echo(f"  hint: {self.hint}", file=file)


class CliConfigError(CliError):
    exit_code = 2


class CliAuthError(CliError):
    exit_code = 3


class CliApiError(CliError):
    exit_code = 4


class CliInputError(CliError):
    exit_code = 5
