"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import {
  AlertTriangle,
  Image as ImageIcon,
  Loader2,
  RotateCw,
  Rocket,
  ExternalLink,
  Pencil,
  Sparkles,
} from "lucide-react";

import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";

import { RefinementPanel } from "./refinement-panel";

interface PreviewSectionInfo {
  type: string;
  design_method: string | null;
  has_ai_image: boolean;
  is_placeholder: boolean;
  asset_id: number | null;
  headline: string | null;
  // v0.27.0 B1
  asset_quality_score?: number | null;
  asset_quality_flags?: string[];
  asset_is_low_quality?: boolean;
}

interface PreviewPageInfo {
  slug: string;
  title: string;
  intent: string | null;
  n_sections: number;
  bricks_page_id: number | null;
  wp_post_id: number | null;
  wp_post_status: string | null;
  last_regenerated_at: string | null;
  // v0.26.0 nuevos opcionales
  preview_thumbnail_url?: string | null;
  preview_captured_at?: string | null;
  sections?: PreviewSectionInfo[];
}

interface PreviewPanelProps {
  projectId: number;
  designMethod: string | null;
  brief: Record<string, unknown> | null;
  pages: PreviewPageInfo[];
  projectStatus: string;
  // v0.26.0 — budget tracking IA images.
  imageGenerationCostUsd?: number;
  imageGenerationBudgetUsd?: number;
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
  imageGenerationCostUsd = 0,
  imageGenerationBudgetUsd = 1.0,
}: PreviewPanelProps) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [regenerating, setRegenerating] = useState<string | null>(null);
  const [regeneratingSection, setRegeneratingSection] = useState<string | null>(
    null,
  );
  const [editingBrief, setEditingBrief] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refinementOpen, setRefinementOpen] = useState(false);
  const [suggestingRefinements, setSuggestingRefinements] = useState(false);
  const budgetPct = imageGenerationBudgetUsd > 0
    ? Math.min(100, (imageGenerationCostUsd / imageGenerationBudgetUsd) * 100)
    : 0;

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

  function handleRegenerateSection(
    slug: string,
    sectionIndex: number,
    designMethodOverride?: string | null,
  ) {
    setError(null);
    const key = `${slug}::${sectionIndex}`;
    setRegeneratingSection(key);
    startTransition(async () => {
      try {
        await api.post(
          `/api/v1/projects/${projectId}/preview/regenerate-section`,
          {
            slug,
            section_index: sectionIndex,
            ...(designMethodOverride
              ? { design_method: designMethodOverride }
              : {}),
          },
        );
        router.refresh();
      } catch (e) {
        setError(
          e instanceof ApiError ? e.message : "Error regenerando sección",
        );
      } finally {
        setRegeneratingSection(null);
      }
    });
  }

  function handleRegenerateImage(slug: string, sectionIndex: number) {
    setError(null);
    const key = `${slug}::img::${sectionIndex}`;
    setRegeneratingSection(key);
    startTransition(async () => {
      try {
        await api.post(
          `/api/v1/projects/${projectId}/preview/regenerate-image`,
          { slug, section_index: sectionIndex },
        );
        router.refresh();
      } catch (e) {
        setError(
          e instanceof ApiError ? e.message : "Error regenerando imagen",
        );
      } finally {
        setRegeneratingSection(null);
      }
    });
  }

  function handleSuggestRefinements() {
    setError(null);
    if (
      !confirm(
        "Generar propuestas de mejora con AI tiene un coste estimado de "
          + "$0.10-0.50. ¿Continuar?",
      )
    )
      return;
    setSuggestingRefinements(true);
    startTransition(async () => {
      try {
        await api.post(
          `/api/v1/projects/${projectId}/brief/suggest-refinements`,
        );
        // Abrir panel; el panel hará fetch del estado actual y mostrará
        // las propuestas cuando la task termine (ProjectPoller refresca).
        setRefinementOpen(true);
        router.refresh();
      } catch (e) {
        setError(
          e instanceof ApiError ? e.message : "Error encolando refinement",
        );
      } finally {
        setSuggestingRefinements(false);
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
          {/* v0.27.0 B6 — Sugerir mejoras con AI. */}
          <button
            type="button"
            onClick={handleSuggestRefinements}
            disabled={pending || suggestingRefinements}
            className="inline-flex items-center gap-1.5 rounded-sm border border-wcm-accent/40 bg-wcm-accent/10 px-3 py-1 text-[11px] text-wcm-accent hover:bg-wcm-accent/20 disabled:cursor-not-allowed disabled:opacity-50"
            title="Genera propuestas de mejora del Brief con gpt-5 (~$0.10-0.50)"
          >
            {suggestingRefinements ? (
              <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
            ) : (
              <Sparkles className="h-3 w-3" aria-hidden />
            )}
            Sugerir mejoras (AI)
          </button>
          <button
            type="button"
            onClick={() => setRefinementOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-sm border border-wcm-detail/60 bg-wcm-secondary/40 px-3 py-1 text-[11px] hover:border-wcm-accent"
            title="Ver propuestas anteriores"
          >
            <Sparkles className="h-3 w-3" aria-hidden />
            ver propuestas
          </button>
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

      {/* v0.26.0 — Budget tracking de imágenes IA. */}
      {imageGenerationCostUsd > 0 && (
        <div className="rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-2 text-[10.5px]">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">
              <Sparkles className="mr-1 inline h-3 w-3 text-wcm-accent" aria-hidden />
              Imágenes IA — coste{" "}
              <strong className="text-wcm-text">
                ${imageGenerationCostUsd.toFixed(4)}
              </strong>{" "}
              / ${imageGenerationBudgetUsd.toFixed(2)} budget
            </span>
            <span className={cn(
              "tabular-nums",
              budgetPct >= 80 ? "text-wcm-warning" : "text-muted-foreground",
            )}>
              {budgetPct.toFixed(0)}%
            </span>
          </div>
          <div className="mt-1 h-1 w-full overflow-hidden rounded-sm bg-wcm-primary">
            <div
              className={cn(
                "h-full transition-all",
                budgetPct >= 100 ? "bg-wcm-danger"
                : budgetPct >= 80 ? "bg-wcm-warning"
                : "bg-wcm-accent",
              )}
              style={{ width: `${Math.min(budgetPct, 100)}%` }}
            />
          </div>
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
        <ul className="space-y-3">
          {pages.map((page) => (
            <li
              key={page.slug}
              className="rounded-sm border border-wcm-detail/40 bg-wcm-secondary/20 p-3"
            >
              <div className="flex flex-wrap items-start gap-3">
                {/* v0.26.0 B6 — Thumbnail Playwright sobre WP draft. */}
                {page.preview_thumbnail_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={page.preview_thumbnail_url}
                    alt={`Preview ${page.title}`}
                    className="h-24 w-40 shrink-0 rounded-sm border border-wcm-detail/60 object-cover"
                  />
                ) : (
                  <div className="flex h-24 w-40 shrink-0 items-center justify-center rounded-sm border border-dashed border-wcm-detail/40 bg-wcm-primary/40 text-[10px] text-muted-foreground">
                    Sin thumbnail
                  </div>
                )}

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

                <div className="flex flex-shrink-0 gap-1.5">
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
              </div>

              {/* v0.26.0 B7 — Secciones de la página con editor inline. */}
              {page.sections && page.sections.length > 0 && (
                <ul className="mt-2 space-y-1 border-t border-wcm-detail/30 pt-2">
                  {page.sections.map((section, idx) => (
                    <SectionRow
                      key={`${page.slug}-${idx}`}
                      section={section}
                      slug={page.slug}
                      index={idx}
                      pending={pending}
                      regeneratingKey={regeneratingSection}
                      onRegenerateSection={handleRegenerateSection}
                      onRegenerateImage={handleRegenerateImage}
                    />
                  ))}
                </ul>
              )}
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

      {/* v0.27.0 B6 — Panel lateral de propuestas refinement. */}
      {refinementOpen && (
        <RefinementPanel
          projectId={projectId}
          onClose={() => setRefinementOpen(false)}
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


interface SectionRowProps {
  section: PreviewSectionInfo;
  slug: string;
  index: number;
  pending: boolean;
  regeneratingKey: string | null;
  onRegenerateSection: (
    slug: string,
    index: number,
    designMethod?: string | null,
  ) => void;
  onRegenerateImage: (slug: string, index: number) => void;
}

/**
 * Fila por sección dentro de una página del preview. Muestra type +
 * design_method (con dropdown override) + acción regenerar sección /
 * regenerar imagen IA si aplica.
 */
function SectionRow({
  section,
  slug,
  index,
  pending,
  regeneratingKey,
  onRegenerateSection,
  onRegenerateImage,
}: SectionRowProps) {
  const sectionKey = `${slug}::${index}`;
  const imageKey = `${slug}::img::${index}`;
  const isRegenSection = regeneratingKey === sectionKey;
  const isRegenImage = regeneratingKey === imageKey;

  return (
    <li className="flex flex-wrap items-center gap-2 text-[10.5px]">
      <span className="rounded-sm border border-wcm-detail/40 bg-wcm-primary px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
        #{index}
      </span>
      <span className="font-mono text-wcm-text">{section.type}</span>
      {section.headline && (
        <span className="truncate text-muted-foreground" style={{ maxWidth: 200 }}>
          — {section.headline}
        </span>
      )}
      {section.has_ai_image && (
        <span
          className="inline-flex items-center gap-1 rounded-sm border border-wcm-accent/40 bg-wcm-accent/10 px-1 text-[9.5px] text-wcm-accent"
          title="Imagen generada por gpt-image-2"
        >
          <Sparkles className="h-2.5 w-2.5" aria-hidden />
          imagen IA
        </span>
      )}
      {/* v0.27.0 B1 — badge calidad baja en imagen del origen. */}
      {section.asset_is_low_quality && !section.has_ai_image && (
        <span
          className="inline-flex items-center gap-1 rounded-sm border border-wcm-warning/40 bg-wcm-warning/10 px-1 text-[9.5px] text-wcm-warning"
          title={
            "Calidad baja detectada · flags: " +
            (section.asset_quality_flags ?? []).join(", ") +
            ` · score ${section.asset_quality_score?.toFixed(2) ?? "?"} ` +
            "· puedes regenerar con IA"
          }
        >
          <AlertTriangle className="h-2.5 w-2.5" aria-hidden />
          calidad baja
        </span>
      )}
      <select
        value={section.design_method ?? ""}
        onChange={(e) =>
          onRegenerateSection(slug, index, e.target.value || null)
        }
        disabled={pending}
        className="h-6 rounded-sm border border-wcm-detail/70 bg-wcm-primary px-1 text-[10px] text-wcm-text focus:border-wcm-accent focus:outline-none disabled:opacity-50"
        title="Cambiar método y regenerar"
      >
        <option value="">— heredar —</option>
        <option value="templates">templates</option>
        <option value="ai">ai</option>
      </select>
      <button
        type="button"
        onClick={() => onRegenerateSection(slug, index)}
        disabled={isRegenSection || pending}
        className="inline-flex items-center gap-1 rounded-sm border border-wcm-detail/60 bg-wcm-primary px-1.5 py-0.5 text-[10px] hover:border-wcm-accent disabled:cursor-not-allowed disabled:opacity-50"
        title="Regenerar SOLO esta sección"
      >
        {isRegenSection ? (
          <Loader2 className="h-2.5 w-2.5 animate-spin" aria-hidden />
        ) : (
          <RotateCw className="h-2.5 w-2.5" aria-hidden />
        )}
        sección
      </button>
      {(section.has_ai_image || section.asset_is_low_quality) && (
        <button
          type="button"
          onClick={() => onRegenerateImage(slug, index)}
          disabled={isRegenImage || pending}
          className="inline-flex items-center gap-1 rounded-sm border border-wcm-detail/60 bg-wcm-primary px-1.5 py-0.5 text-[10px] hover:border-wcm-accent disabled:cursor-not-allowed disabled:opacity-50"
          title={
            section.has_ai_image
              ? "Regenerar la imagen IA de esta sección"
              : "Generar imagen IA en sustitución del origen (calidad baja)"
          }
        >
          {isRegenImage ? (
            <Loader2 className="h-2.5 w-2.5 animate-spin" aria-hidden />
          ) : (
            <ImageIcon className="h-2.5 w-2.5" aria-hidden />
          )}
          imagen
        </button>
      )}
    </li>
  );
}
