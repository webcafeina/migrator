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
**Estado**: 🟥 Superseded by ADR-017

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
**Estado**: 🟥 Superseded by ADR-023

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

## ADR-014 — Esquema Bricks observacional desde docs públicas (provisional)

**Fecha**: 2026-05-13 (Fase 2)
**Estado**: ✅ Aceptada (provisional hasta WCM-001)

**Contexto**: Fase 2 (Bricks transpiler) requería el export JSON real de Bricks Builder (WCM-001). El humano no lo tenía disponible y eligió continuar usando documentación pública (Bricks Academy, repos GitHub `wpgaurav/bricks-skills`, `sabiertas/bricks-mcp-server`, BricksSync) en lugar de bloquear el trabajo.

**Decisión**: El esquema documentado en `.claude/skills/bricks-json-schema/SKILL.md` (v1 observacional) refleja la mejor reconstrucción posible: estructura `id/name/parent/children/settings`, IDs `[a-z0-9]{6}`, prefijo DOM `brxe-`, settings con prefijo `_` para globales (`_typography`, `_padding`, `_background`, etc.), patrón responsive con sufijo `:tablet_portrait`/`:mobile_portrait`. Catálogo de 24 element names para Bricks 2.0+. Importación al destino vía post meta `_bricks_page_content_2` (no hay endpoint REST nativo de Bricks).

Cuando llegue el export real (WCM-001), se valida y se ajusta. Mientras tanto, el transpilador puede producir output con keys/formato levemente desviados.

**Consecuencias**:
- ✅ Fase 2 no se bloquea esperando un asset humano.
- ✅ 63 tests passed con cobertura amplia (16 BlockType mapeados).
- ⚠️ Riesgo de keys mal nombradas que se descubrirán al probar contra un Bricks real (smoke test en Fase 4 o Fase 12).
- ⚠️ Calibración fina queda como tarea técnica al recibir WCM-001 — se documentará ADR nuevo si el ajuste cambia decisiones de diseño.

---

## ADR-015 — IDs Bricks deterministas con blake2b + base36

**Fecha**: 2026-05-13 (Fase 2)
**Estado**: ✅ Aceptada

**Contexto**: Bricks Builder requiere IDs `[a-z0-9]{6}` únicos por página. Necesitamos que re-transpilar la misma página produzca el mismo JSON (idempotencia para `wp-deployer` upsert sin churn).

**Decisión**: `make_element_id(project_id, page_id, order_index, block_type, sub_index, salt)` → `blake2b(digest_size=8)` truncado a 6 chars base36 minúscula. Espacio ≈ 36⁶ ≈ 2.18·10⁹. `IdGenerator` detecta colisiones intra-página y reintenta con `sub_index+1`. `salt="wcm-bricks-v1"` permite invalidar todos los IDs en bloque si en el futuro se cambia el mapping incompatible.

**Consecuencias**:
- ✅ Re-transpilar la misma página → mismo JSON. `wp-deployer` compara hashes y solo actualiza si difiere.
- ✅ Trazabilidad: dado un ID en producción, se reconstruye su tuple lógico.
- ⚠️ Dos páginas que compartan un mismo bloque global (p. ej. header) generan IDs distintos por tener distinto `page_id`. Aceptable para MVP; el header se gestiona como template Bricks aparte.

---

## ADR-016 — Workaround macOS+Python3.14 para .pth files heredando flag hidden

**Fecha**: 2026-05-13 (Fase 2)
**Estado**: ✅ Aceptada (workaround temporal)

**Contexto**: En macOS, archivos creados dentro de un directorio `.venv/` heredan el flag `UF_HIDDEN`. Python 3.14 introdujo en `site.py` un skip explícito de `.pth` files con flag hidden. Resultado: `pip install -e` instala correctamente pero los paquetes editable no son importables hasta que se quite el flag manualmente.

**Decisión**: Mantener `pip install -e` como mecanismo estándar y proporcionar `scripts/fix-venv-hidden-pth.sh` que ejecuta `chflags nohidden` sobre todos los `*.pth` del venv. Ejecutar tras cualquier `pip install`. No-op fuera de macOS.

Issue tracking interno: **WCM-008**.

**Consecuencias**:
- ✅ Workflow editable funciona sin tener que cambiar de Python.
- ⚠️ Cada nuevo `pip install` requiere re-ejecutar el script. Añadir al onboarding del entorno de desarrollo.
- ⚠️ Si upstream Python revierte o setuptools cambia la convención de naming, el workaround queda obsoleto. Bajo coste de mantenimiento.

