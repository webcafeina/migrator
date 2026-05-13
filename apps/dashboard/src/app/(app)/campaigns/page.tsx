import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LaunchCampaignForm } from "./launch-form";

export default function CampaignsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between">
        <h1 className="text-lg font-semibold">Campañas de prospección</h1>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Lanzar campaña</CardTitle>
          </CardHeader>
          <CardContent>
            <LaunchCampaignForm />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Notas</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-wcm-detail">
            <p>
              El sistema <span className="text-wcm-text">nunca</span> envía
              outreach automáticamente. La campaña descubre y enriquece
              leads. La aprobación del outreach es manual desde la página de
              cada lead.
            </p>
            <p>
              <span className="text-wcm-accent">ProspectorAgent</span> está
              actualmente en stub. La implementación real (Google Maps + dorks)
              llega en Fase 9. El endpoint encola la task; el worker la
              ejecuta cuando esté implementado.
            </p>
            <p>
              Una campaña típica produce 30-60 leads cualificados por
              sector+región en menos de 1 hora (objetivo MVP).
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
