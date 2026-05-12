# Decisiones arquitectónicas — Webcafeína Migrator

> Formato ADR ligero. Cada decisión: contexto + decisión + consecuencias.
> Las decisiones se identifican por número `ADR-NNN` y son inmutables (si una se revoca, se añade nueva que la supersede).

---

## ADR-001 — Sin Docker en producción

**Fecha**: 2026-05-12 (Fase 0)
**Estado**: ✅ Aceptada — restricción del cliente

**Contexto**: Webcafeína opera sobre WHM/cPanel. La empresa ha tenido fricciones con stacks containerizados en el pasado (gestión de volúmenes, reinicios, hardening) y prefiere procesos nativos.

**Decisión**: Despliegue como procesos nativos gestionados por **systemd** (preferente) o Supervisor (fallback si systemd no disponible). Nginx nativo como reverse proxy. PostgreSQL y Redis vía paquetes del sistema (yum/dnf o apt según distro WHM).

**Consecuencias**:
- ✅ Mejor afinidad con WHM/cPanel y herramientas que el equipo ya domina.
- ✅ Logs unificados en `journalctl` sin overhead.
- ⚠️ Mayor disciplina al gestionar dependencias (venv aislado por servicio).
- ⚠️ CI tiene que tener cuidado con assumes-docker en linters/tests.

---

## ADR-002 — Bricks Builder como page builder destino

**Fecha**: 2026-05-12 (Fase 0)
**Estado**: ✅ Aceptada — preferencia del equipo

**Contexto**: WordPress tiene múltiples page builders (Elementor, Divi, Bricks, Breakdance, Oxygen, Gutenberg blocks). Webcafeína trabaja con Bricks por rendimiento, calidad del HTML generado y API JSON estable.

**Decisión**: Bricks Builder como page builder destino exclusivo del MVP. No se soportan otros page builders en el output (sí en el origen, vía `lsr-fingerprint`).

**Consecuencias**:
- ✅ Un solo target a soportar para el transpilador — calidad alta.
- ✅ Bricks Theme Styles permite respetar la paleta de cada cliente correctamente.
- ❌ Clientes que prefieran otro builder requerirían rehacer el transpilador. Decisión asumida.
- ⚠️ Dependencia de licencia Bricks (`BRICKS_LICENSE_KEY` en `.env`).

---

## ADR-003 — WPML solo si proyecto.is_multilang

**Fecha**: 2026-05-12 (Fase 0)
**Estado**: ✅ Aceptada

**Contexto**: WPML añade overhead, complejidad y coste de licencia. Muchos clientes son monolang (solo español).

**Decisión**: WPML se instala **solo** cuando `project.is_multilang = true`. Para webs monolingües se mantiene un WP ligero. Si solo hay 2 idiomas y el cliente prefiere sitios separados, se desactiva WPML y se montan 2 instalaciones.

**Consecuencias**:
- ✅ WP más ligero y mantenible para la mayoría de proyectos.
- ✅ Menos coste de licencia para clientes monolang.
- ⚠️ `multilang-handler` + `wpml-configurator` son condicionales en el pipeline.

---

## ADR-004 — WP-CLI vía SSH desde host de control

**Fecha**: 2026-05-12 (Fase 0)
**Estado**: ✅ Aceptada

**Contexto**: Operaciones bulk pesadas (>100 items, search-replace de DB, importación de Bricks JSON grande) son frágiles vía WP REST API. WP-CLI ejecutado localmente en el destino es la forma robusta.

**Decisión**: Comunicarse con el WP destino vía dos canales:
- REST API (idempotencia, operaciones puntuales): skill `wp-rest-bulk`
- WP-CLI vía SSH (paramiko): skill `wpcli-ssh`

Heurística: `N <= 100` → REST; `N > 100` o transaccional → WP-CLI.

**Consecuencias**:
- ✅ Robustez en operaciones grandes (imports completos no se atragantan).
- ⚠️ Requiere acceso SSH al destino. No siempre disponible si el cliente está en hostings pre-configurados sin SSH (anotar limitación en venta).
- ⚠️ Requiere WP-CLI instalado en destino.

---

## ADR-005 — Bright Data residencial como proxy default

**Fecha**: 2026-05-12 (Fase 0)
**Estado**: ✅ Aceptada

**Contexto**: La prospección requiere scraping fiable de Google Maps (no, lo hacemos por API oficial), directorios sectoriales y dorks. Las IPs de datacenter son bloqueadas con frecuencia. Bright Data ofrece residencial pay-as-you-go.

**Decisión**: Bright Data residencial en producción. En desarrollo sin proxy. En staging con datacenter Bright Data (más barato) para pruebas.