---

## ADR-017 — Proxy layered con free tiers; Bright Data como premium opcional

**Fecha**: 2026-05-13 (Fase 3)
**Estado**: ✅ Aceptada — supersede ADR-005

**Contexto**: ADR-005 fijaba Bright Data residencial como default. El usuario pidió evaluar opciones gratuitas. Investigación (Webshare, ScraperAPI, ScrapingBee, listas públicas, Tor) concluye:

- **Listas públicas (ProxyScrape, Databay, Oxylabs free list)**: pésimas en producción — lentas, inestables, riesgo de inyección de ads/malware. Descartadas.
- **Webshare free** ([webshare.io](https://www.webshare.io/)): 10 datacenter proxies forever-free + 1GB/mes, sin tarjeta. Soporta SOCKS5+HTTP, rotación oficial. **Mejor opción gratuita real para producción ligera.**
- **ScraperAPI free** ([scraperapi.com](https://www.scraperapi.com/)): 5k calls/mes free con rotación + bypass de captcha + JS rendering. Buen complemento cuando Webshare se queda corto o aparece captcha.
- **Bright Data**: premium dimensionable. Mantenido como tier opcional.

**Decisión**: `ProxyRotator` layered con backends en orden creciente de capacidad:

```
NoProxy (default dev + migración cliente)
  ↓ ENV vars activan los siguientes
Webshare (free 10 IPs + 1GB/mes)
  ↓
ScraperAPI (free 5k calls/mes)
  ↓
Bright Data (paid premium, opcional)
```

`build_default_rotator()` lee `.env` y construye la cadena automáticamente. En `ENV=production` arranca en el primer backend free disponible; en dev arranca en NoProxy. `rotator.escalate()` pasa al siguiente backend cuando el actual se agota.

**Consecuencias**:
- ✅ Coste mensual real: 0€ hasta que la prospección crezca significativamente.
- ✅ Sin lock-in: cualquiera de los tiers se activa solo con env vars.
- ✅ Migración cliente sigue usando IP directa Webcafeína (sin proxy) — coherente con el principio de transparencia hacia clientes con consentimiento.
- ⚠️ Free tiers tienen quotas: Webshare 1GB/mes ≈ 1000-5000 páginas; ScraperAPI 5k calls. Para campañas grandes (>1000 leads/mes) hay que escalar.
- ⚠️ Webshare datacenter (no residencial) — algunos sitios protegidos pueden detectarlo. En ese caso escalar a ScraperAPI (que sí usa residencial mezclado).
- ⚠️ `.env.example` ampliado con `WEBSHARE_USER`, `WEBSHARE_PASSWORD`, `SCRAPERAPI_KEY` (todos opcionales).

**Fuentes consultadas**:
- [Webshare features](https://www.webshare.io/features/datacenter-proxy)
- [ScraperAPI free tier](https://www.scraperapi.com/)
- [Best free proxies 2026 — ScrapingBee blog](https://www.scrapingbee.com/blog/best-free-proxy-list-web-scraping/)
- [Top rotating residential proxies 2026 — Crawlbase](https://crawlbase.com/blog/rotating-residential-proxies/)

---

## ADR-018 — Workarounds Local by Flywheel para sandbox WP en macOS

**Fecha**: 2026-05-13 (Fase 4)
**Estado**: ✅ Aceptada — solo aplica en dev sandbox, no en producción

**Contexto**: Para Fase 4 (WP client) usamos Local by Flywheel como sandbox de desarrollo (gratis, sin Docker, simula bien un WP real). Durante la verificación inicial aparecieron particularidades del entorno Local que rompen la asunción de "WP-CLI estándar":

1. **`wp-cli.phar` no viene preinstalado** desde versiones recientes de Local. Hay que descargarlo manualmente al directorio del site.
2. **PHP no está en `PATH`** del shell SSH no-interactivo. Local lo instala en `~/Library/Application Support/Local/lightning-services/php-8.x/bin/darwin-arm64/bin/php`. Hay que invocar el binario absoluto.
3. **MySQL escucha en socket Unix con ID volátil** (`~/Library/Application Support/Local/run/<8-char-ID>/mysql/mysqld.sock`). Para WP-CLI vía SSH externo hay que pasar `-d mysqli.default_socket=<sock_path>` a PHP.
4. **El usuario admin del WP no se llama `admin`**: Local lo crea con un nombre custom (en nuestro sandbox: `test`).
5. **`.env` con paths que contienen espacios**: requiere quoting `KEY="value with spaces"` para ser source-able por bash/zsh; `python-dotenv` lo tolera sin quoting, pero usamos `source .env` también para tests integración.

**Decisión**: `WpClientConfig` añade dos campos opcionales `local_php_bin` y `local_mysql_socket`. `WpCliSshClient._build_wpcli_cmd` aplica los workarounds si están configurados; si no, asume `wp` binario global en `PATH` y DB accesible normal (caso producción WHM/cPanel).

**Consecuencias**:
- ✅ El cliente funciona transparentemente contra Local sin código condicional en el caller.
- ✅ En producción real WHM/cPanel, `local_php_bin` y `local_mysql_socket` son `None` y el comando construido es `wp --path=... <args>`.
- ⚠️ Paths volátiles en Local (versión PHP, ID de run) → `.env` se desactualiza si Local cambia algo. Anotado WCM-009 (autodescubrir PHP) y WCM-010 (autodescubrir socket).

---

## ADR-019 — Versionado `/api/v1/...` + endpoint público RGPD fuera del prefijo

**Fecha**: 2026-05-13 (Fase 5)
**Estado**: ✅ Aceptada

**Contexto**: La API expone dos audiencias distintas: (a) el dashboard interno (JSON, JWT/cookie), (b) receptores de outreach que abren un link de opt-out (HTML, sin cookie, token RGPD). Mezclarlas bajo el mismo prefijo confunde y dificulta evolucionar la API sin tocar la página de opt-out.

**Decisión**:
- Endpoints internos de la API: **`/api/v1/...`** con OpenAPI auto en `/docs`. Prefijo de versión por previsión de breaking changes futuras.
- `/health` y `/ready`: sin prefijo (probes para Nginx/monitoring).
- `/opt-out`: sin prefijo, devuelve HTML formateado con paleta Webcafeína. URL pública apta para email humano (`https://migrator.webcafeina.com/opt-out?token=...`).
- Webhooks entrantes: `/api/v1/webhooks/<source>` con HMAC del proveedor.

**Consecuencias**:
- ✅ Versionar la API sin romper opt-out URLs en emails ya enviados.
- ✅ Separación clara máquina↔humano en routing.
- ⚠️ En producción `/docs` y `/openapi.json` se ocultan (Fase 11 / hardening Fase 15 lo refuerza con auth gating).

---

## ADR-020 — Subagentes runtime en `apps/worker/agents/` distintos de los descriptors `.claude/agents/`

**Fecha**: 2026-05-13 (Fase 6)
**Estado**: ✅ Aceptada

**Contexto**: Durante Fase 0 generamos 20 ficheros `.claude/agents/*.md` con frontmatter Anthropic. Esos están pensados para que Claude Code los detecte como "subagentes" invocables vía Task tool. Sin embargo, el producto Webcafeína Migrator opera en runtime con código Python, no con Claude. Necesitamos clases Python que envuelvan la lógica de cada subagente y se invoquen desde el worker.

**Decisión**: Mantener ambos planos separados:

| Plano | Ubicación | Audiencia | Función |
|---|---|---|---|
| **Descriptors** | `.claude/agents/<name>.md` | Claude Code durante construcción | Contrato del agent (inputs/outputs/errores) + documentación |
| **Runtime** | `apps/worker/src/wcm_worker/agents/<name>.py` | Python en producción | Implementación que el orchestrator invoca |

Cada agent Python (`BaseAgent` subclass) implementa el contrato descrito en su `.md`. Los nombres se mantienen sincronizados (kebab-case en .md, snake_case en .py). Los errores tipados de cada agent viven en `wcm_worker.errors`.

**Consecuencias**:
- ✅ Los `.md` siguen siendo útiles como documentación viva durante construcción.
- ✅ El runtime no depende de Claude para ejecutar el pipeline.
- ✅ Tests unitarios trabajan con clases Python normales (mocks, AsyncMock, etc.).
- ⚠️ Mantener consistencia entre .md y .py es manual; conviene revisar el .md cuando se modifique el .py (y al revés). En Fase 14 (docs) se puede automatizar un check de drift.

---

## ADR-021 — CLI: doble entrypoint y CliError = ClickException

**Fecha**: 2026-05-13 (Fase 7)
**Estado**: ✅ Aceptada

**Contexto**: El prompt maestro fija `webcafeina-migrator` como nombre del binario. Es largo para uso diario. Por otro lado, durante Fase 7 descubrimos que un wrapper `main()` con `try/except CliError` no captura excepciones cuando los tests usan `CliRunner.invoke(app, ...)` (que llama directamente a `app`, no a `main`).

**Decisiones**:

1. **Doble entrypoint** en `[project.scripts]`:
   - `webcafeina-migrator` — nombre oficial conforme al prompt maestro
   - `wcm` — alias corto para uso diario
   Ambos apuntan a `wcm_cli.main:main`.

2. **`CliError` hereda de `click.ClickException`**, no de `Exception`. Click/Typer lo captura automáticamente: invoca `CliError.show()` para imprimir el mensaje y aplica `self.exit_code`. Funciona tanto en ejecución real como en `CliRunner.invoke()`.

3. `CliError.show()` se sobrescribe para escribir a **stdout** (no al stderr default de Click) en modo humano — facilita inspección en tests vía `result.output`. En modo `--json` redirige a stderr (mantiene stdout JSON-limpio para `| jq`).

4. Para output normal, usamos `typer.echo()` en lugar de Rich Console (excepto tablas). Rich Console tiene buffering interno que no interactúa bien con `CliRunner`. `typer.echo` pasa por `click.echo` que respeta el stream redirigido.

**Consecuencias**:
- ✅ Tests pasan sin fricción (17/17).
- ✅ Errores se ven correctamente con `wcm` binario en terminal real.
- ✅ Pipes a `jq` funcionan (`wcm --json ... | jq ...`).
- ⚠️ Pierdo colores Rich en mensajes simples. Se mantienen en tablas, que es donde más valor aportan.

---

## ADR-022 — Dashboard Next.js 15: JetBrains Mono en toda la UI

**Fecha**: 2026-05-13 (Fase 8)
**Estado**: ✅ Aceptada

**Contexto**: El stack canónico (CLAUDE.md §4) fija "shadcn/ui + Tailwind CSS con paleta Webcafeína". Para tipografía decía "sans-serif moderna (concreta se decide en Fase 8)". El operador eligió **JetBrains Mono** — fuente monoespaciada — para TODA la UI, no solo código.

**Decisión**: Cargar JetBrains Mono via `next/font/google` con weights 400/500/600/700, exponer como `--font-jetbrains` y aplicarla a `body` + `font-sans` + `font-mono` en Tailwind. Sustituye a Inter/system-ui como default global.

**Consecuencias**:
- ✅ Look denso, técnico, terminal-friendly — coherente con la herramienta (mucho dato tabular).
- ✅ Tabular nums uniformes en tablas (score, confianza, IDs).
- ✅ Refuerza identidad de "tooling interno técnico".
- ⚠️ Texto más ancho que sans-serif tradicional → presupuesto horizontal aumenta. Compensado con `text-sm` por defecto.
- ⚠️ Si en el futuro hay público no-técnico, revisar. No aplica al MVP.

**Otras decisiones de la fase**:
- Logo SVG pendiente → wordmark de texto en lima ("WEBCAFEÍNA" + icono `Activity` de lucide).
- Paleta extendida bajo namespace `wcm-*` (`bg-wcm-primary`, `text-wcm-accent`) coexistente con tokens shadcn estándar.
- Server Components por defecto + Client Components solo para interactividad.
- Cookie http-only `wcm_session` con `credentials: "include"` + rewrite `/api/v1/*` → API. Sin CORS en producción.
- Build `output: "standalone"` para systemd con `node server.js`.

---

## ADR-023 — Embeddings: sentence-transformers local con `multilingual-e5-large`

**Fecha**: 2026-05-13 (Fase 9)
**Estado**: ✅ Aceptada — supersede ADR-010

**Contexto**: ADR-010 fijaba Voyage AI (`voyage-multilingual-2`, 1024 dim) por ser la opción "Claude-native". El operador pidió alternativa **completamente gratuita** sin renunciar a la dimensión 1024 (que ya está fijada en el schema de Postgres + índice ivfflat).

Investigadas en 2026 las opciones:
- **`intfloat/multilingual-e5-large`** (468M params, 1024 dim, 512 tokens, ~5% mejor que BGE-M3 en español según benchmarks comparativos)
- **`BAAI/bge-m3`** (335M params, 1024 dim, 8192 tokens, más rápido en GPU pero peor en español)
- Listas públicas de proxies / Hugging Face Inference free tier: cuotas bajas, no aptas para producción.

**Decisión**: `intfloat/multilingual-e5-large` via **sentence-transformers** local. Match exacto de dimensión con el schema actual (LEAD_EMBEDDING_DIM=1024). Sin cambios en migración Alembic.

Detalles operacionales:
- Modelo se descarga primera vez (~2.2GB) a `~/.cache/huggingface/`.
- `EmbeddingService` lazy singleton en `wcm_worker` — solo se carga en el worker, no en el API (la API es ligera).
- Prefijo "passage: " obligatorio para corpus (convención e5; querys usan "query: ").
- LRU cache para textos repetidos.
- CPU funciona para batch jobs del worker (~50ms/text en CPU moderna); GPU recomendada si > 1000 leads/h.

**Consecuencias**:
- ✅ Coste API: **0€/mes** perpetuo. Sin cuotas. Sin lock-in.
- ✅ Sin migración del schema — dimension match exacto.
- ✅ Calidad multilingüe alta para español (consideran B2B PYMEs).
- ✅ Operativo offline una vez descargado el modelo.
- ⚠️ **RAM 4GB+ recomendada** en el servidor worker (el modelo carga en memoria).
- ⚠️ **Disco ~2.5GB** para el modelo + cache HuggingFace.
- ⚠️ Cold start: primera llamada tras boot tarda 20-40s en cargar el modelo. Mitigamos con eager-load opcional en arranque del worker (config).
- ⚠️ Las variables `VOYAGE_API_KEY` y `VOYAGE_EMBEDDING_MODEL` quedan en `.env.example` por compat histórica pero NO se usan. Se retirarán en Fase 15 (hardening).

---

## ADR-024 — Google Places API legacy (no la "New")

**Fecha**: 2026-05-13 (Fase 9)
**Estado**: ✅ Aceptada

**Contexto**: Google Cloud expone DOS APIs distintas:
- **Places API (legacy)**: `maps.googleapis.com/maps/api/place/*` — la "clásica" desde 2015+, estable, ampliamente integrada en SDKs.
- **Places API (New)**: `places.googleapis.com/v1/*` — anunciada en 2024 con esquema gRPC-style, field masks obligatorios, distinto pricing.

La API key del operador tiene habilitada la **legacy** (test con Places-New devolvió `API_KEY_SERVICE_BLOCKED`).

**Decisión**: Usar **Places API legacy** (`maps.googleapis.com/maps/api/place/*`). Endpoints:
- Text Search: `/textsearch/json?query=...&language=es&region=es`
- Place Details: `/details/json?place_id=...&fields=...` (field mask reduce coste)

**Consecuencias**:
- ✅ Funciona con la API key actual sin cambios en Google Cloud Console.
- ✅ SDK `googlemaps` Python oficial está pensado para legacy (compat directa si se quiere usar).
- ✅ Más documentación, ejemplos y madurez que la New.
- ⚠️ Google ha comunicado que la legacy entrará en deprecation en futuro indefinido. Si Google la retira (estimación >18 meses), migrar a Places-New requiere habilitar la API + adaptar el cliente. Bajo riesgo para el horizonte MVP.
- ⚠️ Field mask en Place Details es opcional en legacy pero **lo aplicamos** para minimizar coste (solo `name,formatted_address,website,international_phone_number,business_status,types,place_id`).

---

## ADR-025 — Resend como proveedor único de email transaccional

**Fecha**: 2026-05-13 (Fase 10)
**Estado**: ✅ Aceptada

**Contexto**: Necesitamos enviar:
- **Outreach a leads** (uno a uno, baja frecuencia, alta criticidad legal y reputacional).
- **Notificaciones internas** al equipo (resúmenes, alertas, replies entrantes).
- En el futuro: emails a clientes (avisos de go-live, checklist entregado).

Candidatos evaluados: SES (barato, complejidad operativa alta), Postmark (excelente reputación, $$$ sin tier gratuito útil), Mailgun (declinando), **Resend** (DX moderna, SDK Python oficial, webhook nativo con HMAC, free tier 3k emails/mes).

**Decisión**: Resend como único proveedor de email saliente.
- SDK oficial `resend` Python.
- Dominio remitente: `migrator@webcafeina.com` (subdomain dedicado para no contaminar la reputación del dominio principal).
- Webhook entrante en `POST /api/v1/webhooks/resend` con HMAC SHA-256 sobre el body crudo, secret `RESEND_WEBHOOK_SECRET`.
- Cliente envolvente en `apps/worker/src/wcm_worker/integrations/resend.py`: reintentos con backoff, `from_env()` perezoso, validador de webhook integrado.

**Consecuencias**:
- ✅ Un único proveedor: trazabilidad y observabilidad consolidadas.
- ✅ Webhooks ya implementados para opens/bounces/replies → `OutreachSend` se actualiza automáticamente.
- ✅ Free tier cubre todo el MVP (3000 emails/mes con holgura).
- ⚠️ Acoplamiento: si Resend sube precios o tiene incidentes, dependemos solo de ellos. Mitigación: el `ResendClient` está aislado en un módulo único — sustituirlo por otro proveedor implica reescribir un solo fichero.
- ⚠️ Dominio `webcafeina.com` debe estar verificado en Resend (SPF/DKIM/DMARC) antes de producción.

---

## ADR-026 — Cloudflare R2 vía boto3 (S3-compat) en lugar del SDK Cloudflare

**Fecha**: 2026-05-13 (Fase 10)
**Estado**: ✅ Aceptada

**Contexto**: Cloudflare R2 expone tanto un SDK propio como compatibilidad con la API S3 de AWS (recomendada en docs oficiales). Necesitamos subir assets de migración (imágenes optimizadas) a un bucket público.

**Decisión**: Usar **boto3** apuntando al endpoint `https://<account_id>.r2.cloudflarestorage.com`.

**Consecuencias**:
- ✅ boto3 está bien soportado, tipado y documentado; el SDK Cloudflare-only es más joven y con menos integraciones.
- ✅ Si en el futuro migramos a AWS S3 o Backblaze B2 (también S3-compat), cambia solo el `endpoint_url` y las credenciales.
- ✅ Las features que usamos (`put_object`, `head_object`, `delete_object`, `Metadata`) están 100% cubiertas por R2 S3-compat.
- ⚠️ Las features propietarias de R2 (Public URLs por bucket, lifecycle rules) requieren la API Cloudflare nativa; las configuramos vía dashboard.
- ⚠️ boto3 añade ~7MB de dep tree; el coste de arranque del worker sube un par de cientos de ms. Aceptable.

---

## ADR-027 — Sync ClickUp ↔ residual_tasks con `clickup_task_id` como join key

**Fecha**: 2026-05-13 (Fase 10)
**Estado**: ✅ Aceptada

**Contexto**: Las tareas residuales que generan los subagentes viven en `residual_tasks`. El equipo trabaja en ClickUp. Necesitamos un mapping estable, bidireccional, sin duplicación.

**Alternativas consideradas**:
1. **Custom field en ClickUp con `residual_task_id`**: requiere mantener el custom field manualmente; frágil.
2. **Columna nativa `clickup_task_id`** + tag `wcm-residual-<id>` en ClickUp.

**Decisión**: Opción 2.
- La columna `residual_tasks.clickup_task_id` ya existe en el schema (Fase 1).
- Al crear una tarea ClickUp se añade el tag `wcm-residual-<id>` para que el operador localice la residual desde ClickUp.
- El webhook entrante (Fase 5) ya cierra el loop: completar en ClickUp ⇒ `residual_tasks.status=DONE`.
- El sync saliente (`ClickupSyncerAgent`) se ejecuta manualmente con `enqueue_residual_sync_clickup(project_id)` o automáticamente al final del pipeline.
- Prioridades: BLOCKING_GO_LIVE→1, CLIENT_CONFIG→2, VISUAL_CONTENT/OTHER→3, POST_GO_LIVE→4.

**Consecuencias**:
- ✅ Mapping sencillo de razonar; sin custom fields configurables.
- ✅ El webhook entrante ya estaba listo — Fase 10 solo añade el agent saliente.
- ⚠️ Si alguien borra manualmente una tarea ClickUp, la `residual_task` queda con `clickup_task_id` apuntando a un id muerto. El re-sync detecta el 404 y lo loggea como warning sin bloquear.

---

## ADR-028 — Observabilidad: Sentry + structlog + Logtail, todo perezoso

**Fecha**: 2026-05-13 (Fase 11)
**Estado**: ✅ Aceptada

**Contexto**: Necesitamos tres capas de observabilidad: errores con stack trace y contexto (APM/error tracking), logs estructurados para búsqueda y análisis, y métricas para alertas.

Candidatos: Datadog (caro, exagerado), Honeycomb (excelente pero $$$ para nuestro volumen), OpenTelemetry self-hosted (overhead operativo alto), o el combo **Sentry (errores) + Better Stack/Logtail (logs) + Prometheus (métricas)** — coste $0 en tiers gratuitos para nuestro volumen MVP.

**Decisión**:
- **Sentry SDK** en `apps/api`, `apps/worker` y `apps/dashboard`. Tres DSNs separados (`SENTRY_DSN_API`, `SENTRY_DSN_WORKER`, `SENTRY_DSN_DASHBOARD` / `NEXT_PUBLIC_SENTRY_DSN`) para tener componentes separados en el panel.
- **structlog** como abstracción única de logging en API y worker. JSON renderer en producción (compatible con cualquier ingester); ConsoleRenderer en dev.
- **Logtail (Better Stack)** opcional vía `LOGTAIL_SOURCE_TOKEN`. El handler se añade al root logger si el token está; si no, no-op.
- **Sin colores en logs** en cualquier entorno: queremos redirigir stdout a journald/archivos sin escape codes ANSI estropeando los logs.
- **PII off** por defecto (`send_default_pii=False` en Sentry SDK). El dashboard interno no necesita enviar emails ni nombres de leads a Sentry.

**Perezoso por diseño**:
- `init_sentry(dsn=None)` devuelve `False` sin tocar nada.
- `setup_logtail_handler(source_token=None)` devuelve `False` y no añade handler.
- `configure_logging()` siempre se ejecuta — es el único setup que aporta valor sin credenciales externas.

**Consecuencias**:
- ✅ Producción puede activar/desactivar Sentry y Logtail con un `systemctl restart` tras editar `.env`. No requiere redeploy.
- ✅ Tests no tocan red ni necesitan mockear servicios externos: sin DSN simplemente no inicializan.
- ✅ Stack 100% gratuito en MVP (Sentry free tier 5k eventos/mes, Logtail free tier 1GB/mes).
- ⚠️ structlog + stdlib logging tienen una curva de aprendizaje para el equipo. Mitigación: `logging.getLogger(...)` sigue funcionando y produce el mismo JSON.
- ⚠️ El JSON renderer pierde colores y formato amigable en producción. Compensación: cualquier ingester (Logtail, Datadog, etc.) consume JSON directamente.

---

## ADR-029 — Métricas con Prometheus (registry propio, sin exporter externo)

**Fecha**: 2026-05-13 (Fase 11)
**Estado**: ✅ Aceptada

**Contexto**: Necesitamos métricas para tasa de requests, latencia, tasks Celery ejecutadas, y agent runs. Alternativas: StatsD (push), OpenTelemetry metrics (más complejo), o **prometheus-client** Python (in-process, scrape pull).

**Decisión**: prometheus-client con `CollectorRegistry` propio (no el global default) en `apps/api/.../observability/metrics.py` y `apps/worker/.../observability/metrics.py`.

- **Endpoint `GET /metrics`** en la API expone el dump del registry en formato OpenMetrics. Sin auth — es interno por Nginx ACL.
- **Middleware Prometheus** en FastAPI registra `wcm_http_requests_total` (Counter) y `wcm_http_request_duration_seconds` (Histogram).
- **Worker**: Celery signals (`task_prerun`, `task_postrun`) registran `wcm_celery_tasks_total` y `wcm_celery_task_duration_seconds`. Context managers `observe_agent` y `observe_celery_task` para instrumentación inline cuando hace falta.
- **Cardinalidad controlada**: `path` se toma del route template (`/projects/{id}` no `/projects/42`) para no explotar Prometheus con un counter por cada ID.

**Por qué registry propio**: evita conflicts en tests (las métricas del default registry persisten entre tests). El propio registry es importado donde se necesita.

**Consecuencias**:
- ✅ Setup mínimo: un endpoint y un middleware.
- ✅ Compatible con cualquier scraper Prometheus, Grafana Agent, Datadog (con `prometheus_check`), VictoriaMetrics, etc.
- ✅ Tests deterministas (sin métricas Python GC del default registry contaminando el output).
- ⚠️ Modelo pull: alguien tiene que scrapeear `/metrics`. En producción (WHM, Fase 12) la opción más simple es Grafana Cloud con el Agent, o un Prometheus self-hosted en el propio servidor.
- ⚠️ El worker no expone `/metrics` propio (no es un servidor HTTP). En Fase 12 lo expondremos vía un sidecar simple o `prometheus-client.start_http_server(9000)` dentro del proceso.

---

## ADR-030 — systemd nativo + 4 units + target agregado

**Fecha**: 2026-05-13 (Fase 12)
**Estado**: ✅ Aceptada

**Contexto**: La regla #1 del proyecto prohíbe Docker (CLAUDE.md). Necesitamos un mecanismo de gestión de procesos que sea: estándar en distros Linux, integrable con journald, con hardening robusto, sin runtime adicional. Candidatos: systemd, Supervisor, OpenRC, runit, bare `nohup`.

**Decisión**: **systemd** como sistema de gestión de procesos. Cuatro units:

1. `wcm-api.service` — uvicorn (2 workers) sirviendo FastAPI en 127.0.0.1:8000.
2. `wcm-worker.service` — celery worker con concurrency configurable.
3. `wcm-beat.service` — celery beat (único en el cluster — vital).
4. `wcm-dashboard.service` — Next.js standalone (`node server.js`) en 127.0.0.1:3000.
5. `wcm.target` — agrega las 4 units; `systemctl start wcm.target` arranca todo.

Cada `.service` aplica hardening:
- `NoNewPrivileges=true`, `ProtectSystem=strict`, `ProtectHome=read-only`
- `PrivateTmp=true`, `PrivateDevices=true`
- `ProtectKernelTunables/Modules/ControlGroups=true`
- `RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6`
- `LockPersonality=true`, `RestrictRealtime=true`, `RestrictNamespaces=true`
- API + worker: `SystemCallFilter=@system-service` (filtro syscalls)
- `ReadWritePaths` explícito (solo `.cache`, `logs`, `work`)
- `User=webcafeina` (usuario sistema sin root)

Las units son **templates** con variables `${WCM_APP_DIR}`, `${WCM_USER}`, `${WCM_PORT_*}` que `infra/whm-setup/03-install-units.sh` renderiza con `envsubst` antes de copiar a `/etc/systemd/system/`.

**Consecuencias**:
- ✅ Sin runtime adicional (Docker, k8s) — systemd ya está en cualquier Linux.
- ✅ Logs directamente en `journalctl -u wcm-api -f`.
- ✅ Restart automático en fallo (`Restart=on-failure`).
- ✅ Hardening contra escalada de privilegios + escapes de filesystem.
- ⚠️ Beat NUNCA debe escalar a >1 instancia (duplicaría tasks programadas). Si en el futuro hace falta HA, migrar a `celery-redbeat` con lock en Redis.
- ⚠️ Para deploy sin password, requiere reglas sudoers explícitas (documentadas en runbook).

---

## ADR-031 — Topología single-server WHM/cPanel; multi-nodo diferido

**Fecha**: 2026-05-13 (Fase 12)
**Estado**: ✅ Aceptada

**Contexto**: La empresa ya tiene infra WHM/cPanel (AlmaLinux + cPanel + AutoSSL + backup nativo) en producción para otros sitios. Para Webcafeína Migrator inicial, ¿desplegar en un nodo único reutilizando esa infra, o salir a un esquema multi-nodo desde el principio (load balancer + 2× API + worker pool + DB managed)?

**Decisión**: **Single-server WHM/cPanel** en MVP. Todo en un nodo:
- Nginx (cPanel-managed) → reverse proxy a API + Dashboard.
- API + Worker + Beat + Dashboard como systemd units en el mismo host.
- Postgres + Redis locales.
- Cloudflare R2 como único storage externo (assets).

**Razones**:
- Volumen MVP: <100 migraciones/mes + <10k leads/mes. Cabe holgado en un VPS de 4 vCPU / 8GB RAM.
- Coste fijo: 1 servidor WHM (~50€/mes) vs. multi-nodo en cloud (~250€/mes para mismo SLO).
- AutoSSL + backup managed por cPanel reducen overhead operativo.
- Trazabilidad: todo en un journald, un Postgres, un Redis.

**Cuándo abandonar este modelo**:
- API > 200 RPS sostenidos → mover API a un segundo nodo + LB.
- Worker queue lag persistente → escalar concurrency o nodos.
- DB > 50GB o QPS > 200 → migrar a Postgres managed.

**Consecuencias**:
- ✅ Setup completo automatizable con 5 scripts en `infra/whm-setup/`.
- ✅ Deploy con `bash infra/deploy/deploy.sh main` (idempotente, con rollback).
- ✅ CI/CD via GitHub Actions: `ci.yml` (tests automáticos) + `deploy-production.yml` (trigger manual con SSH + script).
- ⚠️ SPOF: si el nodo cae, todo cae. Mitigación: `pg_dump` diario + snapshots WHM nativos.
- ⚠️ Beat depende de que el nodo no se reinicie en mid-task de retention sweep. Mitigación: `task_acks_late=true` + idempotencia en cada task.

---

## Cómo añadir una nueva decisión

1. Incrementar `ADR-NNN`.
2. Añadir entrada con: Fecha, Estado, Contexto, Decisión, Consecuencias.
3. Si supersede una decisión previa, marcar la anterior como "🟥 Superseded by ADR-MMM".
4. Commit con `docs(adr): ADR-NNN <título>`.
