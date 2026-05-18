"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";

import { ApiError, api } from "@/lib/api";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { UserRead } from "@/types/api";

interface UsersManagerProps {
  initialUsers: UserRead[];
  /** Forbidden si el usuario actual no es admin (el backend rechaza). */
  forbidden?: boolean;
}

type Role = "admin" | "operator" | "viewer";

/**
 * Pantalla admin-only de gestión de usuarios. Layout:
 * - Tabla de usuarios con role inline editable (select) + toggles
 *   activo/desactivar + botón borrar con confirmación.
 * - Botón "+ Crear usuario" abre dialog con form (email/name/role/
 *   password opcional). Si password se omite, el backend lo rechaza
 *   (>=12 chars) — el dialog genera uno aleatorio y lo muestra al
 *   creador.
 */
export function UsersManager({ initialUsers, forbidden }: UsersManagerProps) {
  const router = useRouter();
  const [users, setUsers] = useState<UserRead[]>(initialUsers);
  const [createOpen, setCreateOpen] = useState(false);
  const [pending, startTransition] = useTransition();

  if (forbidden) {
    return (
      <div className="rounded-sm border border-wcm-danger/40 bg-wcm-danger/[0.05] p-6 text-xs">
        <h2 className="text-sm font-semibold text-wcm-danger">
          Acceso restringido
        </h2>
        <p className="mt-2 text-wcm-text/80">
          Solo administradores pueden ver y gestionar usuarios. Si crees
          que deberías tener acceso, pídeselo al admin del equipo.
        </p>
      </div>
    );
  }

  function updateRole(user: UserRead, newRole: Role) {
    if (user.role === newRole) return;
    startTransition(async () => {
      try {
        const updated = await api.patch<UserRead>(
          `/api/v1/users/${user.id}`,
          { role: newRole },
        );
        setUsers((prev) =>
          prev.map((u) => (u.id === user.id ? updated : u)),
        );
        toast.success(`${updated.email} ahora es ${updated.role}`);
      } catch (err) {
        toast.error(
          err instanceof ApiError ? err.message : "Error al cambiar rol",
        );
      }
    });
  }

  function toggleActive(user: UserRead) {
    startTransition(async () => {
      try {
        const updated = await api.patch<UserRead>(
          `/api/v1/users/${user.id}`,
          { is_active: !user.is_active },
        );
        setUsers((prev) =>
          prev.map((u) => (u.id === user.id ? updated : u)),
        );
        toast.success(
          `${updated.email} ${updated.is_active ? "activado" : "desactivado"}`,
        );
      } catch (err) {
        toast.error(
          err instanceof ApiError ? err.message : "Error al cambiar estado",
        );
      }
    });
  }

  function deleteUser(user: UserRead) {
    const ok = window.confirm(
      `Borrar usuario ${user.email}? Acción IRREVERSIBLE. ` +
        "Si solo quieres bloquear acceso, mejor desactivar (es reversible).",
    );
    if (!ok) return;
    startTransition(async () => {
      try {
        await api.delete(`/api/v1/users/${user.id}`);
        setUsers((prev) => prev.filter((u) => u.id !== user.id));
        toast.success(`Usuario ${user.email} borrado`);
      } catch (err) {
        toast.error(
          err instanceof ApiError ? err.message : "Error al borrar",
        );
      }
    });
  }

  function addUser(newUser: UserRead, generatedPwd?: string) {
    setUsers((prev) => [newUser, ...prev]);
    if (generatedPwd) {
      toast.success(
        `Usuario ${newUser.email} creado · password generado: ${generatedPwd}`,
        { duration: 30000 },
      );
    } else {
      toast.success(`Usuario ${newUser.email} creado`);
    }
    setCreateOpen(false);
    router.refresh();
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
          Usuarios ({users.length})
        </h2>
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          disabled={pending}
          className="rounded-sm bg-wcm-accent px-2.5 py-1 text-xs font-semibold text-wcm-primary hover:brightness-105 disabled:opacity-50"
        >
          + Crear usuario
        </button>
      </header>

      {users.length === 0 ? (
        <div className="rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-6 text-center text-xs text-muted-foreground">
          Sin usuarios. Pulsa <strong>+ Crear usuario</strong> para
          añadir el primero.
        </div>
      ) : (
        <div className="overflow-hidden rounded-sm border border-wcm-detail/40">
          <table className="w-full border-collapse text-xs">
            <thead className="bg-wcm-secondary/40">
              <tr>
                <Th>Email</Th>
                <Th>Nombre</Th>
                <Th>Rol</Th>
                <Th>Activo</Th>
                <Th>Alta</Th>
                <Th>{" "}</Th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr
                  key={u.id}
                  className="border-t border-wcm-detail/40 hover:bg-wcm-secondary/30"
                >
                  <td className="px-3 py-2 font-mono text-[11.5px]">
                    {u.email}
                  </td>
                  <td className="px-3 py-2">{u.name}</td>
                  <td className="px-3 py-2">
                    <select
                      value={u.role ?? "viewer"}
                      onChange={(e) => updateRole(u, e.target.value as Role)}
                      disabled={pending}
                      className="h-7 rounded-sm border border-wcm-detail/70 bg-wcm-primary px-2 text-[11.5px] text-wcm-text focus:border-wcm-accent focus:outline-none disabled:opacity-50"
                    >
                      <option value="admin">admin</option>
                      <option value="operator">operator</option>
                      <option value="viewer">viewer</option>
                    </select>
                  </td>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      onClick={() => toggleActive(u)}
                      disabled={pending}
                      className={cn(
                        "inline-flex rounded-sm border px-2 py-0.5 text-[10.5px] uppercase tracking-wider transition-colors disabled:opacity-50",
                        u.is_active
                          ? "border-wcm-accent/50 bg-wcm-accent/10 text-wcm-accent hover:brightness-105"
                          : "border-wcm-detail/60 text-muted-foreground hover:border-wcm-text",
                      )}
                      title={u.is_active ? "Click para desactivar" : "Click para activar"}
                    >
                      {u.is_active ? "Sí" : "No"}
                    </button>
                  </td>
                  <td className="px-3 py-2 tabular-nums text-wcm-text/70">
                    {formatRelativeTime(u.created_at)}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      type="button"
                      onClick={() => deleteUser(u)}
                      disabled={pending}
                      className="rounded-sm border border-wcm-detail/60 px-2 py-0.5 text-[10.5px] text-wcm-danger hover:border-wcm-danger disabled:opacity-50"
                    >
                      Borrar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {createOpen && (
        <CreateUserDialog
          onCancel={() => setCreateOpen(false)}
          onCreated={addUser}
        />
      )}
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
      {children}
    </th>
  );
}

function CreateUserDialog({
  onCancel,
  onCreated,
}: {
  onCancel: () => void;
  onCreated: (user: UserRead, generatedPwd?: string) => void;
}) {
  const [pending, startTransition] = useTransition();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("operator");
  const [generatePwd, setGeneratePwd] = useState(true);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const pwd = generatePwd ? _genPassword() : password;
    if (pwd.length < 12) {
      setError("Password debe tener >= 12 caracteres.");
      return;
    }
    startTransition(async () => {
      try {
        const user = await api.post<UserRead>("/api/v1/users", {
          email,
          name,
          role,
          is_active: true,
          password: pwd,
        });
        onCreated(user, generatePwd ? pwd : undefined);
      } catch (err) {
        setError(
          err instanceof ApiError ? err.message : "Error al crear usuario",
        );
      }
    });
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      onClick={(e) => {
        if (e.target === e.currentTarget && !pending) onCancel();
      }}
    >
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md space-y-3 rounded-sm border border-wcm-accent/40 bg-wcm-primary p-5 text-xs"
      >
        <h3 className="text-sm font-semibold text-wcm-accent">
          Crear usuario nuevo
        </h3>
        <Field htmlFor="cu-email" label="Email *">
          <input
            id="cu-email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={pending}
            className={inputClass}
          />
        </Field>
        <Field htmlFor="cu-name" label="Nombre *">
          <input
            id="cu-name"
            type="text"
            required
            minLength={1}
            maxLength={120}
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={pending}
            className={inputClass}
          />
        </Field>
        <Field htmlFor="cu-role" label="Rol">
          <select
            id="cu-role"
            value={role}
            onChange={(e) => setRole(e.target.value as Role)}
            disabled={pending}
            className={inputClass}
          >
            <option value="admin">admin (gestión + observabilidad completa)</option>
            <option value="operator">operator (uso diario)</option>
            <option value="viewer">viewer (solo lectura)</option>
          </select>
        </Field>

        <label className="flex items-baseline gap-2 text-xs text-wcm-text/90">
          <input
            type="checkbox"
            checked={generatePwd}
            onChange={(e) => setGeneratePwd(e.target.checked)}
            disabled={pending}
            className="h-3.5 w-3.5 accent-wcm-accent"
          />
          Generar password aleatorio (recomendado)
        </label>

        {!generatePwd && (
          <Field htmlFor="cu-pwd" label="Password (>= 12 chars)">
            <input
              id="cu-pwd"
              type="password"
              minLength={12}
              maxLength={255}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={pending}
              className={inputClass}
            />
          </Field>
        )}

        {error && (
          <p className="text-[11px] text-wcm-danger">{error}</p>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={onCancel}
            disabled={pending}
            className="rounded-sm border border-wcm-detail/60 px-3 py-1 text-xs text-wcm-text/80 hover:border-wcm-detail disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={pending || !email || !name}
            className="rounded-sm bg-wcm-accent px-3 py-1 text-xs font-semibold text-wcm-primary hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "Creando…" : "Crear →"}
          </button>
        </div>
      </form>
    </div>
  );
}

const inputClass =
  "h-8 w-full rounded-sm border border-wcm-detail/70 bg-wcm-primary px-2 text-xs text-wcm-text placeholder:text-muted-foreground focus:border-wcm-accent focus:outline-none disabled:opacity-50";

function Field({
  htmlFor,
  label,
  children,
}: {
  htmlFor: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={htmlFor}
        className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground"
      >
        {label}
      </label>
      {children}
    </div>
  );
}

function _genPassword(length: number = 18): string {
  const alphabet =
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*-_=+";
  const arr = new Uint8Array(length);
  crypto.getRandomValues(arr);
  return Array.from(arr, (b) => alphabet[b % alphabet.length]!).join("");
}
