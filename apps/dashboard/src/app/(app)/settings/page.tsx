import Link from "next/link";

import { api } from "@/lib/api";
import type { UserRead } from "@/types/api";

import { OperationRunbook } from "./_components/operation-runbook";
import {
  SystemInfoPanel,
  type SystemInfoData,
} from "./_components/system-info-panel";
import { UserCard } from "./_components/user-card";

/**
 * `/settings` — Ajustes. Pantalla informativa: usuario actual, runtime
 * del API y runbook para operaciones que no viven en el dashboard
 * (editar .env, gestionar usuarios vía CLI).
 *
 * Server Component. Fetcha /auth/me + /system/info en paralelo con
 * `.catch()` defensivo — cualquier dependencia caída se refleja en su
 * componente correspondiente sin romper la página entera.
 */
export default async function SettingsPage() {
  const [user, info] = await Promise.all([
    api.get<UserRead>("/api/v1/auth/me").catch(() => null),
    api
      .get<SystemInfoData>("/api/v1/system/info")
      .catch(() => null),
  ]);

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-lg font-semibold text-wcm-text">Ajustes</h1>
        <p className="text-xs text-muted-foreground">
          Usuario actual, estado del API y procedimientos operativos.
          Solo lectura — las variables del sistema y los usuarios se
          gestionan en el servidor.
        </p>
      </header>

      <section className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_360px]">
        <div className="space-y-5">
          <Block title="Usuario actual">
            <UserCard user={user} />
          </Block>

          <Block title="Estado del sistema">
            <SystemInfoPanel info={info} />
          </Block>

          <Block title="Plantillas de contacto">
            <Link
              href="/settings/templates"
              className="block rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-4 text-xs text-wcm-text hover:border-wcm-accent hover:text-wcm-accent"
            >
              <div className="font-semibold">
                Gestionar plantillas Jinja2 →
              </div>
              <p className="mt-1 text-muted-foreground">
                Editar los borradores que el composer usa para generar
                los correos comerciales. Solo administradores pueden
                escribir.
              </p>
            </Link>
          </Block>
        </div>

        <aside>
          <Block title="Operación">
            <OperationRunbook />
          </Block>
        </aside>
      </section>
    </div>
  );
}

function Block({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <h2 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
        {title}
      </h2>
      {children}
    </div>
  );
}
