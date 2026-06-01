"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { ArrowLeft, ArrowRight, Check, Loader2, Rocket } from "lucide-react";

import { ApiError, api } from "@/lib/api";
import { eurToUsd, formatUsd } from "@/lib/currency";
import { cn } from "@/lib/utils";
import type { LeadRead, PreflightResult, ProjectRead } from "@/types/api";

import { PreflightDisplay } from "./preflight-display";

interface NewProjectWizardProps {
  /** Lead opcional para pre-rellenar URL + builder + nombre cliente. */
  initialLead: LeadRead | null;
}

type StepKey = "origen" | "business" | "design" | "destino" | "features" | "preflight";

const STEPS: Array<{ key: StepKey; label: string; short: string }> = [
  { key: "origen", label: "Origen + credenciales (opcional)", short: "1 · Origen" },
  { key: "business", label: "Sobre el negocio (v0.25.0)", short: "2 · Negocio" },
  { key: "design", label: "Método de diseño (v0.25.0)", short: "3 · Diseño" },
  { key: "destino", label: "Destino y dominio", short: "4 · Destino" },
  { key: "features", label: "Features del proyecto", short: "5 · Features" },
  { key: "preflight", label: "Comprobación y arranque", short: "6 · Arranque" },
];

/**
 * Wizard onboarding de creación de proyecto (v0.18.0).
 *
 * 4 pasos con stepper superior. El proyecto se CREA al pasar de paso 3
 * a paso 4 (para poder ejecutar preflight contra él); si el operador
 * cancela en paso 4, el proyecto queda en BD con status=queued y puede
 * retomarse desde /projects/{id}.
 *
 * Reactividad: state propio (sin librería). Cada paso valida sus campos
 * antes de permitir avanzar (Next disabled si falta algo).
 */
