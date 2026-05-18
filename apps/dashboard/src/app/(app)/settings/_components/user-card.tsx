import { formatDate } from "@/lib/utils";
import type { UserRead } from "@/types/api";

interface UserCardProps {
  user: UserRead | null;
}

/**
 * Card kv-densa con los datos del usuario logueado. Mismo lenguaje
 * visual que `ConfigPanel` de /projects/[id]: dl grid 2-col, fondo
 * `wcm-secondary/30`, sin Card de shadcn (más denso).
 */
export function UserCard({ user }: UserCardProps) {
  if (!user) {
    return (
      <div className="rounded-sm border border-wcm-danger/40 bg-wcm-danger/[0.05] p-4 text-xs text-wcm-text/80">
        No se pudo recuperar el usuario actual. La sesión podría haber
        expirado — recarga la página o vuelve a hacer login.
      </div>
    );
  }

  const rows: Array<[string, React.ReactNode]> = [
    ["email", user.email],
    ["nombre", user.name],
    ["rol", <RoleBadge key="r" role={user.role ?? "viewer"} />],
    ["activo", (user.is_active ?? false) ? "sí" : "no"],
    ["alta", formatDate(user.created_at)],
    ["id", <code key="i" className="text-[10.5px]">{user.id}</code>],
  ];

  return (
    <dl className="grid grid-cols-[80px_1fr] gap-x-3 gap-y-2 rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-4 text-xs">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-muted-foreground">{k}</dt>
          <dd className="break-all text-wcm-text">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function RoleBadge({ role }: { role: string }) {
  const cls =
    role === "admin"
      ? "border-wcm-accent/50 bg-wcm-accent/10 text-wcm-accent"
      : role === "operator"
        ? "border-wcm-detail/60 text-wcm-text/90"
        : "border-wcm-detail/60 text-muted-foreground";
  return (
    <span
      className={`inline-flex rounded-sm border px-1.5 text-[10px] uppercase tracking-wider ${cls}`}
    >
      {role}
    </span>
  );
}
