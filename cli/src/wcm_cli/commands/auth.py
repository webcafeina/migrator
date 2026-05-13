"""Login/logout. Almacenan el JWT en ~/.config/wcm/credentials.json."""

from __future__ import annotations

from typing import Annotated

import httpx
import typer

from wcm_cli import output
from wcm_cli.config import CliConfig, clear_token, save_token
from wcm_cli.errors import CliApiError, CliAuthError, CliConfigError

app = typer.Typer(help="Autenticación")


@app.command()
def login(
    email: Annotated[str, typer.Option(prompt=True, help="Email de tu usuario")],
    password: Annotated[
        str,
        typer.Option(prompt=True, hide_input=True, help="Contraseña"),
    ],
) -> None:
    """Inicia sesión en el API y guarda el token localmente."""
    cfg = CliConfig.load()
    url = f"{cfg.api_url}/api/v1/auth/login"

    try:
        with httpx.Client(timeout=cfg.timeout_s, verify=cfg.verify_ssl) as client:
            response = client.post(url, json={"email": email, "password": password})
    except httpx.ConnectError as e:
        raise CliConfigError(
            f"No se pudo conectar al API ({cfg.api_url}).",
            hint="¿Está `uvicorn wcm_api.main:app` arrancado?",
        ) from e

    if response.status_code == 401:
        raise CliAuthError("Credenciales inválidas.", hint="Verifica email y contraseña.")
    if response.status_code != 200:
        raise CliApiError(f"Login falló: HTTP {response.status_code} — {response.text[:200]}")

    # El API responde con la cookie wcm_session; el JWT está dentro. Para CLI,
    # extraemos el token de la cookie y lo guardamos para uso Bearer posterior.
    token = response.cookies.get("wcm_session")
    if not token:
        raise CliApiError("API respondió 200 pero sin cookie wcm_session.")

    path = save_token(token)
    user = response.json()
    output.success(f"Sesión iniciada como {user['email']} (rol: {user['role']})")
    output.info(f"Token cacheado en {path} (modo 600)")


@app.command()
def logout() -> None:
    """Cierra sesión local (borra el token cacheado)."""
    clear_token()
    output.success("Sesión cerrada localmente. Token borrado.")


@app.command()
def me() -> None:
    """Muestra el usuario actualmente autenticado."""
    from wcm_cli.client import ApiClient

    client = ApiClient()
    user = client.get("/api/v1/auth/me")
    if output.is_json_mode():
        output.emit_json(user)
    else:
        output.key_value(
            {
                "email": user["email"],
                "nombre": user["name"],
                "rol": user["role"],
                "activo": user["is_active"],
            }
        )