**Consecuencias**:
- ✅ Tasa de éxito alta en prospección.
- ⚠️ Coste variable. Tope mensual en presupuesto operativo (monitoreo en dashboard).
- ⚠️ Captcha aún puede aparecer; fallback a 2captcha con presupuesto controlado por campaña.

---

## ADR-006 — Outreach con revisión humana obligatoria, sin envío automático

**Fecha**: 2026-05-12 (Fase 0)
**Estado**: ✅ Aceptada — política de Webcafeína

**Contexto**: La automatización completa de outreach tiene riesgos legales (LSSI-CE), reputacionales (spam) y de calidad (mensajes mal personalizados pasan filtros y queman dominio).

**Decisión**: La herramienta **prepara** secuencias y las guarda en `outreach_sequences` con `status="draft_pending_review"`. El operador revisa cada secuencia y la envía manualmente desde la herramienta de email del cliente (Brevo, Lemlist, Gmail, etc.). La herramienta **nunca envía a leads**.

**Consecuencias**:
- ✅ Menor riesgo legal y reputacional.
- ✅ Mensajes mejor cuidados.
- ❌ No es "send-and-forget"; el equipo invierte tiempo en revisión. Asumido.

---

## ADR-007 — Sin TODOs huérfanos

**Fecha**: 2026-05-12 (Fase 0)
**Estado**: ✅ Aceptada

**Contexto**: TODOs en código sin tracking se pierden y degradan calidad con el tiempo.

**Decisión**: Cada `TODO` en código debe llevar un identificador `WCM-NNN` que enlace a una entrada en `ISSUES.md` (local hasta crear repo GitHub) o GitHub Issues (cuando exista).

**Consecuencias**:
- ✅ Trazabilidad completa de deuda técnica.
- ⚠️ Pequeña fricción al añadir un TODO. Asumida.

---

## ADR-008 — Git local sin remote durante construcción Fase 0

**Fecha**: 2026-05-12 (Fase 0)
**Estado**: 🟥 Superseded by ADR-013

**Contexto**: Al iniciar la construcción no hay aún un repo GitHub creado. El usuario prefiere revisar el bootstrap antes de exponerlo.

**Decisión**: `git init` local con identidad `info@webcafeina.com` / `Webcafeína`. Sin remote configurado. Push se hará tras crear el repo GitHub (siguiente sesión).

**Consecuencias**:
- ✅ Cambios versionados desde el primer commit.
- ⚠️ Si el repo GitHub se crea con un commit inicial autogenerado por GitHub, habrá que reconciliar histories. Anticipar usando `git push -u origin main --force` con commit limpio, o crear repo vacío.

---

## ADR-009 — Modelos LLM: Opus para subagentes críticos, Sonnet para el resto

**Fecha**: 2026-05-12 (Fase 0)
**Estado**: ✅ Aceptada

**Contexto**: Algunos subagentes requieren razonamiento complejo (orchestrator, bricks-transpiler), otros son ejecutores deterministas con cierta lógica.

**Decisión**: Frontmatter `model: opus` en `orchestrator.md` y `bricks-transpiler.md`. `model: sonnet` (default Claude Code) en el resto.

**Consecuencias**:
- ✅ Coste optimizado.
- ✅ Razonamiento adecuado donde importa.
- ⚠️ Si se detecta que otro subagente necesita Opus, cambiar individualmente.

---

## ADR-010 — Embedding vectorial: voyage-multilingual-2, 1024 dimensiones

**Fecha**: 2026-05-12 (Fase 1)
**Estado**: ✅ Aceptada

**Contexto**: La columna `leads.embedding` (pgvector) sirve para buscar leads similares por contenido de la web. El proveedor de embedding influye en (a) calidad para español de PYMEs, (b) coste por 1M tokens, (c) dimensionalidad almacenada en BD (cambiarla implica re-embedding + nuevo índice).

**Decisión**: Usar **`voyage-multilingual-2`** (Voyage AI, propiedad de Anthropic) con **1024 dimensiones**. Coherente con la postura "Claude-native" y buena cobertura para español. Coste competitivo (~$0.12/M tokens). Si en el futuro se quiere cambiar, se documenta nueva ADR + migración con re-embedding completo.

La dimensión queda codificada como constante `LEAD_EMBEDDING_DIM = 1024` en `packages/db-schema/src/wcm_db/models/leads.py` y replicada en la migración `0001_initial_schema.py`.

**Consecuencias**:
- ✅ Calidad multilingüe sólida (esp/cat/gal/eu/en en una misma campaña).
- ✅ Anthropic-aligned, sin dependencia de OpenAI.
- ⚠️ Cambiar de proveedor → migración de schema + re-embedding completo de la tabla `leads`.
- ⚠️ Voyage API requiere credencial separada (a añadir al `.env.example` en Fase 9).

---

## ADR-011 — Enums viven en wcm_types, wcm_db los re-exporta

