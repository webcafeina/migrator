import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { UserRead } from "@/types/api";

export default async function SettingsPage() {
  const me = await api.get<UserRead>("/api/v1/auth/me").catch(() => null);

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold">Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle>Usuario actual</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {me ? (
            <>
              <Row label="ID">{me.id}</Row>
              <Row label="Email">{me.email}</Row>
              <Row label="Nombre">{me.name}</Row>
              <Row label="Rol">{me.role}</Row>
              <Row label="Activo">{me.is_active ? "sí" : "no"}</Row>
              <Row label="Creado">{formatDate(me.created_at)}</Row>
            </>
          ) : (
            <p className="text-wcm-detail">No se pudo obtener el usuario.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Configuración del entorno</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-wcm-detail">
          <p>
            El dashboard es de solo lectura para la configuración. Las
            variables del sistema viven en <code>.env</code> en el servidor
            (permisos 600). Para editarlas:
          </p>
          <ol className="list-decimal pl-5 space-y-1">
            <li>
              SSH al servidor: <code>ssh root@migrator.webcafeina.com</code>
            </li>
            <li>
              Editar <code>/etc/webcafeina-migrator/env</code>
            </li>
            <li>
              Reload de los servicios:{" "}
              <code>systemctl restart webcafeina-api webcafeina-worker</code>
            </li>
          </ol>
          <p>
            Detalle completo del despliegue en{" "}
            <span className="text-wcm-text">docs/despliegue.md</span>.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Gestión de usuarios (admin)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-wcm-detail">
          <p>
            La gestión de usuarios (crear, eliminar, asignar roles) está
            disponible solo vía CLI <code>wcm users …</code> o directamente
            con SQL. UI de gestión: Fase 14.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-xs text-wcm-detail uppercase tracking-wider shrink-0">
        {label}
      </span>
      <span className="text-right text-wcm-text break-all">{children}</span>
    </div>
  );
}
