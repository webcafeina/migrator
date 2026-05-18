"""Comandos sobre usuarios del sistema (admin-only).

Cubre el CRUD documentado en `OperationRunbook` del dashboard:
- `wcm users list`
- `wcm users create --email --role --name [--password]`
- `wcm users set-role EMAIL --role admin|operator|viewer`
- `wcm users deactivate EMAIL` / `wcm users activate EMAIL`
- `wcm users delete EMAIL --confirm`

Todos los endpoints requieren rol admin. El usuario actual debe haber
hecho `wcm login` con credenciales de admin antes.
"""

from __future__ import annotations

import secrets
import string
from typing import Annotated

import typer

from wcm_cli import output
from wcm_cli.client import ApiClient
from wcm_cli.errors import CliApiError, CliInputError

app = typer.Typer(help="Gestión de usuarios del sistema (admin-only)")


def _resolve_email(client: ApiClient, email: str) -> dict:
    """Convierte email → user dict (los endpoints usan UUID, no email).
    Levanta CliInputError si no hay match."""
    users = client.get("/api/v1/users")
    for u in users:
        if u["email"].lower() == email.lower():
            return u
    raise CliInputError(
        f"Usuario no encontrado: {email}",
        hint="Usa `wcm users list` para ver los usuarios registrados.",
    )


def _gen_password(length: int = 18) -> str:
    """Password aleatorio aceptable por `UserCreate` (>=12 chars)."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


@app.command("list")
def list_users() -> None:
    """Lista todos los usuarios del sistema (admin-only)."""
    client = ApiClient()
    users = client.get("/api/v1/users")
    if not users:
        output.info("Sin usuarios registrados.")
        return

    output.render_table(
        f"Usuarios ({len(users)})",
        ["email", "name", "role", "activo", "creado"],
        [
            [
                u["email"],
                u["name"],
                u["role"],
                "✓" if u["is_active"] else "✗",
                u["created_at"][:10],
            ]
            for u in users
        ],
        json_payload=users,
    )


@app.command("create")
def create_user(
    email: Annotated[str, typer.Option(help="Email del nuevo usuario")],
    name: Annotated[str, typer.Option(help="Nombre del usuario")],
    role: Annotated[
        str,
        typer.Option(
            help="Rol: admin | operator | viewer",
        ),
    ] = "operator",
    password: Annotated[
        str | None,
        typer.Option(
            help="Password (>=12 chars). Si vacío, se genera uno aleatorio "
            "y se imprime al final."
        ),
    ] = None,
    inactive: Annotated[
        bool,
        typer.Option("--inactive", help="Crear deshabilitado por defecto."),
    ] = False,
) -> None:
    """Crea un usuario nuevo. Solo admin puede ejecutarlo."""
    if role not in {"admin", "operator", "viewer"}:
        raise CliInputError(
            f"Rol inválido: {role}",
            hint="Usa admin, operator o viewer.",
        )
    pwd = password or _gen_password()
    if len(pwd) < 12:
        raise CliInputError(
            "El password debe tener >=12 caracteres.",
        )
    client = ApiClient()
    user = client.post(
        "/api/v1/users",
        json={
            "email": email,
            "name": name,
            "role": role,
            "is_active": not inactive,
            "password": pwd,
        },
    )
    output.success(
        f"Usuario {user['email']} creado · rol={user['role']} · id={user['id']}"
    )
    if password is None:
        output.warning(
            f"Password generado: {pwd}\n"
            "Comparte por canal seguro y pide cambiarlo en el primer login."
        )


@app.command("set-role")
def set_role(
    email: Annotated[str, typer.Argument(help="Email del usuario")],
    role: Annotated[
        str,
        typer.Option(help="Nuevo rol: admin | operator | viewer"),
    ],
) -> None:
    """Cambia el rol de un usuario existente."""
    if role not in {"admin", "operator", "viewer"}:
        raise CliInputError(f"Rol inválido: {role}")
    client = ApiClient()
    user = _resolve_email(client, email)
    updated = client.patch(f"/api/v1/users/{user['id']}", json={"role": role})
    output.success(
        f"{updated['email']} ahora es {updated['role']}"
    )


@app.command("activate")
def activate(
    email: Annotated[str, typer.Argument(help="Email del usuario")],
) -> None:
    """Activa un usuario desactivado (puede volver a iniciar sesión)."""
    client = ApiClient()
    user = _resolve_email(client, email)
    updated = client.patch(
        f"/api/v1/users/{user['id']}", json={"is_active": True}
    )
    output.success(f"{updated['email']} activado")


@app.command("deactivate")
def deactivate(
    email: Annotated[str, typer.Argument(help="Email del usuario")],
) -> None:
    """Desactiva un usuario (no podrá iniciar sesión hasta reactivar)."""
    client = ApiClient()
    user = _resolve_email(client, email)
    updated = client.patch(
        f"/api/v1/users/{user['id']}", json={"is_active": False}
    )
    output.success(f"{updated['email']} desactivado")


@app.command("delete")
def delete_user(
    email: Annotated[str, typer.Argument(help="Email del usuario")],
    confirm: Annotated[
        bool,
        typer.Option("--confirm", help="Confirma borrado irreversible"),
    ] = False,
) -> None:
    """Borra un usuario permanentemente. Requiere --confirm.

    Para deshabilitar acceso sin borrar (preferible), usa
    `wcm users deactivate EMAIL`.
    """
    if not confirm:
        raise CliInputError(
            "Borrar requiere --confirm (irreversible).",
            hint=(
                "Si solo quieres bloquear acceso, usa\n"
                "`wcm users deactivate EMAIL` (reversible)."
            ),
        )
    client = ApiClient()
    user = _resolve_email(client, email)
    try:
        client.delete(f"/api/v1/users/{user['id']}")
    except CliApiError as e:
        if e.details.get("constraint"):
            output.error(
                f"No se puede borrar (FK constraint: {e.details['constraint']})"
            )
            raise typer.Exit(code=1) from None
        raise
    output.success(f"Usuario {email} borrado permanentemente")
