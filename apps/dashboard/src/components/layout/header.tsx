import { LogOut } from "lucide-react";
import { api } from "@/lib/api";
import type { UserRead } from "@/types/api";
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

  return (
    <header className="flex h-12 items-center justify-between border-b border-wcm-detail bg-wcm-primary px-4">
      <div className="text-xs text-wcm-detail uppercase tracking-wider">
        Migrator dashboard
      </div>

      <div className="flex items-center gap-3 text-sm">
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
