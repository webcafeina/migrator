"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Loader2, RotateCw, Rocket, ExternalLink, Pencil } from "lucide-react";

import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface PreviewPageInfo {
  slug: string;
  title: string;
  intent: string | null;
  n_sections: number;
  bricks_page_id: number | null;
  wp_post_id: number | null;
  wp_post_status: string | null;
  last_regenerated_at: string | null;
}

interface PreviewPanelProps {
  projectId: number;
  designMethod: string | null;
  brief: Record<string, unknown> | null;
  pages: PreviewPageInfo[];
  projectStatus: string;
}

/**
 * `<PreviewPanel>` — UI de revisión iterativa del rediseño (v0.25.1 B7).
 *
 * 3 capacidades:
 * 1. Listar páginas + botón "Regenerar página" por cada una.
 * 2. Modal "Editar Brief" (campos business_*) que dispara PATCH /brief.
 * 3. Botón "Aprobar y publicar" → POST /preview/approve.
 */
export function PreviewPanel({
  projectId,
  designMethod,
  brief,
  pages,
  projectStatus,
}: PreviewPanelProps) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [regenerating, setRegenerating] = useState<string | null>(null);
  const [editingBrief, setEditingBrief] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const business =
    (brief?.business as Record<string, unknown>) ?? ({} as Record<string, unknown>);

  function handleRegenerate(slug: string) {
    setError(null);
    setRegenerating(slug);
    startTransition(async () => {
      try {
        await api.post(`/api/v1/projects/${projectId}/preview/regenerate-page`, {
          slug,
        });
        router.refresh();
      } catch (e) {
        setError(
          e instanceof ApiError ? e.message : "Error regenerando página",
        );
      } finally {
        setRegenerating(null);
      }
    });
  }

  function handleApprove() {
    setError(null);
    if (!confirm("¿Aprobar el preview y publicar todas las páginas?")) return;
    startTransition(async () => {
      try {
        await api.post(`/api/v1/projects/${projectId}/preview/approve`);
        router.refresh();
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Error publicando");
      }
    });
  }

  return (
    <section className="space-y-4">
      {/* Header */}
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
            Preview · {pages.length} página{pages.length === 1 ? "" : "s"}
          </h2>
          <p className="mt-0.5 text-[10.5px] text-muted-foreground">
            Método de diseño:{" "}
            <strong className="text-wcm-text">
              {designMethod ?? "legacy"}
            </strong>
            {" · "}
            Estado proyecto:{" "}
            <strong className="text-wcm-text">{projectStatus}</strong>
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setEditingBrief(true)}
            className="inline-flex items-center gap-1.5 rounded-sm border border-wcm-detail/60 bg-wcm-secondary/40 px-3 py-1 text-[11px] hover:border-wcm-accent"
          >
            <Pencil className="h-3 w-3" aria-hidden />
            Editar Brief
          </button>
          <button
            type="button"
            onClick={handleApprove}
            disabled={pending}
            className="inline-flex items-center gap-1.5 rounded-sm bg-wcm-accent px-3 py-1 text-[11px] font-semibold text-wcm-primary hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Rocket className="h-3 w-3" aria-hidden />
            Aprobar y publicar
          </button>
        </div>
      </header>

      {/* Brief summary */}
      {brief && (
        <div className="rounded-sm border border-wcm-detail/40 bg-wcm-primary/40 p-3 text-[11px]">
          <div className="font-semibold text-wcm-text">
            {(business.name as string) ?? "Sin nombre"}
          </div>
          <div className="mt-1 text-muted-foreground">
            {(business.description as string) ?? (
              <em>Sin descripción del negocio.</em>
            )}
          </div>
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[10.5px] text-muted-foreground">
            <span>
              Sector: <strong className="text-wcm-text">{(business.sector as string) ?? "—"}</strong>
            </span>
            <span>
              Tono: <strong className="text-wcm-text">{(business.tone_of_voice as string) ?? "—"}</strong>
            </span>
            <span>
              Target:{" "}
              <strong className="text-wcm-text">
                {(business.target_audience as string) ?? "—"}
              </strong>
            </span>
          </div>
          {Array.isArray(business.usps) && (business.usps as string[]).length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {(business.usps as string[]).map((u) => (
                <span
                  key={u}
                  className="rounded-sm border border-wcm-accent/40 bg-wcm-accent/10 px-1.5 py-0.5 text-[9.5px] text-wcm-accent"
                >
                  {u}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="rounded-sm border border-wcm-danger/50 bg-wcm-danger/10 p-2 text-[11px] text-wcm-danger">
          {error}
        </div>
      )}

      {/* Lista de páginas */}
      {pages.length === 0 ? (
        <p className="text-[11px] italic text-muted-foreground">
          Sin páginas generadas todavía. Lanza el pipeline desde la vista
          principal del proyecto.
        </p>
      ) : (
        <ul className="space-y-2">
          {pages.map((page) => (
            <li
              key={page.slug}
              className="flex flex-wrap items-center gap-3 rounded-sm border border-wcm-detail/40 bg-wcm-secondary/20 p-3"
            >
              <div className="flex-1 text-xs">
                <div className="font-semibold text-wcm-text">
                  {page.title}
                  <span className="ml-2 text-[10px] font-normal text-muted-foreground">
                    /{page.slug}
                  </span>
                </div>
                <div className="mt-0.5 text-[10.5px] text-muted-foreground">
                  {page.intent && (
                    <>
                      intent:{" "}
                      <strong className="text-wcm-text/80">{page.intent}</strong>
                      {" · "}
                    </>
                  )}
                  {page.n_sections} secciones
                  {page.wp_post_id != null && (
                    <>
                      {" · "}
                      WP post:{" "}
                      <strong className="text-wcm-text/80">
                        #{page.wp_post_id}
                      </strong>
                    </>
                  )}
                  {page.last_regenerated_at && (
                    <>
                      {" · "}
                      regenerada{" "}
                      {new Date(page.last_regenerated_at).toLocaleString("es-ES", {
                        dateStyle: "short",
                        timeStyle: "short",
                      })}
                    </>
                  )}
                </div>
              </div>
              <div className="flex gap-1.5">
                <button
                  type="button"
                  onClick={() => handleRegenerate(page.slug)}
                  disabled={regenerating === page.slug || pending}
                  className="inline-flex items-center gap-1.5 rounded-sm border border-wcm-detail/60 bg-wcm-primary px-2 py-1 text-[10.5px] hover:border-wcm-accent disabled:cursor-not-allowed disabled:opacity-50"
                  title="Re-ejecuta el agente templates/AI para esta página"
                >
                  {regenerating === page.slug ? (
                    <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
                  ) : (
                    <RotateCw className="h-3 w-3" aria-hidden />
                  )}
                  Regenerar
                </button>
                {page.wp_post_id != null && (
                  <a
                    href={`/wp-admin/post.php?action=edit&post=${page.wp_post_id}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-sm border border-wcm-detail/60 bg-wcm-primary px-2 py-1 text-[10.5px] hover:border-wcm-accent"
                    title="Abrir editor Bricks en nueva pestaña"
                  >
                    <ExternalLink className="h-3 w-3" aria-hidden />
                    Editor
                  </a>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      <p className="text-[10px] text-muted-foreground">
        Tras editar el Brief o regenerar páginas, las páginas quedan en
        estado <strong>draft</strong> en WordPress. Usa{" "}
        <strong>Aprobar y publicar</strong> para pasarlas a publicadas.
      </p>

      {/* Modal editar Brief */}
      {editingBrief && (
        <EditBriefModal
          projectId={projectId}
          business={business}
          onClose={() => setEditingBrief(false)}
          onSaved={() => {
            setEditingBrief(false);
            router.refresh();
          }}
        />
      )}
    </section>
  );
}

interface EditBriefModalProps {
  projectId: number;
  business: Record<string, unknown>;
  onClose: () => void;
  onSaved: () => void;
}

function EditBriefModal({
  projectId,
  business,
  onClose,
  onSaved,
}: EditBriefModalProps) {
  const [description, setDescription] = useState(
    (business.description as string) ?? "",
  );
  const [sector, setSector] = useState((business.sector as string) ?? "");
  const [audience, setAudience] = useState(
    (business.target_audience as string) ?? "",
  );
  const [tone, setTone] = useState((business.tone_of_voice as string) ?? "");
  const [uspsInput, setUspsInput] = useState(
    Array.isArray(business.usps) ? (business.usps as string[]).join(", ") : "",
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const usps = uspsInput
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      await api.patch(`/api/v1/projects/${projectId}/brief`, {
        business_description: description || null,
        business_sector: sector || null,
        target_audience: audience || null,
        tone_of_voice: tone || null,
        usps_json: usps.length > 0 ? usps : null,
      });
      onSaved();
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Error guardando Brief",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-sm border border-wcm-detail/60 bg-wcm-secondary p-5 text-xs"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-sm font-semibold text-wcm-accent">
          Editar Brief — campos business
        </h3>
        <p className="mt-1 text-[10.5px] text-muted-foreground">
          Tras guardar, regenera las páginas afectadas para que los
          cambios se reflejen en el output.
        </p>
        <div className="mt-3 space-y-3">
          <label className="block">
            <span className="text-[11px] text-wcm-text/90">Descripción del negocio</span>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className={inputClass}
            />
          </label>
          <label className="block">
            <span className="text-[11px] text-wcm-text/90">Sector</span>
            <input
              type="text"
              value={sector}
              onChange={(e) => setSector(e.target.value)}
              className={inputClass}
            />
          </label>
          <label className="block">
            <span className="text-[11px] text-wcm-text/90">Audiencia objetivo</span>
            <textarea
              rows={2}
              value={audience}
              onChange={(e) => setAudience(e.target.value)}
              className={inputClass}
            />
          </label>
          <label className="block">
            <span className="text-[11px] text-wcm-text/90">Tono de voz</span>
            <select
              value={tone}
              onChange={(e) => setTone(e.target.value)}
              className={inputClass}
            >
              <option value="">— sin cambio —</option>
              <option value="formal">Formal</option>
              <option value="casual">Casual</option>
              <option value="friendly">Cercano / amigable</option>
              <option value="premium">Premium / lujo</option>
              <option value="playful">Lúdico</option>
              <option value="serious">Serio / profesional</option>
            </select>
          </label>
          <label className="block">
            <span className="text-[11px] text-wcm-text/90">USPs (CSV)</span>
            <input
              type="text"
              value={uspsInput}
              onChange={(e) => setUspsInput(e.target.value)}
              placeholder="Artesanal, Hecho a mano, Único"
              className={inputClass}
            />
          </label>
        </div>
        {error && (
          <p className="mt-3 rounded-sm border border-wcm-danger/50 bg-wcm-danger/10 p-2 text-[11px] text-wcm-danger">
            {error}
          </p>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="rounded-sm border border-wcm-detail/60 px-3 py-1 text-[11px] hover:border-wcm-detail disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-sm bg-wcm-accent px-3 py-1 text-[11px] font-semibold text-wcm-primary hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50",
            )}
          >
            {saving && <Loader2 className="h-3 w-3 animate-spin" aria-hidden />}
            Guardar
          </button>
        </div>
      </div>
    </div>
  );
}

const inputClass =
  "mt-1 h-8 w-full rounded-sm border border-wcm-detail/70 bg-wcm-primary px-2 text-xs text-wcm-text placeholder:text-muted-foreground focus:border-wcm-accent focus:outline-none";