export function NewProjectWizard({ initialLead }: NewProjectWizardProps) {
  const router = useRouter();
  const [step, setStep] = useState<StepKey>("origen");
  const [pending, startTransition] = useTransition();

  // --- Paso 1: Origen ---
  const [sourceUrl, setSourceUrl] = useState(initialLead?.url ?? "");
  const [clientName, setClientName] = useState(
    initialLead?.business_name ?? "",
  );
  const initialBuilder = initialLead?.builder_detected ?? "";
  const [builder, setBuilder] = useState<string>(
    initialBuilder !== "unknown" ? initialBuilder : "",
  );
  const [provideSourceCreds, setProvideSourceCreds] = useState(false);
  const [wixApiKey, setWixApiKey] = useState("");
  const [wixSiteId, setWixSiteId] = useState("");
  const [webflowApiToken, setWebflowApiToken] = useState("");
  const [webflowSiteId, setWebflowSiteId] = useState("");

  // --- Paso 2 v0.25.0: Sobre el negocio ---
  const [businessDescription, setBusinessDescription] = useState("");
  const [businessSector, setBusinessSector] = useState("");
  const [targetAudience, setTargetAudience] = useState("");
  const [toneOfVoice, setToneOfVoice] = useState("");
  const [uspsInput, setUspsInput] = useState(""); // CSV editable

  // --- Paso 3 v0.25.0: Método de diseño ---
  const [designMethod, setDesignMethod] = useState<"templates" | "ai" | "">("");
  // v0.27.0 — Budget gpt-image-2 (input en EUR, persistencia en USD).
  // Default 0.90 EUR ≈ 1.00 USD (default backend si no se setea).
  const [imageBudgetEur, setImageBudgetEur] = useState<string>("0.90");

  // --- Paso 4: Destino ---
  const [targetDomain, setTargetDomain] = useState("");

  // --- Paso 3: Features ---
  const [hasEcommerce, setHasEcommerce] = useState(false);
  const [isMultilang, setIsMultilang] = useState(false);
  const [preservePaths, setPreservePaths] = useState(true);

  // --- Paso 4: Preflight ---
  const [projectId, setProjectId] = useState<number | null>(null);
  const [preflight, setPreflight] = useState<PreflightResult | null>(null);
  const [preflightLoading, setPreflightLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const stepIdx = STEPS.findIndex((s) => s.key === step);

  // Validaciones por paso.
  const canAdvanceOrigen =
    sourceUrl.trim() !== "" &&
    clientName.trim() !== "" &&
    /^https?:\/\//.test(sourceUrl.trim());
  // v0.25.0 — `business` puede avanzar SIEMPRE (campos vacíos los infiere
  // BriefGenerator vía OpenAI; operador puede saltarlos). `design` puede
  // avanzar SIEMPRE (default templates si vacío).
  const canAdvanceBusiness = true;
  const canAdvanceDesign = true;
  const canAdvanceDestino = targetDomain.trim() !== "";
  const canAdvanceFeatures = true;
  const canStart = preflight?.can_start === true && !pending;

  function goTo(next: StepKey) {
    setError(null);
    setStep(next);
  }

  async function handleCreateAndPreflight() {
    setError(null);
    setPreflightLoading(true);
    try {
      // 1. Crear proyecto.
      const body: Record<string, unknown> = {
        client_name: clientName.trim(),
        source_url: sourceUrl.trim(),
        target_domain: targetDomain.trim(),
        has_ecommerce: hasEcommerce,
        is_multilang: isMultilang,
        preserve_paths: preservePaths,
      };
      if (builder && builder !== "unknown") body.builder_source = builder;
      if (initialLead) body.lead_id = initialLead.id;

      // v0.25.0 — Brief fields + design_method.
      if (businessDescription.trim())
        body.business_description = businessDescription.trim();
      if (businessSector) body.business_sector = businessSector;
      if (targetAudience.trim())
        body.target_audience = targetAudience.trim();
      if (toneOfVoice) body.tone_of_voice = toneOfVoice;
      const uspsList = uspsInput
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      if (uspsList.length > 0) body.usps_json = uspsList;
      if (designMethod) body.design_method = designMethod;
      // v0.27.0 — Budget gpt-image-2: convertir EUR → USD para BD.
      const budgetEurNum = Number.parseFloat(imageBudgetEur);
      if (Number.isFinite(budgetEurNum) && budgetEurNum > 0) {
        body.image_generation_budget_usd = Number(
          eurToUsd(budgetEurNum).toFixed(2),
        );
      }

      const proj = await api.post<ProjectRead>("/api/v1/projects", body);
      setProjectId(proj.id);

      // 2. Si hay credenciales del back, guardar (admin-only).
      if (provideSourceCreds && (builder === "wix" || builder === "webflow")) {
        try {
          const credBody: Record<string, unknown> = { builder };
          if (builder === "wix") {
            credBody.api_key = wixApiKey;
            credBody.site_id = wixSiteId;
          } else {
            credBody.api_token = webflowApiToken;
            credBody.site_id = webflowSiteId;
          }
          await api.put(`/api/v1/projects/${proj.id}/source-credentials`, credBody);
        } catch (err) {
          // No bloqueamos: el operador puede no ser admin.
          console.warn("Credenciales del origen no guardadas:", err);
        }
      }

      // 3. Ejecutar preflight.
      const result = await api.post<PreflightResult>(
        `/api/v1/projects/${proj.id}/preflight`,
      );
      setPreflight(result);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Error creando o preflighteando",
      );
    } finally {
      setPreflightLoading(false);
    }
  }

  function handleStart() {
    if (!projectId) return;
    setError(null);
    startTransition(async () => {
      try {
        await api.post(`/api/v1/projects/${projectId}/start`);
        router.push(`/projects/${projectId}`);
      } catch (err) {
        setError(
          err instanceof ApiError ? err.message : "Error arrancando pipeline",
        );
      }
    });
  }

  function handleSaveAndExit() {
    if (!projectId) return;
    router.push(`/projects/${projectId}`);
  }

  return (
    <div className="space-y-5">
      {/* Stepper superior. */}
      <ol className="flex gap-1 overflow-x-auto pb-2" aria-label="Pasos del wizard">
        {STEPS.map((s, i) => {
          const isDone = i < stepIdx;
          const isActive = i === stepIdx;
          return (
            <li
              key={s.key}
              className="flex min-w-[110px] flex-1 items-center gap-2 px-1.5"
              aria-current={isActive ? "step" : undefined}
            >
              <span
                className={cn(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 text-[10px] font-semibold",
                  isDone
                    ? "border-wcm-accent bg-wcm-accent/15 text-wcm-accent"
                    : isActive
                      ? "border-wcm-accent bg-wcm-accent text-wcm-primary shadow-[0_0_0_4px_rgba(177,241,0,0.18)]"
                      : "border-wcm-detail/60 bg-wcm-secondary/30 text-muted-foreground",
                )}
              >
                {isDone ? <Check className="h-3 w-3" aria-hidden /> : i + 1}
              </span>
              <span
                className={cn(
                  "text-[10.5px] uppercase tracking-wider",
                  isActive ? "font-semibold text-wcm-text" : "text-muted-foreground",
                )}
              >
                {s.short}
              </span>
            </li>
          );
        })}
      </ol>

      {/* Contenido del paso activo. */}
      <div className="rounded-sm border border-wcm-detail/40 bg-wcm-secondary/20 p-5">
        <h2 className="text-sm font-semibold text-wcm-accent">
          {STEPS[stepIdx]?.label}
        </h2>

        {step === "origen" && (
          <div className="mt-4 space-y-3">
            <Field htmlFor="w-url" label="URL del origen *">
              <input
                id="w-url"
                type="url"
                required
                placeholder="https://miweb.com"
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field htmlFor="w-client" label="Nombre del cliente *">
              <input
                id="w-client"
                type="text"
                required
                value={clientName}
                onChange={(e) => setClientName(e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field htmlFor="w-builder" label="Builder origen (opcional)">
              <select
                id="w-builder"
                value={builder}
                onChange={(e) => setBuilder(e.target.value)}
                className={inputClass}
              >
                <option value="">— sin determinar (lo detecta el pipeline) —</option>
                <option value="wix">Wix</option>
                <option value="webflow">Webflow</option>
                <option value="hostinger_ai">Hostinger AI</option>
                <option value="wordpress">WordPress</option>
                <option value="squarespace">Squarespace</option>
                <option value="shopify">Shopify</option>
                <option value="other">Otro</option>
              </select>
            </Field>

            {(builder === "wix" || builder === "webflow") && (
              <div className="rounded-sm border border-wcm-detail/40 bg-wcm-primary/40 p-3">
                <label className="flex items-baseline gap-2 text-xs text-wcm-text/90">
                  <input
                    type="checkbox"
                    checked={provideSourceCreds}
                    onChange={(e) => setProvideSourceCreds(e.target.checked)}
                    className="h-3.5 w-3.5 cursor-pointer accent-wcm-accent"
                  />
                  <span>
                    El cliente nos dio acceso al back ({builder}) — quiero
                    introducir credenciales API para mejorar el scraping
                  </span>
                </label>
                {provideSourceCreds && builder === "wix" && (
                  <div className="mt-3 space-y-2">
                    <Field htmlFor="w-wix-key" label="Wix API key">
                      <input
                        id="w-wix-key"
                        type="password"
                        value={wixApiKey}
                        onChange={(e) => setWixApiKey(e.target.value)}
                        className={inputClass}
                        autoComplete="off"
                      />
                    </Field>
                    <Field htmlFor="w-wix-site" label="Wix site_id">
                      <input
                        id="w-wix-site"
                        type="text"
                        value={wixSiteId}
                        onChange={(e) => setWixSiteId(e.target.value)}
                        className={inputClass}
                      />
                    </Field>
                  </div>
                )}
                {provideSourceCreds && builder === "webflow" && (
                  <div className="mt-3 space-y-2">
                    <Field htmlFor="w-wf-token" label="Webflow API token">
                      <input
                        id="w-wf-token"
                        type="password"
                        value={webflowApiToken}
                        onChange={(e) => setWebflowApiToken(e.target.value)}
                        className={inputClass}
                        autoComplete="off"
                      />
                    </Field>
                    <Field htmlFor="w-wf-site" label="Webflow site_id">
                      <input
                        id="w-wf-site"
                        type="text"
                        value={webflowSiteId}
                        onChange={(e) => setWebflowSiteId(e.target.value)}
                        className={inputClass}
                      />
                    </Field>
                  </div>
                )}
                <p className="mt-2 text-[10.5px] text-muted-foreground">
                  Las credenciales se cifran (Fernet) antes de guardarse.
                  Solo admin puede introducirlas.
                </p>
              </div>
            )}
          </div>
        )}

        {step === "business" && (
          <div className="mt-4 space-y-3">
            <p className="text-xs text-muted-foreground">
              Los campos vacíos los inferirá la IA (gpt-4o-mini ~$0.01) cuando
              corra `BriefGenerator`. Edítalos manualmente si prefieres
              control directo o si la IA no acierta.
            </p>
            <Field htmlFor="w-bdesc" label="Descripción del negocio (2-4 frases)">
              <textarea
                id="w-bdesc"
                rows={3}
                value={businessDescription}
                onChange={(e) => setBusinessDescription(e.target.value)}
                placeholder="Estudio de diseño de joyería artesanal en Madrid…"
                className={inputClass}
              />
            </Field>
            <Field htmlFor="w-bsector" label="Sector">
              <select
                id="w-bsector"
                value={businessSector}
                onChange={(e) => setBusinessSector(e.target.value)}
                className={inputClass}
              >
                <option value="">— auto-detectar con IA —</option>
                <option value="restaurant">Restaurante / Hostelería</option>
                <option value="agency">Agencia creativa / diseño</option>
                <option value="consulting">Consultoría</option>
                <option value="services">Servicios profesionales</option>
                <option value="ecommerce">E-commerce</option>
                <option value="portfolio">Portfolio / artista</option>
                <option value="fitness">Fitness / deporte</option>
                <option value="hotel">Hotel / alojamiento</option>
                <option value="healthcare">Salud / clínica</option>
                <option value="legal">Legal / abogados</option>
                <option value="education">Educación / formación</option>
                <option value="realestate">Inmobiliaria</option>
                <option value="beauty">Belleza / estética</option>
                <option value="automotive">Automoción</option>
                <option value="other">Otro</option>
              </select>
            </Field>
            <Field htmlFor="w-audience" label="Audiencia objetivo (1-2 frases)">
              <textarea
                id="w-audience"
                rows={2}
                value={targetAudience}
                onChange={(e) => setTargetAudience(e.target.value)}
                placeholder="Mujeres 35-55 con poder adquisitivo alto…"
                className={inputClass}
              />
            </Field>
            <Field htmlFor="w-tone" label="Tono de voz">
              <select
                id="w-tone"
                value={toneOfVoice}
                onChange={(e) => setToneOfVoice(e.target.value)}
                className={inputClass}
              >
                <option value="">— auto-detectar con IA —</option>
                <option value="formal">Formal</option>
                <option value="casual">Casual</option>
                <option value="friendly">Cercano / amigable</option>
                <option value="premium">Premium / lujo</option>
                <option value="playful">Lúdico / divertido</option>
                <option value="serious">Serio / profesional</option>
              </select>
            </Field>
            <Field htmlFor="w-usps" label="USPs (separados por coma, 3-5)">
              <input
                id="w-usps"
                type="text"
                value={uspsInput}
                onChange={(e) => setUspsInput(e.target.value)}
                placeholder="Joyería artesanal, Piezas únicas, Diseños exclusivos"
                className={inputClass}
              />
            </Field>
          </div>
        )}

        {step === "design" && (
          <div className="mt-4 space-y-3">
            <p className="text-xs text-muted-foreground">
              Cómo se construirá visualmente la web rediseñada. v0.26.0
              recomienda <strong>Híbrido</strong>: la heurística decide
              por sección (hero/cta = AI generativo, features/services =
              templates curados). Puedes sobreescribir por sección desde{" "}
              <code className="text-wcm-text/80">/preview</code>.
            </p>
            <div className="space-y-2">
              {/* v0.26.0 — Híbrido (default, design_method=null). */}
              <label
                className={cn(
                  "flex cursor-pointer items-start gap-3 rounded-sm border-2 p-3",
                  designMethod === ""
                    ? "border-wcm-accent bg-wcm-accent/10"
                    : "border-wcm-detail/40 bg-wcm-primary/40 hover:border-wcm-detail",
                )}
              >
                <input
                  type="radio"
                  name="w-design"
                  value=""
                  checked={designMethod === ""}
                  onChange={() => setDesignMethod("")}
                  className="mt-1 h-3.5 w-3.5 cursor-pointer accent-wcm-accent"
                />
                <div className="flex-1 text-xs">
                  <div className="font-semibold text-wcm-text">
                    ⚖️ Híbrido (recomendado, v0.26.0)
                  </div>
                  <div className="text-muted-foreground">
                    Hero + CTAs con <strong>AI generativo</strong> (OpenAI
                    gpt-5, ~$0.05-0.30 por sección). Features, services,
                    testimonios, etc. con <strong>templates curados</strong>{" "}
                    de brickstemplate.com (gratis). Override por sección en
                    el preview. Coste típico: $1-5/proyecto.
                  </div>
                </div>
              </label>
              <label
                className={cn(
                  "flex cursor-pointer items-start gap-3 rounded-sm border-2 p-3",
                  designMethod === "templates"
                    ? "border-wcm-accent bg-wcm-accent/10"
                    : "border-wcm-detail/40 bg-wcm-primary/40 hover:border-wcm-detail",
                )}
              >
                <input
                  type="radio"
                  name="w-design"
                  value="templates"
                  checked={designMethod === "templates"}
                  onChange={() => setDesignMethod("templates")}
                  className="mt-1 h-3.5 w-3.5 cursor-pointer accent-wcm-accent"
                />
                <div className="flex-1 text-xs">
                  <div className="font-semibold text-wcm-text">
                    🎨 Templates puro (sin AI, gratis)
                  </div>
                  <div className="text-muted-foreground">
                    Todas las secciones con templates de brickstemplate.com.
                    Sin llamadas API. Calidad consistente pero menos
                    diferenciado. Sin imágenes IA en hero (slots vacíos
                    quedan como ResidualTask).
                  </div>
                </div>
              </label>
              <label
                className={cn(
                  "flex cursor-pointer items-start gap-3 rounded-sm border-2 p-3",
                  designMethod === "ai"
                    ? "border-wcm-accent bg-wcm-accent/10"
                    : "border-wcm-detail/40 bg-wcm-primary/40 hover:border-wcm-detail",
                )}
              >
                <input
                  type="radio"
                  name="w-design"
                  value="ai"
                  checked={designMethod === "ai"}
                  onChange={() => setDesignMethod("ai")}
                  className="mt-1 h-3.5 w-3.5 cursor-pointer accent-wcm-accent"
                />
                <div className="flex-1 text-xs">
                  <div className="font-semibold text-wcm-text">
                    🤖 AI puro (OpenAI gpt-5)
                  </div>
                  <div className="text-muted-foreground">
                    Todas las páginas generadas con gpt-5 (call por
                    página entera). Más caro y con más variabilidad que
                    híbrido. Coste estimado: <strong>$3-15 por proyecto</strong>.
                    Requiere <code className="text-wcm-text/80">OPENAI_API_KEY</code>.
                  </div>
                </div>
              </label>
            </div>

            {/* v0.27.0 — Budget gpt-image-2 (input EUR, persistencia USD). */}
            <div className="mt-4 rounded-sm border border-wcm-detail/40 bg-wcm-primary/40 p-3">
              <Field
                htmlFor="w-image-budget"
                label="Presupuesto imágenes IA (€)"
              >
                <div className="flex items-center gap-2">
                  <input
                    id="w-image-budget"
                    type="number"
                    min="0.10"
                    max="90"
                    step="0.10"
                    value={imageBudgetEur}
                    onChange={(e) => setImageBudgetEur(e.target.value)}
                    className={cn(inputClass, "w-32 text-right")}
                  />
                  <span className="text-xs text-muted-foreground">€</span>
                  <span className="text-[10.5px] text-muted-foreground">
                    ≈ {(() => {
                      const eur = Number.parseFloat(imageBudgetEur);
                      if (!Number.isFinite(eur) || eur <= 0)
                        return "$? USD";
                      return formatUsd(eurToUsd(eur));
                    })()}{" "}
                    USD <em>(lo que factura OpenAI)</em>
                  </span>
                </div>
                <p className="mt-1 text-[10.5px] text-muted-foreground">
                  Límite duro de gasto en <code className="text-wcm-text/80">gpt-image-2</code>{" "}
                  para rellenar slots de imagen vacíos en hero/image/gallery/testimonial.
                  Cada imagen medium 1024×1024 ≈ $0.05. <strong>Default 0.90 €</strong>{" "}
                  ≈ $1.00 (cubre ~20 imágenes). Si se supera, los slots restantes
                  quedan como ResidualTask.
                </p>
              </Field>
            </div>
          </div>
        )}

        {step === "destino" && (
          <div className="mt-4 space-y-3">
            <Field htmlFor="w-target" label="Dominio destino (WordPress) *">
              <input
                id="w-target"
                type="text"
                required
                placeholder="migracion-cliente.webcafeina.com"
                value={targetDomain}
                onChange={(e) => setTargetDomain(e.target.value)}
                className={inputClass}
              />
            </Field>
            <p className="text-[11.5px] text-muted-foreground">
              El WP destino se configura vía env vars{" "}
              <code className="text-wcm-text">WP_DEFAULT_*</code> (SITE_URL,
              REST_USER, REST_APP_PASSWORD, HOST, SSH_USER, SSH_KEY_PATH).
              En el paso 4 verificaremos REST + SSH automáticamente.
            </p>
          </div>
        )}

        {step === "features" && (
          <div className="mt-4 space-y-2">
            <Checkbox
              id="w-ecom"
              checked={hasEcommerce}
              onChange={setHasEcommerce}
              label="Tiene tienda online (activa WooCommerce)"
            />
            <Checkbox
              id="w-multi"
              checked={isMultilang}
              onChange={setIsMultilang}
              label="Multilang (activa configuración WPML — requiere licencia)"
            />
            <Checkbox
              id="w-paths"
              checked={preservePaths}
              onChange={setPreservePaths}
              label="Preservar paths origen → destino (recomendado para SEO)"
            />
          </div>
        )}

        {step === "preflight" && (
          <div className="mt-4 space-y-4">
            {!preflight && !preflightLoading && (
              <div className="space-y-3">
                <p className="text-[11.5px] text-wcm-text/90">
                  Pulsa el botón para crear el proyecto y ejecutar los 4 chequeos.
                  Tarda ~10 segundos. Si todos pasan podrás arrancar el pipeline
                  directamente.
                </p>
                <button
                  type="button"
                  onClick={handleCreateAndPreflight}
                  disabled={preflightLoading || projectId !== null}
                  className="rounded-sm bg-wcm-accent px-3 py-1.5 text-xs font-semibold text-wcm-primary hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Crear proyecto y ejecutar preflight →
                </button>
              </div>
            )}
            {preflightLoading && (
              <div className="flex items-center gap-2 text-xs text-wcm-text/80">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-wcm-accent" aria-hidden />
                Ejecutando los 4 chequeos (≤10s)…
              </div>
            )}
            {preflight && (
              <>
                <PreflightDisplay
                  wpTarget={preflight.wp_target}
                  plugins={preflight.plugins}
                  source={preflight.source}
                  sourceCredentials={preflight.source_credentials}
                  blockingIssues={preflight.blocking_issues}
                  warnings={preflight.warnings}
                />
                <div className="flex flex-wrap gap-2 pt-2">
                  <button
                    type="button"
                    onClick={handleStart}
                    disabled={!canStart}
                    className="inline-flex items-center gap-1.5 rounded-sm bg-wcm-accent px-3 py-1.5 text-xs font-semibold text-wcm-primary hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Rocket className="h-3.5 w-3.5" aria-hidden />
                    Crear y arrancar pipeline
                  </button>
                  <button
                    type="button"
                    onClick={handleCreateAndPreflight}
                    disabled={preflightLoading}
                    className="rounded-sm border border-wcm-detail/60 px-3 py-1.5 text-xs text-wcm-text/80 hover:border-wcm-detail hover:text-wcm-text"
                  >
                    Re-ejecutar preflight
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveAndExit}
                    className="rounded-sm border border-wcm-detail/60 px-3 py-1.5 text-xs text-wcm-text/80 hover:border-wcm-detail hover:text-wcm-text"
                  >
                    Guardar sin arrancar (proyecto queda en queued)
                  </button>
                </div>
                {!canStart && (
                  <p className="text-[11px] text-wcm-warning">
                    Resuelve los chequeos bloqueantes antes de arrancar.
                    Re-ejecuta el preflight tras corregirlos.
                  </p>
                )}
              </>
            )}
          </div>
        )}

        {error && (
          <p className="mt-3 text-[11.5px] text-wcm-danger">{error}</p>
        )}
      </div>

      {/* Navegación entre pasos. */}
      <div className="flex justify-between gap-2">
        <button
          type="button"
          onClick={() => {
            if (stepIdx > 0) goTo(STEPS[stepIdx - 1]!.key);
          }}
          disabled={stepIdx === 0 || pending}
          className="inline-flex items-center gap-1.5 rounded-sm border border-wcm-detail/60 px-3 py-1 text-xs text-wcm-text/80 hover:border-wcm-detail hover:text-wcm-text disabled:opacity-50"
        >
          <ArrowLeft className="h-3 w-3" aria-hidden />
          Anterior
        </button>
        {step !== "preflight" && (
          <button
            type="button"
            onClick={() => {
              if (step === "origen" && !canAdvanceOrigen) return;
              if (step === "business" && !canAdvanceBusiness) return;
              if (step === "design" && !canAdvanceDesign) return;
              if (step === "destino" && !canAdvanceDestino) return;
              if (step === "features" && !canAdvanceFeatures) return;
              goTo(STEPS[stepIdx + 1]!.key);
            }}
            disabled={
              (step === "origen" && !canAdvanceOrigen) ||
              (step === "destino" && !canAdvanceDestino)
            }
            className="inline-flex items-center gap-1.5 rounded-sm bg-wcm-accent px-3 py-1 text-xs font-semibold text-wcm-primary hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Siguiente
            <ArrowRight className="h-3 w-3" aria-hidden />
          </button>
        )}
      </div>
    </div>
  );
}

const inputClass =
  "h-8 w-full rounded-sm border border-wcm-detail/70 bg-wcm-primary px-2 text-xs text-wcm-text placeholder:text-muted-foreground focus:border-wcm-accent focus:outline-none";

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

function Checkbox({
  id,
  checked,
  onChange,
  label,
}: {
  id: string;
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
}) {
  return (
    <label htmlFor={id} className="flex items-baseline gap-2 text-xs text-wcm-text/90">
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-3.5 w-3.5 cursor-pointer accent-wcm-accent"
      />
      {label}
    </label>
  );
}
