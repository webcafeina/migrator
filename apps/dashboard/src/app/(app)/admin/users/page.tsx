import Link from "next/link";

import { ApiError, api } from "@/lib/api";
import type { UserRead } from "@/types/api";

import { UsersManager } from "./_components/users-manager";

/**
 * `/admin/users` — gestión de usuarios admin-only. Espejo UI del CLI
 * `wcm users`. RBAC backend (`require_role(admin)`) decide; si el
 * usuario actual NO es admin, el fetch a `/users` da 403 y mostramos
 * mensaje amigable.
 */
export default async function AdminUsersPage() {
  let users: UserRead[] = [];
  let forbidden = false;
  try {
    users = await api.get<UserRead[]>("/api/v1/users");
  } catch (err) {
    if (err instanceof ApiError && err.status === 403) {
      forbidden = true;
    }
    // Otros errores se propagarán como error de Next; preferimos no
    // ocultar bugs reales del API.
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold text-wcm-text">
            Usuarios del sistema
          </h1>
          <p className="text-xs text-muted-foreground">
            Gestión admin-only. Cambios surten efecto inmediato —
            desactivar un usuario lo desconecta en su próxima petición.
          </p>
        </div>
        <Link
          href="/settings"
          className="text-xs text-wcm-text/70 hover:text-wcm-accent"
        >
          ← Volver a Ajustes
        </Link>
      </header>

      <UsersManager initialUsers={users} forbidden={forbidden} />

      <p className="text-[10.5px] text-muted-foreground">
        Equivalente CLI:{" "}
        <code>wcm users list | create | set-role | deactivate | delete</code>
        . El password se genera aleatorio por defecto al crear (canal
        seguro para compartir, pedir cambio en primer login).
      </p>
    </div>
  );
}