**Fecha**: 2026-05-12 (Fase 1)
**Estado**: ✅ Aceptada

**Contexto**: Los enums (LeadStatus, BuilderType, etc.) son compartidos por (a) la BD (columnas VARCHAR con CHECK implícito vía StrEnum), (b) la capa de schemas Pydantic, (c) los tipos TypeScript generados. Duplicar genera drift inevitable.

**Decisión**: La fuente única vive en `packages/shared-types/python/wcm_types/enums.py`. `packages/db-schema/src/wcm_db/enums.py` re-exporta cada Enum (mantiene compatibilidad con `from wcm_db.enums import ...` sin acoplar a `wcm_types` a nivel de import path). `wcm-db-schema` declara `wcm-shared-types` como dependencia.

**Consecuencias**:
- ✅ Cambiar un enum → cambia en BD, API y dashboard automáticamente.
- ✅ Test `test_db_reexports_same_enum_objects` valida la identidad (`is`).
- ⚠️ Si alguien define un enum nuevo en `wcm_db.enums`, romperá. Documentado.

---

## ADR-013 — Repo GitHub diferido hasta final de Fase 15

**Fecha**: 2026-05-12 (Fase 1)
**Estado**: ✅ Aceptada — supersede ADR-008

**Contexto**: ADR-008 (provisional) preveía crear el repo GitHub al inicio de Fase 1. El usuario ha decidido posponer la creación del repositorio remoto hasta que **todas las fases (0–15) estén desarrolladas y revisadas localmente**. Razones expresadas: control total durante la construcción + revisión final antes de exponer.

**Decisión**: El repositorio sigue solo local (`git init` en `/Users/alvaro/Desktop/webcafeina-migrator/`) sin remote configurado. La creación del repo GitHub (privado, bajo cuenta Webcafeína) se hace al cerrar Fase 15, antes del primer despliegue. El push inicial llevará el histórico completo de los commits ya hechos.

**Implicaciones por fase**:
- **Fases 2–11, 13, 14, 15**: ninguna implicación. Trabajo 100% local.
- **Fase 12 (Infra/Deploy)**: los workflows `.github/workflows/*.yml` se escriben con normalidad (su sintaxis y contenido se valida estáticamente), pero **no se ejecutan** hasta que exista el repo remoto. El despliegue inicial en WHM se hace manualmente con `infra/deploy/deploy.sh` antes de tener CI/CD operativo.
- Antes del primer push: revisar y depurar el histórico si hace falta (sin amends de commits firmados como Co-Authored-By).

**Consecuencias**:
- ✅ Cero exposición durante construcción.
- ✅ Revisión humana antes del primer push final.
- ⚠️ Sin CI rojo/verde durante construcción — confiamos en tests locales `pnpm test`/`pytest`.
- ⚠️ Sin Issues GitHub durante construcción — pendientes en `ISSUES.md` local con IDs `WCM-NNN`. Migración a Issues GitHub al final.
- ⚠️ Sin Dependabot/Renovate durante construcción — auditoría de deps al inicio de Fase 15 (Hardening) revisa el snapshot completo.

---

## ADR-012 — Generación TS automática con pydantic2ts (no manual)

**Fecha**: 2026-05-12 (Fase 1)
**Estado**: ✅ Aceptada

**Contexto**: Necesitamos tipos TypeScript del contrato del API en el dashboard. Mantenerlos a mano es alto coste y alto riesgo de drift.

**Decisión**: Usar **`pydantic-to-typescript`** (`pydantic2ts`) para generar `packages/shared-types/ts/index.d.ts` a partir de `wcm_types/schemas/*.py`. Script en `packages/shared-types/scripts/gen-ts.sh`. Comando shortcut: `pnpm gen:types`. Requiere `json-schema-to-typescript` (npm `json2ts`) accesible vía `JSON2TS_CMD` env (default: `json2ts` en PATH; CI puede usar `npx -y json-schema-to-typescript`).

**Consecuencias**:
- ✅ Un único origen para los tipos del contrato.
- ✅ CI puede validar drift comparando regeneración vs commit.
- ⚠️ La herramienta genera alias duplicados de enums (UserRole1, OutreachChannel2, etc.) cuando el mismo enum se referencia desde varios schemas. Funcionalmente correcto, cosméticamente feo. Pendiente WCM-007 (post-procesado para deduplicar).
- ⚠️ Requiere Node + Python en el entorno de build.

---

## Cómo añadir una nueva decisión

1. Incrementar `ADR-NNN`.
2. Añadir entrada con: Fecha, Estado, Contexto, Decisión, Consecuencias.
3. Si supersede una decisión previa, marcar la anterior como "🟥 Superseded by ADR-MMM".
4. Commit con `docs(adr): ADR-NNN <título>`.
