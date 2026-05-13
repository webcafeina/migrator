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

## Cómo añadir una nueva decisión

1. Incrementar `ADR-NNN`.
2. Añadir entrada con: Fecha, Estado, Contexto, Decisión, Consecuencias.
3. Si supersede una decisión previa, marcar la anterior como "🟥 Superseded by ADR-MMM".
4. Commit con `docs(adr): ADR-NNN <título>`.
