import { api } from "@/lib/api";
import type { UserRead } from "@/types/api";
import { ActiveCampaignsIndicator } from "./active-campaigns-indicator";
import { LogoutButton } from "./logout-button";

/**
 * Header server component. Llama a /auth/me con la cookie del request.
 * Si falla (401), middleware ya habría redirigido — pero por defensa
 * mostramos "—".
 */
export async function Header() {
  let user: UserRead | null = null;
  try {
    user = await api.get<UserRead>("/api/v1/auth/me");
  } catch {
    // No bloqueamos render; middleware se encarga de redirigir
  }

  // Entorno actual (dev | production). Sustituye al texto redundante
  // "Migrator dashboard" — el sidebar ya identifica el producto.
  const envLabel = process.env.NODE_ENV === "production" ? "prod" : "dev";
  const envIsProd = envLabel === "prod";

  return (
    <header className="flex h-12 items-center justify-between border-b border-wcm-detail bg-wcm-primary px-4">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
        <span
          aria-hidden
          className={
            envIsProd
              ? "h-1.5 w-1.5 rounded-full bg-wcm-warning shadow-[0_0_0_2px_rgba(255,171,0,0.18)]"
              : "h-1.5 w-1.5 rounded-full bg-[#5fc591] shadow-[0_0_0_2px_rgba(95,197,145,0.15)]"
          }
        />
        <span>entorno · {envLabel}</span>
      </div>

      <div className="flex items-center gap-3 text-sm">
        <ActiveCampaignsIndicator />
        {user ? (
          <>
            <span className="text-wcm-text">{user.email}</span>
            <span className="rounded-sm border border-wcm-accent/30 bg-wcm-accent/10 px-1.5 py-0.5 text-[10px] text-wcm-accent uppercase">
              {user.role}
            </span>
          </>
        ) : (
          <span className="text-wcm-detail">— · —</span>
        )}
        <LogoutButton />
      </div>
    </header>
  );
}
