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
**Estado**: ❌ SUPERSEDED por ADR-035 (2026-05-15)

**Contexto** (lectura inicial, parcialmente errónea): En macOS, archivos creados dentro de un directorio `.venv/` heredan el flag `UF_HIDDEN`. Python 3.14 introdujo en `site.py` un skip explícito de `.pth` files con flag hidden. Resultado: `pip install -e` instala correctamente pero los paquetes editable no son importables hasta que se quite el flag manualmente.

**Decisión** (ineficaz en la práctica): Mantener `pip install -e` como mecanismo estándar y proporcionar `scripts/fix-venv-hidden-pth.sh` que ejecuta `chflags nohidden` sobre todos los `*.pth` del venv.

**Por qué se invalida**: el diagnóstico atribuyó el bug a una heurística inexistente del propio macOS. La causa real es **iCloud Drive sincronizando `~/Desktop/`** y reaplicando `UF_HIDDEN` sobre los ficheros bajo cualquier directorio dotted cada pocos segundos. Verificado empíricamente: `chflags nohidden` sobre un `.pth` dentro de `.venv/` queda revertido en <5 s; el mismo `chflags` sobre un `.pth` en `/tmp/` se mantiene indefinidamente. Por eso el script funcionaba en pruebas aisladas pero fallaba al arrancar la stack.

Issue tracking interno: **WCM-008** (cerrado).

Ver ADR-035 para la solución actual (`venv.nosync/` + symlink `venv`).

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

## ADR-032 — Estrategia e2e: Playwright (dashboard) + pipeline test (worker)

**Fecha**: 2026-05-13 (Fase 13)
**Estado**: ✅ Aceptada

**Contexto**: Tests unitarios e integration sólos no detectan regresiones en flujos completos: login → list → action en el dashboard; ni pipeline orchestrator + agentes encadenados produciendo BricksPage + ResidualTasks. Necesitamos e2e sin depender de sandbox real (que se construye en Fase 14+).

**Decisión**: Dos caminos paralelos:

1. **Dashboard e2e con Playwright** (`apps/dashboard/tests/e2e/`):
   - `webServer` arranca `next dev -p 3100` durante los tests.
   - Todas las llamadas a `/api/v1/*` se interceptan con `page.route()` y se sirven fixtures controladas (`apps/dashboard/tests/e2e/fixtures/api-mocks.ts`).
   - Sin red real, sin servidor API real.
   - **Visual regression** con `expect(page).toHaveScreenshot()` + baseline en `__screenshots__/`, tolerance `maxDiffPixelRatio: 0.01`.
   - CI: `playwright install --with-deps chromium` + ejecución headless. Visual specs se omiten en CI hasta tener baselines estables (`--ignore-snapshots`).
   - Locales en español (`locale: "es-ES"`, `timezoneId: "Europe/Madrid"`).
2. **Pipeline e2e Python** (`tests/e2e/test_full_migration_pipeline.py`):
   - Instancia `Orchestrator` real con stub agents que replican la semántica de los reales (crean ScrapedPage / BricksPage / ResidualTask reales).
   - Fixture `stateful_session` en memoria (no Postgres) que persiste objetos por tipo.
   - Verifica: completado de fases en orden, fallo en required bloquea (BLOCKED_HUMAN_INPUT), fallo en opcional continúa pero outcome=QA_FAILED, conditional skip por `condition_attr`.
   - Un test extra usa el fingerprinter real contra el HTML Wix fixture.

**Lo que NO cubrimos** (post-MVP, sandbox real):
- Migración end-to-end con WP real (REST + SSH).
- R2 real upload + verificación.
- Resend envío real.
- Bricks Builder importando el JSON en una instancia WP real.

**Coverage**: añadido `pytest-cov` con `--cov-config=pytest.ini` que limita el source a paquetes de producción. Threshold mínimo: **70%**. Estado actual: **74.8%**. El CI exige el threshold solo en la run con Python 3.14 (la stable usada en prod).

**CI matrix**: Python `["3.13", "3.14"]` × Node `["20", "22"]`. Detecta regresiones de versión antes de actualizar el servidor.

**Consecuencias**:
- ✅ Suite e2e completa: dashboard + pipeline + fingerprint real.
- ✅ Tests deterministas, sin flakiness por red.
- ✅ Visual regression sirve de tripwire para cambios involuntarios de UI.
- ✅ Coverage 74.8% sin red ni servicios externos.
- ⚠️ Las baselines de visual regression hay que regenerarlas la primera vez en Linux x64 (CI). Para eso: `pnpm e2e:update-snapshots` desde el entorno objetivo y commit.
- ⚠️ Python 3.13 puede empezar a fallar si alguna dep (sentence-transformers) drop support. Si la matrix 3.13 falla en CI, decidimos mantener o quitar.

---

## ADR-033 — Hardening philosophy: defensa en profundidad + audit programado

**Fecha**: 2026-05-14 (Fase 15)
**Estado**: ✅ Aceptada

**Contexto**: Antes del primer release a producción, formalizamos cómo pensamos sobre seguridad operativa para que las próximas versiones no degraden la postura actual.

**Filosofía**:

1. **Defensa en profundidad**, no en perímetro. Cada capa asume que la anterior puede fallar:
   - Nginx ACL + rate-limit por dominio (capa 1).
   - FastAPI middleware con rate-limit por endpoint vía `slowapi` (capa 2).
   - Validación de payload con Pydantic (capa 3).
   - RBAC con `require_role` (capa 4).
   - Doble-check anti-spam en send (lead pudo opted-out entre compose y send) (capa 5).
   - Validador legal v1.0 en composer (capa 6 — no enviamos algo no-conforme aunque las anteriores fallen).
2. **Audit programado** (no reactivo):
   - `pip-audit` y `pnpm audit` cada release.
   - Audit doc en `docs/security/audit-vX.Y.Z.md` por cada bump de versión.
   - Manual review checklist: secrets, HMAC `compare_digest`, `set -euo pipefail`, `require_role`.
3. **Default seguro, opt-in para riesgo**:
   - Sentry `send_default_pii=False` por defecto.
   - `/metrics` y `/health/deep` deny-all + allow internos.
   - Cookie `HttpOnly`, `Secure`, `SameSite=Lax` (a confirmar en deploy WCM-016).
   - CORS lista explícita (nunca `*`).
4. **Trazabilidad sobre prevención**:
   - Todo lo que toca datos personales genera `audit_log` con `legal_ground`.
   - `opt_out_log` permanente.
   - Versión de validador legal persistida en cada `OutreachSequence`.
5. **Rate limiting con `enabled=False` en tests**: para no tener que resetear buckets entre tests. Producción los usa con valores en `apps/api/src/wcm_api/rate_limit.py`. Si rotamos a Redis storage (WCM-017), seguir el mismo patrón.

**Decisión sobre rotación**:
- Secrets (`JWT_SECRET`, `SECRET_KEY`): cada 6 meses.
- API keys externas (Google, Resend, ClickUp): cada 12 meses o tras incidente.
- Bricks license: gestión humana, no auto-rotar.

**Decisión sobre dependencias**:
- Vulnerabilidades **high/critical**: parchar en <72h (override pnpm / pin pip).
- Vulnerabilidades **moderate**: parchar en próximo release.
- Vulnerabilidades **low**: documentar en audit doc, parchar oportunista.

**Decisión sobre revisión legal**:
- WCM-011 abierto: revisión externa por asesor antes de outreach masivo en producción.
- Las plantillas actuales se consideran "borradores aprobados internamente, pendientes de validación externa".

**Consecuencias**:
- ✅ Postura clara para el equipo: cualquier nueva feature debe respetar las 5 capas.
- ✅ Audit doc por release: histórico verificable (regla #11 docs/humanos no aplica a estos).
- ⚠️ Auditoría manual mensual de `audit_log` (runbook §"tareas recurrentes") sigue siendo responsabilidad humana — no automatizamos detección de anomalías en MVP.
- ⚠️ La rotación de secrets requiere coordinación con el equipo (forzar re-login de operadores). Documentado en runbook.

---

## ADR-035 — `venv.nosync/` con symlink `venv` para evitar el bug iCloud + dotted dir

**Fecha**: 2026-05-15
**Estado**: ✅ Aceptada (supersede ADR-016)

**Contexto**: en macOS, cuando el repo vive bajo un directorio sincronizado con iCloud Drive (típicamente `~/Desktop/` o `~/Documents/` con "Desktop & Documents Folders" activado), iCloud reaplica el flag `UF_HIDDEN` sobre cualquier fichero dentro de directorios cuyo nombre empiece por `.` (incluido `.venv/`). Python 3.14 introdujo en `site.py` un skip explícito de `.pth` files con flag hidden — y como iCloud restaura el flag en <5 s, el workaround `chflags nohidden` documentado en ADR-016 fallaba al arrancar la stack: los procesos Python ven los `.pth` como hidden y no importan los paquetes editable.

Diagnóstico empírico (ver WCM-008 cerrado): un `.pth` copiado a `/tmp/test.pth` mantiene el flag `nohidden` indefinidamente; el mismo `.pth` dentro de `.venv/` lo reaplica en <5 s. xattr `com.apple.fileprovider.dir#N` y `com.apple.fileprovider.pinned#PX` confirman que el FileProvider (iCloud Drive) está vigilando el directorio.

**Decisión**: el venv se llama `venv.nosync/` y se expone como `venv/` vía symlink:

```
venv -> venv.nosync
```

- Sufijo `.nosync`: convención reconocida por iCloud Drive para excluir un fichero o directorio de la sincronización. `com.apple.fileprovider` no toca lo que termine en `.nosync`.
- Sin punto inicial: evita la heurística "dot dir = hidden" que macOS aplica para Finder.
- Symlink `venv`: deja todos los scripts (`venv/bin/uvicorn`, `venv/bin/celery`, `venv/bin/python`...) y docs intactos. El usuario y los scripts no necesitan saber del trickery.

**Pasos de remediación aplicados en repo**:
1. `.venv/` borrado, recreado como `venv.nosync/` + symlink `venv`.
2. Reinstalación de los 8 paquetes editables + `greenlet`.
3. `s/.venv\//venv\//g` en README, dev-local.md, release-v0.1.0.md, despliegue.md, playbook-operativo.md, audit-v0.1.0.md, cli/README.md, scripts/README.md, scripts/dev-up.sh, infra/deploy/{deploy,migrate,rollback}.sh, .claude/agents/deployer-systemd.md, ruff.toml.
4. `scripts/fix-venv-hidden-pth.sh` reescrito como aviso de obsolescencia (no se borra para no romper memoria muscular ni docs externas).
5. `.gitignore` añade `venv.nosync/` además de `venv/` y `.venv/`.
6. ADR-016 marcado como SUPERSEDED. WCM-008 cerrado en `ISSUES.md`.

**Consecuencias**:
- ✅ El bug desaparece de raíz: `pip install -e` funciona; los procesos arrancan a la primera; `dev-status.sh` da OK sin pasos manuales intermedios.
- ✅ El día que el repo se mueva fuera de iCloud sync (p. ej. a `~/code/`), el sufijo `.nosync` deja de ser necesario pero no estorba; el symlink se puede simplificar a un venv directo.
- ✅ En Linux/prod (servidor WHM), el problema no existe; ahí el venv se llama `venv/` directamente sin symlink. La doc de despliegue ya refleja el nombre nuevo.
- ⚠️ Cualquier nuevo dev del equipo debe leer la nota de `docs/dev-local.md §1` antes de hacer `python -m venv`. Si crea `.venv` directamente, recae en el bug.
- ⚠️ El symlink `venv` debe quedarse local (no entra a git porque está gitignored), igual que `venv.nosync`.

---

## ADR-036 — Patrón de rediseño visual del dashboard en 5 bloques granulares

**Fecha**: 2026-05-18 (consolidado tras 4 pantallas rediseñadas:
`/leads` v0.4.0, `/` v0.5.0, `/campaigns` v0.6.0, `/projects` v0.7.0;
reforzado con `/projects/[id]` v0.8.0 y agrupación `/errors` +
`/residual-tasks` en v0.9.0; **completado con `/settings` v0.10.0** —
última pantalla del dashboard, que confirmó la variación del patrón
para pantallas no-list).
**Estado**: ✅ Aceptada — ciclo cerrado

**Contexto**: tras el cierre del MVP v0.1.0 (2026-05-14) y una
auditoría visual completa del dashboard (capturas en
`/tmp/wcm-audit/AUDIT.md`), arrancamos un proceso de rediseño
pantalla por pantalla con paleta y tipografía fijas (la marca WCM no
cambia). Tras 4 pantallas rediseñadas con el mismo proceso, el
patrón está consolidado y conviene documentarlo para que se replique
en las pantallas restantes sin volver a inventar.

**Decisión**: cada rediseño se descompone en **5 bloques
granulares**, cada uno con su commit propio:

1. **Backend — endpoint de stats** (`feat(api):`). Endpoint nuevo
   `GET /api/v1/X/stats` con agregados que alimentan el topbar del
   rediseño (counts por status, deltas, valores derivados). 5-10
   tests unit con `AsyncMock side_effect` sobre las execute() y
   `literal_binds` para verificar SQL compilado.

2. **Frontend — componentes presentacionales** (`feat(X):`). Creación
   de componentes en `apps/dashboard/src/app/(app)/X/_components/`.
   Reusar shared (`KpiStrip`, `FilterChips`) o promover desde
   `_components/` específico a `apps/dashboard/src/components/` cuando
   un componente sirve a 2+ páginas (`git mv` preserva historial).
   Tests Vitest con `renderToString` (smoke) y/o
   `@testing-library/react` (interactividad). Si el componente es
   Client con `useTransition + async`, anticipar 3-5 tests `.skip()`
   por bug React 19 + happy-dom (WCM-036).

3. **Frontend — refactor `page.tsx`** (`feat(X):`). Server Component
   que fetcha en paralelo lista + stats + datos auxiliares con
   `.catch()` defensivo. Layout consistente:
   - Header: título + descripción 1-línea + acción primaria lima.
   - `KpiStrip` con 4-6 KPIs en línea (responsive `flex-wrap`).
   - (Opcional) `FilterChips` con URL state y counts de stats globales.
   - Tabla densa o empty state contextual.

4. **Frontend — pulido** (`feat(X):`). Tres cosas coordinadas:
   - 2 empty states diferenciados: `EmptyX` (sistema vacío, card lima
     con onboarding + CTAs) vs `EmptyFilterResult` (filtro deja 0,
     card neutra con instrucción de quitar filtro).
   - Responsive verificado en 3 viewports (1440 / 900 / 600). Tablas
     densas con `hideUntil="md" | "lg"` por columna.
   - Microcopy: header del listado refleja filtro activo
     (`X resultados · filtrado por <status castellano>`).

5. **Tests — spec Playwright** (`test(X):`). 6-9 specs con la mitad
   ejecutables (header, CTA primario, accesibilidad de form) y la
   mitad marcados `test.skip(SSR_BLOCKED, "WCM-021")` para contenido
   del Server Component. Cuando MSW node esté (WCM-021), los
   skipped pasan automáticamente.

**Componentes compartidos**: cuando un componente sirve a 2+
páginas, se promueve de `_components/` específico a
`apps/dashboard/src/components/`. Ejemplos hasta hoy:
- `FilterChips` (v0.5.0): de `/leads/_components/` a `components/`.
- `KpiStrip` (v0.7.0): de `/_overview/` a `components/`, renombrado
  desde `OverviewKpiStrip`.

**Cierre de cada rediseño**: tag SemVer (minor para rediseño nuevo,
patch para hotfix) + `gh release create` con notas en castellano
detallando Added/Changed/Fixed/Decisions/Tests. Preflight obligatorio
**incluyendo `pnpm lint`** (lección de v0.6.0 → v0.6.1: next lint
no se ejecuta con tsc/vitest).

**Consecuencias**:
- ✅ Cadencia predecible: ~5 commits + 1 release por pantalla, en
  sesiones de ~2-3 horas cada una.
- ✅ Cada commit revisable de forma independiente (granular >
  monolítico).
- ✅ Componentes shared crecen orgánicamente sin sobre-diseño
  prematuro.
- ✅ Tests escalan con cada rediseño (de 410 totales en MVP a 562 en
  v0.7.0 sin esfuerzo concentrado).
- ⚠️ El bloque 5 (tests) sigue limitado por WCM-021 (MSW node):
  muchos specs Playwright quedan `.skip()` hasta entonces. La
  cobertura "real" vive en vitest del componente + spec mínima
  ejecutable.
- ⚠️ Sin auditoría visual no aplicable a pantallas donde no hay datos
  reales en BD (caso `/projects/[id]` WCM-034). Hay que diseñar
  contra el schema + completar la verificación visual cuando lleguen
  los primeros datos en producción.

Releases que materializan este patrón: v0.4.0, v0.5.0, v0.6.0,
v0.7.0, v0.8.0, v0.9.0, v0.10.0 (cierre). Detalle de cada bloque en
`STATE.md` §"Sesiones post-MVP".

**Agrupación de 2 pantallas en una release** (caso v0.9.0): cuando 2
pantallas comparten patrón exacto (lista plana + filtro por enum, sin
master-detail ni subpáginas), pueden meterse en la misma release con
un commit por bloque que toca ambas a la vez. Reduce overhead de
release sin sacrificar granularidad. NO aplicable cuando las pantallas
tienen schemas o componentes claramente distintos.

**Variación para pantallas no-list** (caso v0.10.0 `/settings`): el
patrón se adapta cuando la pantalla es informativa/configuración en
vez de listado:
- **Bloque 1** sigue siendo un endpoint backend dedicado, pero no
  agrega counts (`/stats`) sino runtime info (`/system/info`). Mismo
  beneficio: una fuente única de verdad que el dashboard consume.
- **Bloque 4** no usa `FilterChips` ni 2 empty states (no hay nada
  que filtrar ni vaciar). Se reduce a verificación responsive +
  microcopy.
- **Resto idéntico**: componentes presentacionales en
  `_components/`, refactor `page.tsx` denso con kv-grid en lugar de
  KpiStrip, spec Playwright con guardias específicas (en `/settings`
  la guardia "no menciona Fase 14" es análoga a la "no menciona
  Fase 10" de `/projects/[id]/diff` v0.8.0 — ambas previenen
  regresiones de mentiras vaporware).

**Cierre del ciclo (v0.10.0)**: 11/11 pantallas operativas
rediseñadas. `/login` queda fuera porque vive en otro app group con
su propio layout. Total: 6 sprints (v0.4.0 → v0.10.0) en 4 días
calendario, ~5 commits + 1 release por sprint. Componentes shared
estabilizados en `apps/dashboard/src/components/` (`FilterChips`,
`KpiStrip`); cada nuevo componente shared exigió 2+ páginas como
prerequisito antes de promoverse — sin abstracciones prematuras.

---

## ADR-037 — Bricks bloqueante en preflight; GF/WC informativos

**Fecha**: 2026-05-19 (post-v0.19.0, sprint de revisión de decisiones)
**Estado**: ✅ Aceptada

**Contexto**: El preflight (`POST /projects/{id}/preflight`) hace HEAD a 3 endpoints REST para detectar plugins instalados en el WP destino: Bricks Builder, Gravity Forms, WooCommerce. Hasta esta decisión, los 3 se trataban igual — como **warnings informativos** que no bloqueaban el botón "Crear y arrancar pipeline". El razonamiento original era "el pipeline degrada elegantemente si falta cualquier plugin".

El problema: los 3 plugins NO son equivalentes en consecuencias.

- **Gravity Forms ausente**: `forms-rebuilder` detecta, genera ResidualTask "instalar GF y configurar manualmente" y la fase salta. El operador instala después, sin pérdida.
- **WooCommerce ausente**: idem con `migrate_woo`.
- **Bricks Builder ausente**: el `wp-deployer` crea páginas en WP (`status=draft`), pero el `bricks_json` se escribe en el post meta `_bricks_page_content_2` que **solo Bricks renderiza**. Sin Bricks, las páginas quedan **completamente vacías** en el frontend (post_content está vacío también — Bricks no usa post_content). El operador no se entera hasta que abre el dominio destino y ve páginas en blanco.

El comportamiento original mezclaba un nivel crítico (Bricks) con dos opcionales (GF, WC). Permitía arrancar el pipeline sin Bricks instalado, lo que producía un deploy técnicamente exitoso pero comercialmente inútil.

**Decisión**: En `wcm_api.services.preflight.run_preflight`, tratar **Bricks como bloqueante** (incluirlo en `blocking_issues` con mensaje específico) y mantener GF/WC como warnings. La UI (`PreflightDisplay > PluginsCard`) pinta la card en rojo (`text-wcm-danger`) si Bricks falta, en ámbar si solo faltan GF/WC, en verde si todos OK. Tag visible "bloqueante" junto al item Bricks cuando falla. Microcopy específico sustituye al genérico de "residuales" cuando Bricks falta.

**Consecuencias**:

- ✅ Refleja la realidad técnica: sin Bricks, el deploy no tiene valor visible.
- ✅ No bloquea proyectos corporativos sin ecommerce (WC ausente sigue siendo warning, no impide arrancar).
- ✅ Cambio mínimo de complejidad: ~40 LOC backend + frontend + tests.
- ✅ Refuerza el patrón "el preflight es la garantía de que el deploy va a entregar valor".
- ⚠️ Sigue siendo posible falso negativo si Bricks está activo pero `/wp-json/bricks/v1/` no responde (configuración del sitio rara). En ese caso el operador no podría arrancar aunque Bricks esté operativo. Mitigación: el mensaje del bloqueante dice "no detectado en destino", no "no instalado" — el operador puede verificar manualmente y, si Bricks está activo pero no expone REST, hay un escape vía `PATCH /api/v1/projects/{id}` para forzar el arranque (avanzado).
- ⚠️ Si en futuro queremos `forms-rebuilder` o `migrate_woo` también bloqueantes cuando el proyecto los necesite (`has_ecommerce=true` + WC ausente → bloqueante), la opción es ADR-04X "bloqueante condicional" — fuera de scope hoy.

**Implementación**: 4 tests backend (`test_preflight_service.py`) cubren Bricks ausente, GF/WC ausentes, todos presentes, Bricks + WP destino ambos bloqueantes. 2 tests frontend (`preflight-display.test.tsx`) cubren las variantes visuales nuevas.

---

## ADR-038 — WPML manual confirmado; revisión cuando ≥3 multilangs/año

**Fecha**: 2026-05-19 (sprint de revisión de decisiones, post-v0.19.0)
**Estado**: ✅ Aceptada (provisional — revisar con datos de uso)

**Contexto**: Webcafeína no tiene licencia WPML. El agente `wpml-configurator` (v0.17.0+) NUNCA instala ni configura nada en el destino — solo genera UNA ResidualTask BLOCKING muy detallada con guía paso a paso de configuración manual (6 pasos, ~30 min base + 5 min por página secundaria).

Al revisar esta decisión se valoraron 4 alternativas:

1. **Mantener actual**: $0 inversión, 1-3h manuales por migración multilang.
2. **Comprar licencia + fase sigue manual**: $99/año, sigue 1-2h manuales.
3. **Comprar licencia + automatizar `wpml-configurator` real**: $99/año + 5-7 días desarrollo, reduce a 5-15 min por migración.
4. **Soporte opcional con licencia del cliente**: 7-10 días + flujo de captura de clave.

**Decisión**: **Mantener opción 1**. Posponemos la inversión en automatizar WPML hasta tener datos reales de cuántas migraciones multilang aceptamos al año.

Razones:

- Coste de oportunidad alto: 5-7 días en `wpml-configurator` real antes de validar que el producto encuentra mercado en webs multilang es prematuro.
- La residual actual es lo suficientemente detallada para que cualquier operador la complete sin formación adicional.
- WPML "Multilingual CMS" cuesta $99/año por seat — invertir sin certeza de volumen no escala.
- Primero validar end-to-end con 1-2 migraciones manuales que el flujo multilang funciona correctamente (scraper detecta idiomas, transpiler genera Bricks pages traducidas, etc.). Si los 1-2 pilotos fallan en algo no-WPML, la inversión habría sido en vano.

**Criterio explícito de revisión**: si Webcafeína detecta que está aceptando 3 o más proyectos multilang al año, **abrir revisión inmediata para implementar opción 3** (`wpml-configurator` real). El umbral de 3/año amortiza la licencia + tiempo de desarrollo (~5-7h por proyecto manual × 3 = ~20h vs. ~50h de implementación una vez; el corte está antes pero damos margen).

**Consecuencias**:

- ✅ Cero inversión hoy, cero riesgo técnico.
- ✅ Capacidad de migrar webs multilang sigue existiendo (solo más lenta).
- ⚠️ Cada lead multilang requiere ~1-3h extra de operador + decisión sobre quién compra la licencia (Webcafeína o el cliente). Documentar en el playbook operativo.
- ⚠️ Si Webcafeína decide priorizar leads multilang en prospección comercial, esta decisión debe revisarse antes de captarlos masivamente.

**Métrica de seguimiento**: contar `projects.is_multilang=True` completados por año en el dashboard. Cuando llegue a 3, abrir ADR-04X "automatización WPML".

---

## ADR-039 — Default draft + botón "Publicar todo" único

**Fecha**: 2026-05-19 (sprint de revisión de decisiones, post-v0.19.0)
**Estado**: 🟡 Aceptada — implementación programada para v0.20.0+

**Contexto**: Tras `wp-deployer`, `migrate_woo` y `rebuild_forms`, los recursos creados en el WP destino quedan en estado **draft/inactive**:

| Recurso | Status tras deploy | Quién publica |
|---|---|---|
| Páginas WP | `draft` | Operador o cliente, manualmente desde wp-admin |
| Productos WooCommerce | `draft` | Idem |
| Formularios Gravity | `is_active: "0"` (inactivo) | Idem |

La filosofía original ("nada que toque el frontend hasta que un humano lo apruebe") es correcta — evita deploys nocturnos accidentales, permite QA visual sin que aparezca en Google, refuerza el "go-live" como momento explícito.

Pero la práctica revela 2 problemas:

1. **Trabajo manual repetitivo post-deploy**: 5-10 min de clicks en wp-admin (bulk-select páginas, productos, activar forms uno a uno). Propenso a olvidos.
2. **QA no es 100% representativo**: `visual_diff` y Lighthouse corren contra preview links autenticados (`?preview=true`), pero **menus, redirects y links públicos** solo muestran páginas publicadas. Existe una diferencia silenciosa entre lo que valida el QA y lo que verá el visitante final tras publicar.

Se evaluaron 4 opciones (mantener actual, publish por defecto, flag en wizard, botón único).

**Decisión**: **Mantener default draft/inactive** + añadir **endpoint y UI nuevos "Publicar todo"** que en una sola acción atómica:

- Páginas: `POST /wp/v2/pages/{id}` con `{"status": "publish"}` para cada `bricks_pages.wp_post_id`.
- Productos: `PUT /wc/v3/products/{id}` con `{"status": "publish"}` para cada `woo_products.wp_product_id`.
- Forms: `PUT /gf/v2/forms/{id}` con `is_active: "1"`.
- Genera ResidualTask informativa "Verificar redirects 301 + cache del destino + DNS final (si aplica)".

Restricciones:

- Endpoint `POST /api/v1/projects/{id}/publish` (operator+), requiere `{"confirm": true}` (como rollback).
- Solo permitido si `status ∈ {completed, qa_failed}` — queremos que QA haya corrido al menos una vez.
- UI: botón "Publicar todo" en `<ProjectActions>` cuando status lo permita. Confirmación inline en lima (acción positiva, no roja): "¿Publicar N páginas + M productos + K forms?".
- CLI: `wcm projects publish ID [--yes/-y]` con prompt interactivo como `rollback`.
- Eventos SSE: `publish_phase_event(project_id, "publish", "running"|"completed"|"failed")`.

**Consecuencias**:

- ✅ Conserva seguridad — nada se publica accidentalmente, el "publish" sigue siendo decisión explícita del operador.
- ✅ Elimina 5-10 min de clicks por migración.
- ✅ Coherente con patrón de rollback (acción única con confirmación inline + endpoint con `confirm` obligatorio).
- ✅ El visual_diff puede seguir comparando contra preview (no cambia su comportamiento).
- ⚠️ Tras "Publicar todo" pueden surgir problemas que QA no detectó (menus malformados, redirects circulares en producción). El operador debe revisar visualmente el dominio público tras la publicación.
- ⚠️ NO incluye `publish` de páginas/productos/forms **individualmente** desde el dashboard. Es todo-o-nada. Si el operador quiere publicar solo algunas páginas, lo sigue haciendo desde wp-admin. (Caso edge poco frecuente; añadir granularidad si surge necesidad real).

**Implementación**: programada para sprint v0.20.0+. Estimación ~5-7 días: endpoint + service que itera + UI + CLI + tests (mocks REST + endpoint + integration test contra WP sandbox). Tareas listadas en TaskList con prefijo `[ADR-039]`.

**Status del documento**: hasta que se implemente, el flujo sigue siendo "draft + manual publish via wp-admin". Cuando salga v0.20.0+ con el botón, `docs/flujo-migracion.md` se actualizará para describir el flujo completo de publicación.

---

## ADR-040 — Playwright para todo el scraping del origen (sin branching por builder)

**Fecha**: 2026-05-19 (sprint de revisión de decisiones, post-v0.19.0)
**Estado**: 🟡 Aceptada — implementación programada para v0.20.0+

**Contexto**: `scrape_origin` usa actualmente `httpx` (HTTP simple, sin JavaScript). Funciona bien para webs estáticas (Hostinger AI por SSR, WordPress nativo, sitios corporativos simples) pero **falla silenciosamente** para los 2 builders objetivo principales:

- **Wix Editor X / Studio**: el HTML inicial es un esqueleto + bundle JS gigante. Sin ejecutar JS, BeautifulSoup no encuentra `<h1>`, `<img>`, secciones. `extract_content` devuelve `0 blocks`, `bricks_pages` se generan vacías, `deploy_wp` crea páginas WP con `bricks_json: []`, el destino aparece en blanco. El operador no se entera hasta ver el resultado.
- **Webflow con Interactions / CMS items**: HTML estático razonable, pero animaciones, lazy-load de imágenes y contenido CMS dinámico no aparecen.

Se evaluaron 4 opciones:

1. **Mantener httpx + documentar limitación**: cero cambios pero bloquea Wix/Webflow.
2. **Detectar HTML vacío y FAIL**: hace visible el problema sin resolverlo.
3. **Playwright para Wix/Webflow específicamente; httpx para el resto** (branching por builder): cubre el 95% sin lentificar lo que ya funciona.
4. **Playwright para TODO** (simple swap): máxima cobertura, tiempos ×10-25, memoria pesada.

**Decisión**: **Opción 4 — Playwright para todo el scraping**. Sin branching por builder. El agente `scrape_origin` usa Playwright + Chromium headless para cada página, respetando el `hydration_wait_selector()` que cada extractor define (Wix `[data-mesh-id]`, Webflow `[data-wf-injected]`, Hostinger `[data-hostai-loaded="true"]`).

Razones para preferir simplicidad sobre velocidad:

- Un único camino de código → menos bugs en el branching, menos casos límite.
- Cualquier builder nuevo que añadamos (Squarespace, Shopify, plataforma desconocida) funciona out-of-the-box sin decidir si hidrata o no.
- Lo que ve el operador en su navegador es exactamente lo que scrapeamos — el modelo mental es simple ("Playwright captura como visitante real").
- Los tiempos largos del pipeline son aceptables porque la migración es batch (no real-time). Una migración típica de 10-15 páginas pasaría de ~30s a ~3-5 min de scraping; total del pipeline ~12-25 min. Sigue siendo aceptable para un proceso que el operador no observa segundo a segundo.

**Consecuencias**:

- ✅ **Simplicidad arquitectónica**: 0 branching, 0 lógica condicional. El fetcher es uno solo.
- ✅ Cubre el 100% de builders, incluso los que aún no documentamos.
- ✅ Cero ambigüedad: si la página tiene contenido visible al humano, lo scrapeamos.
- ⚠️ **Tiempos del pipeline mucho más largos**: scraping pasa de ~200ms/página a ~2-5s/página. Migración 30 páginas: ~10 min solo de scraping (antes ~30s). Total pipeline pasa de ~10-15 min a ~15-25 min. Doc `docs/flujo-migracion.md` y email `notify` deben mencionar tiempos esperados realistas.
- ⚠️ **Dependencias SO obligatorias en el worker**: `playwright install-deps && playwright install chromium`. Sin ellas, `scrape_origin` falla con `PlaywrightNotAvailableError` y el pipeline se aborta (fase `required=True`). En cPanel sin acceso root podría no ser posible — el operador necesita servidor con privilegios o instalación manual de Chromium + libs (libnss3, libatk, libxss1, libasound2, libnspr4, libgbm1).
- ⚠️ **Memoria del worker**: Chromium consume ~150-300MB por instancia. Reuso de browser + context (mismo patrón que `screenshot_session` del visual_diff) limita el pico a ~300MB constante. Worker debe tener ≥1GB RAM disponible para no swappear.
- ⚠️ **Sin fallback a httpx**: si Playwright falla en runtime (chromium crashea), la fase FAIL → pipeline aborta (BLOCKED_HUMAN_INPUT). Decisión consciente: opción 3 (branching) sería un escape, pero contradice el principio "Playwright para todo".

**Implementación**: programada para v0.20.0+. Estimación 3-4 días: helper `PlaywrightFetcher` con context manager + browser reuse + refactor `scrape_origin` para usar el fetcher + tests con Playwright real (no mockeable trivialmente, requiere headless en CI) + actualización docs deployment. Tareas listadas en TaskList con prefijo `[ADR-040]`.

**Acción operador antes del primer deploy v0.20.0+**: instalar Playwright en el worker del servidor producción. Documentar en `docs/despliegue.md` los comandos exactos por distro (Debian/Ubuntu vs CentOS/RHEL).

---

## ADR-041 — Botón "Re-arrancar" para proyectos en ROLLED_BACK

**Fecha**: 2026-05-19 (sprint de revisión de decisiones, post-v0.19.0)
**Estado**: 🟡 Aceptada — implementación programada para v0.20.0+

**Contexto**: Tras un rollback exitoso (ADR-039 / v0.19.0), `project.status = ROLLED_BACK` es **terminal**. Desde la UI no hay forma de re-arrancar ese mismo proyecto. Las opciones documentadas eran (a) crear proyecto nuevo desde el wizard, (b) PATCH manual del status vía API.

La filosofía original ("rollback fuerza decisión consciente de replantear") es sensata para el caso "proyecto un desastre, mejor empezar de cero". Pero falla en el ciclo de iteración típico durante el desarrollo de un piloto:

1. Crear proyecto piloto v1.
2. Arrancar pipeline → falla algo (config WP errónea, env var faltante, plugin desactivado).
3. Rollback (limpia páginas creadas).
4. Operador arregla el problema en `.env` o en el WP destino.
5. **Quiere re-arrancar el mismo proyecto** sin perder el preflight, las residuales, las visual_diffs históricos, los bricks_pages transpilados. **Hoy no puede** sin PATCH manual o crear duplicado.

En todos estos casos toda la información del proyecto está intacta en BD. Forzar a recrear desperdicia trabajo y ralentiza el ciclo de iteración.

**Decisión**: Añadir endpoint y UI nuevos "Re-arrancar pipeline" para proyectos en `ROLLED_BACK`. Conserva el historial; solo resetea los timestamps de ejecución y vuelve a encolar la task Celery.

Comportamiento:

- `POST /api/v1/projects/{id}/restart` (operator+, requiere `{"confirm": true}` como rollback).
- Solo permitido si `project.status == ROLLED_BACK`. Cualquier otro status → 409.
- Internamente:
  - `project.status = QUEUED`.
  - `project.started_at = None`.
  - `project.completed_at = None`.
  - `bricks_pages.wp_post_id` ya es NULL desde el rollback (sin tocar).
  - `bricks_pages.bricks_json` se conserva intacto. El próximo pipeline pasará por `scrape_origin` → ... → `transpile_bricks`, que hace UPSERT por (project_id, slug). Si el HTML del origen cambió, se actualiza; si no, idempotente.
  - `visual_diffs` y `qa_reports` históricos NO se borran — son útiles para comparar "primer intento vs segundo". El próximo deploy generará nuevas filas (visual_diffs upsert por page_path, qa_reports inserta histórico nuevo).
  - `residual_tasks` se conservan — el operador puede revisar qué se reportó la vez anterior. Si quiere limpieza, las cierra a mano.
  - Encola `enqueue_project_pipeline(project_id, resume=False)` — pipeline completo desde fase 1.
- UI: en `<ProjectActions>` cuando `status=rolled_back`, mostrar botón "Re-arrancar pipeline" (verde lima, icon `RotateCcw`) con confirmación inline en lima: "¿Re-arrancar este proyecto? Mantendrá toda la información acumulada (visual diffs, residuales, transpilado)".
- CLI: `wcm projects restart ID [--yes/-y]` con prompt `typer.confirm` interactivo.

**Consecuencias**:

- ✅ Cierra el ciclo de iteración en 1 click. No más PATCH manuales ni proyectos duplicados.
- ✅ Conserva todo el historial del proyecto — diagnóstico comparativo posible ("¿qué cambió entre intento 1 y 2?").
- ✅ Coherente con patrones rollback (ADR pendiente) y publish (ADR-039): endpoint dedicado + `confirm` obligatorio + UI con confirmación inline.
- ⚠️ El operador puede re-arrancar sin revisar lo que cambió y caer en el mismo error. Mitigación: el botón se muestra solo en `ROLLED_BACK` (no en `qa_failed`), donde ya hubo un rollback explícito. El operador conoce el contexto.
- ⚠️ Tras re-arrancar, el pipeline se ejecuta desde la fase 1 (no Resume). Si el problema era específico de una fase tardía (ej. wp-deployer), volvemos a hacer scraping y todo el preprocesado. Coste de tiempo aceptable porque al haber pasado por rollback es razonable querer un re-deploy limpio.
- ⚠️ Si en el futuro queremos un "Re-arrancar desde fase X" (resume parcial), sería ADR-04X separado. Hoy solo offrecemos el pipeline completo.

**Implementación**: programada para v0.20.0+. Estimación ~2-3 días: endpoint + UI button + CLI + tests. Tareas listadas en TaskList con prefijo `[ADR-041]`.

---

## ADR-042 — Snapshot SQL pre-deploy + restore en rollback (supersede H1 MVP de ADR-039)

**Fecha**: 2026-05-19 (sprint de revisión de decisiones, post-v0.19.0)
**Estado**: 🟡 Aceptada — implementación programada para v0.20.0+

**Contexto**: El `RollbackAgent` MVP (v0.19.0) hace DELETE solo de páginas WP creadas por `wp-deployer`. **NO** revierte:

- Cambios a páginas existentes pre-migración (no había snapshot).
- Menús nav (Bricks los crea como side-effect de `nav-menu` elements).
- Theme Styles + opciones Bricks (inyectados directamente).
- Productos WooCommerce (post_type=product, no tocado por rollback).
- Forms Gravity Forms (tabla custom GF).
- Media library (imágenes subidas por `optimize_assets`).
- Redirects 301 (plugin Redirection).

Tras N iteraciones de pilotos, el WP destino acumula basura visual y de catálogo. Cada limpieza manual es ~15-30 min de wp-admin.

Durante el primer piloto real, el operador necesitará iterar 5-10 veces hasta dar con la configuración buena (envs, plugins, parámetros). Sin snapshot, cada iteración deja huellas — el siguiente pipeline no parte de un WP "como estaba originalmente".

Se evaluaron 4 opciones (mantener MVP, rollback extendido sin SQL, snapshot SQL completo, opcional con `--full`).

**Decisión**: **Snapshot SQL pre-deploy + restore atómico vía WP-CLI** (opción 3). El rollback pasa a ser **perfecto** (recupera literalmente todo el estado del WP destino al momento previo al deploy), no parcial.

Comportamiento:

1. **Nueva fase `pre_deploy_snapshot`** en el pipeline, insertada justo **antes** de `deploy_wp` (orden: 6.5). `required=False` — si falla, el pipeline sigue pero el operador queda sin posibilidad de rollback completo (residual task informativa).
2. Agente ejecuta vía SSH (reusando `WpCliSshClient` existente):
   ```bash
   wp db export /tmp/wcm-snapshot-{project_id}-{timestamp}.sql \
     --path={wp_path} --add-drop-table
   ```
3. Path persistido en `projects.pre_deploy_snapshot_path` (migración Alembic 0009 — nueva columna nullable VARCHAR(500)) + `projects.pre_deploy_snapshot_at` (TIMESTAMPTZ).
4. **`RollbackAgent` extendido** (supersede comportamiento MVP):
   - Si `pre_deploy_snapshot_path` está poblado y el archivo existe en el servidor → restore via `wp db import {path} --path={wp_path}`. Ignora la lógica anterior de DELETE página-a-página.
   - Si no hay snapshot (proyecto creado antes de v0.20.0+ o snapshot falló) → fallback al rollback actual (DELETE por wp_post_id). Backward compat completo.
5. UI: la confirmación inline del botón Rollback cambia copy si hay snapshot disponible:
   - Con snapshot: "¿Restaurar el WP destino al estado previo al deploy (snapshot del DD/MM HH:MM)? Recupera páginas + productos + menús + opciones + todo el contenido."
   - Sin snapshot: copy actual ("¿Borrar las páginas WP?").
6. **Cleanup de snapshots**: tras restore exitoso, el snapshot se conserva en disco del servidor para auditoría. Snapshot viejo se borra automáticamente cuando un nuevo deploy genera el siguiente snapshot (rotación 1-en-1). Tarea programada por sprint v0.21+ si crece el espacio.

**Consecuencias**:

- ✅ Rollback **realmente atómico**: revierte el estado completo del WP destino, no solo páginas.
- ✅ Iteración rápida durante pilotos: cada pipeline parte de WP "como estaba" sin acumular basura.
- ✅ Reusa infraestructura existente (`WpCliSshClient`, patrón vía SSH del wp-deployer).
- ✅ Backward compat: proyectos pre-v0.20.0+ (sin snapshot) usan el rollback MVP. No rompe nada.
- ⚠️ **Downtime del WP destino durante restore**: `wp db import` lockea tablas ~10-60s según tamaño. Para piloto interno sin tráfico real, irrelevante. Para producción real (cliente final con tráfico), debería mostrar warning visible "el WP destino estará inaccesible ~1 min".
- ⚠️ **Espacio en disco del servidor**: cada snapshot ~10-50 MB. Con rotación 1-en-1 (1 snapshot activo por proyecto), N proyectos × 1 snapshot = ~500 MB para 10 proyectos. Aceptable. Si crece, sprint v0.21+ añade rotación por edad.
- ⚠️ **Requiere root o permisos similares** al `wp db` (CREATE TABLE, DROP TABLE, INSERT). En cPanel típico el usuario MySQL ya los tiene, pero verificar en preflight de v0.20.0+ (nuevo chequeo "puedes hacer wp db export").
- ⚠️ Si el WP destino tiene plugins que mantienen estado externo (caches Redis del propio WP, índices Elasticsearch, etc.), el restore SQL no los toca → quedan inconsistentes. Mitigación: ResidualTask post-restore "invalidar cache y reindexar si aplica".

**Implementación**: programada para v0.20.0+. Estimación ~4-5 días: migración Alembic 0009 + nuevo agente `pre_deploy_snapshot` (sync vía WpCliSshClient + persiste path) + refactor `RollbackAgent` con branching snapshot/MVP + tests con SSH mockeado + actualizar `docs/flujo-migracion.md` y `docs/despliegue.md`. Tareas listadas en TaskList con prefijo `[ADR-042]`.

**Acción operador antes del primer deploy v0.20.0+**: verificar que el usuario MySQL del WP destino tiene permisos `CREATE`, `DROP`, `INSERT`, `SELECT` en su database (cPanel suele darlos por defecto al phpMyAdmin user). Si no, el snapshot falla en preflight.

---

## ADR-043 — Resume salta fases COMPLETED por defecto + selector "Re-ejecutar todo"

**Fecha**: 2026-05-19 (sprint de revisión de decisiones, post-v0.19.0)
**Estado**: 🟡 Aceptada — implementación programada para v0.20.0+

**Contexto**: Cuando un proyecto está en `qa_failed` o `blocked_human_input` y el operador pulsa **Resume**, el `Orchestrator` actual re-recorre **toda la lista de 15 fases**. Las que ya estaban COMPLETED se vuelven a ejecutar — son idempotentes (UPSERT por slug/URL) así que el resultado neto es el mismo, pero **el tiempo de ejecución es igual al pipeline original** (~15-25 min para una migración típica).

Decisión original: simplicidad + robustez ("si algo se desincronizó silenciosamente, re-ejecutar lo arregla"). Sin estado adicional necesario.

El problema en la práctica: el 95% de Resume son "arreglé UN problema, ejecuta solo lo que falta". El operador arregla los `broken_links` (residual), pulsa Resume y espera 15 min para que se ejecute `qa` (~30s) + el resto (~30s). El feedback es malísimo.

Se evaluaron 4 opciones (mantener actual, saltar siempre, saltar + flag, control fino con selección manual de fases).

**Decisión**: **Saltar fases COMPLETED por defecto** + **selector "Re-ejecutar todo desde el principio"** disponible en los 3 frentes (UI, CLI, API). El 5% de casos donde se sospecha corrupción tiene escape explícito.

Comportamiento:

- **`Orchestrator.__init__` gana parámetro `force_rerun_all: bool = False`**. La task Celery `wcm.orchestrator.run_project` lo recibe vía kwargs.
- **`_should_run(spec, project)` extendido**:
  ```python
  if not self.resume: return True            # primer Start: siempre ejecuta
  if self.force_rerun_all: return True       # operador pidió rerun total
  # Resume normal: saltar fases ya COMPLETED
  existing = self._get_existing_phase(project.id, spec.phase_name)
  if existing and existing.status == ProjectPhaseStatus.COMPLETED:
      return False
  return True
  ```
- **`enqueue_project_pipeline(project_id, *, resume=False, force_rerun_all=False)`** propaga el flag.
- **Endpoint `POST /api/v1/projects/{id}/resume?force_rerun_all=true`** (query param opcional, default false).
- **UI — `<ProjectActions>` botón Resume modificado**:
  - Click simple → modo rápido (saltar COMPLETED).
  - Toggle inline junto al botón: checkbox "Re-ejecutar todo desde el principio" (default desmarcado). Si marcado, el POST lleva `?force_rerun_all=true`. Microcopy debajo: "Útil si sospechas que una fase COMPLETED dejó algo inconsistente (raro)".
- **CLI — `wcm projects resume ID [--force-rerun-all/-f]`** con prompt explicativo si el flag está activo: "Re-ejecutará TODAS las 15 fases, no solo las pendientes. Tarda ~15-25 min. ¿Continuar?".

**Consecuencias**:

- ✅ Resume rápido en el 95% de casos: tras arreglar broken_links, Resume tarda ~1-2 min (solo qa + checklist + clickup + notify) en lugar de ~15 min.
- ✅ Feedback inmediato al operador — se acaba la mala UX de "esperar el mismo tiempo que el pipeline original para verificar un fix pequeño".
- ✅ Escape `force_rerun_all` cubre el caso raro de "una fase COMPLETED dejó algo corrupto" (típicamente tras crash del worker, kill -9, etc.).
- ✅ Paridad triple (API + CLI + UI) coherente con la regla de paridad funcional del CLAUDE.md §6.
- ⚠️ Confianza en `project_phases.status` como fuente de verdad. Si el operador edita manualmente la tabla (no debería) o un crash deja el status en COMPLETED erróneamente, el Resume normal lo salta. El flag está para eso.
- ⚠️ Las fases saltadas por COMPLETED **no actualizan timestamps ni incrementan attempt**. Eso podría confundir al diagnóstico: "¿cuándo corrió scrape_origin?" → la última vez que NO se saltó. Aceptable; en logs queda "[skipped: already completed in resume]" para trazabilidad.
- ⚠️ Si una fase COMPLETED depende de output de otra que el operador quiere reejecutar, el flag `--force-rerun-all` es la opción. No hay reejecución selectiva por ahora.

**Implementación**: programada para v0.20.0+. Estimación ~3-4 días: lógica orchestrator + propagación flag (enqueue helper, task Celery kwargs, endpoint, CLI, UI) + tests (saltar COMPLETED, force_rerun_all ignora skip, mezcla con condition_attr) + actualizar `docs/flujo-migracion.md` §3.7 explicando los dos modos. Tareas listadas en TaskList con prefijo `[ADR-043]`.

---

## ADR-044 — Visual diff: residual automática + threshold configurable por proyecto

**Fecha**: 2026-05-19 (sprint de revisión de decisiones, post-v0.19.0)
**Estado**: 🟡 Aceptada — implementación programada para v0.20.0+

**Contexto**: `visual_diff` compara screenshot origen vs destino con `pixelmatch` y produce un `score` por página (0-1). Hoy:

- Solo se persiste en `visual_diffs` + `project.visual_diff_avg_score`.
- UI pinta thumbnails con ScoreBadge (verde ≥85%, ámbar 70-85%, rojo <70%).
- **No genera ResidualTask automática** ni bloquea el pipeline.
- El env `VISUAL_DIFF_THRESHOLD=0.85` existe en `.env.example` pero NO se usa en código (reservado para futuro).

El problema: cada migración requiere ~15-30 min de revisión visual manual del operador (mirar 30 thumbnails, decidir página a página). Y peor: si el operador olvida abrir `/diff` (la fase no es bloqueante), entrega al cliente sin revisar.

Por otro lado, distintos clientes tienen distintas tolerancias visuales. Un piloto interno de pruebas tolera ±25% sin problema (estamos validando el pipeline, no la pixel-perfect-fidelity). Un cliente corporativo exigente exige ≥95%. Hard-codear un umbral global no captura esa variabilidad.

Se evaluaron 5 opciones (mantener, residual con threshold fijo, residual con threshold configurable, bloquear pipeline, threshold por viewport).

**Decisión**: Opción 3 — **residual automática + threshold configurable por proyecto** con cascada de fuentes (default global env → override por proyecto).

Cascada de configuración:

1. **Default global**: `VISUAL_DIFF_RESIDUAL_THRESHOLD` (env, default `0.70`). Usado si el proyecto no tiene override.
2. **Override por proyecto**: `projects.visual_diff_threshold FLOAT NULL` (nueva col Alembic 0010). NULL = usa default global. Float entre 0 y 1.

Comportamiento del agente al final de `visual_diff.run()`:

```python
threshold = (
    project.visual_diff_threshold
    if project.visual_diff_threshold is not None
    else float(os.environ.get("VISUAL_DIFF_RESIDUAL_THRESHOLD", "0.70"))
)
for diff in visual_diff_rows:
    if diff.score >= threshold:
        continue
    ctx.session.add(ResidualTask(
        title=f"Visual diff bajo en {diff.page_path} ({int(diff.score * 100)}%)",
        description="<plantilla con causas posibles + URL overlay + instrucciones>",
        category=ResidualCategory.VISUAL_CONTENT,
        estimated_minutes=10,
        generated_by="visual-diff",
    ))
```

Configuración del threshold por proyecto:

- **Wizard `/projects/new`**: NO lo pide (sobrecarga decisión técnica que el operador típico no necesita ajustar). Default sensato del env.
- **Ficha proyecto `/projects/[id]`**: nueva sección "Configuración avanzada" (collapsible cerrada por defecto) con campo numérico (slider o input 0-100) "Umbral visual diff (genera residual si score < N%)". Default visible: "70% (heredado de env global)". Cambio vía `PATCH /api/v1/projects/{id}` con `visual_diff_threshold`.
- **CLI**: `wcm projects set-visual-threshold ID --value 0.85` (o `--default` para resetear a NULL).
- **API**: `ProjectUpdate` schema gana el campo.

Tras cambiar el threshold, el operador puede re-ejecutar `visual_diff` aisladamente (vía Resume con `force_rerun_all=true` por ahora — la reejecución selectiva de UNA fase es ADR futuro). Las residuales viejas (con threshold antiguo) se conservan; las nuevas usan el threshold nuevo.

**Consecuencias**:

- ✅ Operador no puede olvidar páginas con score bajo — aparecen en el checklist con título descriptivo + URL del overlay.
- ✅ Flexibilidad por cliente: piloto interno ≥0.50, cliente corporativo ≥0.90.
- ✅ Default sensato (0.70 = el rojo de la UI) — proyectos sin configurar tienen comportamiento razonable inmediato.
- ✅ No bloquea el pipeline — la fase sigue `required=False`, la residual es VISUAL_CONTENT (no BLOCKING).
- ⚠️ Falsos positivos posibles (fonts diferentes, widgets dinámicos legítimos). Operador cierra manualmente como DONE — coste ~30s/falso vs ~15 min de revisión manual sin residual.
- ⚠️ El threshold por proyecto requiere migración + UI nueva (sección "Configuración avanzada"). Si nadie ajusta nunca el threshold, la complejidad añadida es overkill. Mitigación: por defecto la sección está cerrada (collapsed), el campo aparece pre-rellenado con el default global mostrado como heredado. Operador típico no la abre.
- ⚠️ El default 0.70 es el threshold "rojo" del ScoreBadge UI. Coherencia visual: si pinta rojo, genera residual. Si pinta ámbar (0.70-0.85), no genera residual (operador lo ve visualmente sin que aparezca en checklist).

**Implementación**: programada para v0.20.0+. Estimación ~3-4 días.

Tareas listadas en TaskList con prefijo `[ADR-044]`:
- Migración Alembic 0010 — `projects.visual_diff_threshold FLOAT NULL`.
- Modelo Project + Schema ProjectRead/ProjectUpdate.
- VisualDiffAgent — generar residuales tras umbral con cascada (project > env).
- UI sección "Configuración avanzada" en `/projects/[id]` + componente collapsible.
- CLI `wcm projects set-visual-threshold ID --value X` (o `--default`).
- Tests (agent con/sin threshold por proyecto, fallback env, residual generada con título correcto, UI collapsible).

`docs/flujo-migracion.md` se actualizará con nota en sección 8.4 (visual_diff) explicando el comportamiento que viene.

---

## ADR-045 — Automatizar historial de pedidos WC + mejorar residual de cupones

**Fecha**: 2026-05-19 (sprint de revisión de decisiones, post-v0.19.0)
**Estado**: 🟡 Aceptada — implementación programada para v0.20.0+

**Contexto**: La decisión MVP original (revisada como E1-E4 del inventario) era **no migrar** historial de pedidos, historial de envíos forms, cupones ni pasarela de pago. Cada uno genera ResidualTask informativa para que el operador lo gestione manualmente.

Tras evaluar caso por caso, Webcafeína decide automatizar **una** de las cuatro (E1 — historial de pedidos) y **mejorar la información** de otra (E3 — cupones, sin automatizar). Las otras dos se mantienen sin cambios (E2 historial forms, E4 pasarela de pago).

Razonamiento:

- **E1 sí**: Webcafeína espera leads e-commerce establecidos con clientes recurrentes que necesitan ver "mis pedidos anteriores" — para ellos el historial es valor real. Wix Stores y Webflow Ecommerce **sí exponen** pedidos vía API con permisos admin, lo que hace la automatización viable cuando el operador captura credenciales en el wizard (`source_access_mode=api`).
- **E3 sí, pero solo mejorar info, no automatizar**: los cupones del origen con códigos específicos (`WIX2024`, `BLACK24`) raramente sirven literal en el destino. El operador casi siempre crea nuevos al lanzar. Pero **listar los cupones detectados** en la residual (con código, descuento, condiciones) le da contexto útil sin asumir la decisión por él.
- **E2 no**: Wix Forms y Webflow Forms no permiten exportar entries vía API pública. La automatización sería imposible sin permisos elevados.
- **E4 no**: 5+ pasarelas (Stripe, Redsys, PayPal, Bizum, etc.) cada una con su API/sandbox/webhooks. Coste de mantenimiento no escala. La residual manual (~30-60 min) es la decisión correcta y duradera.

**Decisión — Parte A: Automatizar E1**:

Solo si **hay credenciales del back** (`project.source_access_mode == "api"` + `source_credentials_encrypted` válido) y `project.has_ecommerce == True`. Sin credenciales API, fallback al comportamiento actual (residual manual).

Comportamiento:

1. **Nueva tabla `woo_orders`** (migración Alembic 0011):
   ```
   id (PK)
   project_id (FK)
   source_order_id (str, ID en origen)
   wp_order_id (int NULL, ID en WC destino tras migración)
   order_number (str)
   customer_email (str, normalized)
   customer_name (str)
   billing_address_json (JSONB)
   shipping_address_json (JSONB)
   line_items_json (JSONB, lista [{sku, qty, price, total}])
   total NUMERIC(12, 2)
   currency CHAR(3)
   status VARCHAR(20)  -- mapeado: completed | processing | pending | refunded | cancelled
   order_date TIMESTAMPTZ
   raw_origin_json (JSONB, dump completo del API por si necesario diagnóstico)
   migrated_at TIMESTAMPTZ NULL
   migration_error TEXT NULL
   ```
2. **Extender adapters Wix/Webflow** con `list_orders()`:
   - `WixApiClient.list_orders()` → `GET /stores/v2/orders` con paginación cursor (Wix Stores API).
   - `WebflowApiClient.list_orders()` → `GET /ecommerce/v1/orders/{site_id}` con paginación.
   - Mapea fields a estructura canónica `OrderInfo` (idéntica para ambos builders).
   - Errores tipados ya existentes (`WixApiAuthError`, etc.).
3. **`WooMigratorAgent` extendido**:
   - Tras migrar productos (lógica actual), si `source_access_mode == "api"` + credenciales válidas:
     - Llama al adapter correspondiente, lista pedidos del origen.
     - Persiste en `woo_orders` (UPSERT por `(project_id, source_order_id)`).
     - Por cada `WooOrder` con `wp_order_id IS NULL`, crea pedido en WC via `POST /wc/v3/orders` con `status=completed` (o el mapeado), `set_paid=false` (no marca pagado — solo migra estructura), `line_items` referenciando SKUs ya migrados.
     - Persiste `wp_order_id` tras éxito.
   - Si fallo individual de pedido → log warning, sigue. ResidualTask "N pedidos fallaron al migrar" si hay >0 errores.
   - Si NO hay credenciales API → comportamiento actual (residual manual "exportar CSV desde origen + WC importer").

**Decisión — Parte B: Mejorar residual de cupones (sin automatizar)**:

El agente NO crea cupones en WC. Pero **lista los detectados** en el origen para que la residual sea accionable:

1. Extender adapters con `list_coupons()`:
   - `WixApiClient.list_coupons()` → `GET /stores/v3/coupons` (si hay).
   - `WebflowApiClient.list_coupons()` → `GET /ecommerce/v1/coupons/{site_id}`.
2. La residual generada incluye en la `description`:
   ```markdown
   ### Cupones detectados en el origen (3)
   
   | Código | Descuento | Condiciones | Activo |
   |--------|-----------|-------------|--------|
   | WELCOME10 | 10% | min. 30€ | sí |
   | BLACK24 | 25% | productos categoría "ofertas" | no (caducó) |
   | FREE-SHIP | envío gratis | min. 50€ | sí |
   
   Decide si los recreas con esos códigos en WC (Marketing → Cupones → 
   Crear) o si prefieres códigos nuevos. WC no soporta el mismo set de 
   condiciones que Wix/Webflow — algunas reglas avanzadas (exclusiones 
   por usuario, fechas custom) requerirán ajuste manual.
   ```
3. Sin credenciales API → la residual sigue siendo genérica como hoy ("Revisar cupones manualmente en el origen y recrear en WC si aplica").

**Consecuencias**:

- ✅ Clientes e-commerce establecidos reciben historial migrado — valor real para Webcafeína al cerrar leads grandes.
- ✅ Cupones: operador tiene contexto sin asumir trabajo de recreación automática (que sería frágil por diferencias de condiciones entre plataformas).
- ✅ Backward compat: proyectos sin credenciales API se comportan como hoy (residual manual).
- ⚠️ **RGPD — datos personales del cliente final**: los pedidos contienen email, nombre y direcciones de los clientes del cliente. Webcafeína actúa como **encargado del tratamiento** (art. 28 RGPD); el cliente (dueño de la web) es el responsable. Necesitamos:
  - Cláusula en el contrato cliente↔Webcafeína autorizando el tratamiento como parte del servicio de migración.
  - Persistencia de `woo_orders` cifrada en reposo (Postgres tiene `pgcrypto`, alternativa Fernet aplicada a `billing_address_json` y `shipping_address_json`).
  - Borrado de `woo_orders` tras N días de la migración completada (default 30 días). Configurable por proyecto en futuro ADR.
  - Auditoría en `audit_log` de cada lectura/escritura masiva de `woo_orders`.
- ⚠️ **Coste de mantenimiento**: las APIs de Wix/Webflow para pedidos cambian. Tests con sandboxes reales necesarios al menos trimestralmente. Documentar en `docs/playbook-operativo.md`.
- ⚠️ **No migra pagos reales** (datos de tarjeta tokens, transactions). Solo cabecera + line items. La pasarela del cliente (E4) seguirá siendo manual.
- ⚠️ Mapeo de status puede tener gaps: Wix tiene `paid|unpaid|refunded|partially_refunded|canceled` (5), WC tiene `pending|processing|on-hold|completed|cancelled|refunded|failed` (7). El mapeo es lossy pero documentado.

**Implementación**: programada para v0.20.0+. Estimación ~6-8 días (la más grande de los ADRs registrados hasta ahora). Sprint dedicado o como bloque grande dentro de v0.20.0.

Tareas listadas en TaskList con prefijo `[ADR-045]`:
- Migración Alembic 0011 — tabla `woo_orders` + cifrado PII.
- Extender `WixApiClient` con `list_orders()` + `list_coupons()`.
- Extender `WebflowApiClient` con `list_orders()` + `list_coupons()`.
- `WooMigratorAgent` extendido (pedidos + plantilla cupones).
- Tarea de borrado programado de `woo_orders` (Celery beat, 30 días).
- Cláusula RGPD para contrato cliente (acción humana — registrada como TODO en `docs/playbook-operativo.md`).

`docs/flujo-migracion.md` se actualizará con nota en sección 8.1 (`migrate_woo`).

---

## ADR-046 — Confirmación de 6 decisiones sin cambios tras revisión

**Fecha**: 2026-05-19 (sprint de revisión de decisiones, post-v0.19.0)
**Estado**: ✅ Aceptada — todas confirmadas tras evaluación explícita

**Contexto**: Durante la revisión sistemática de las 23 decisiones implícitas/explícitas del flujo de migración, 6 fueron evaluadas y se determinó que **el comportamiento actual es correcto sin necesidad de cambios**. Este ADR las registra como confirmadas para que dentro de 6-12 meses, si alguien las cuestiona, vea que ya fueron consideradas y por qué se mantienen.

### Decisión A1 — Credenciales del back del origen son admin-only

**Comportamiento actual**: el endpoint `PUT /api/v1/projects/{id}/source-credentials` requiere rol `admin`. Solo admins pueden introducir/borrar credenciales API de Wix/Webflow.

**Por qué se mantiene**: son secretos del cliente con valor económico (acceso al back de su negocio). El nivel de privilegio "admin" es estricto pero apropiado para evitar exposición accidental. Si un operator necesita configurar credenciales, escala a un admin — es un workflow aceptable.

**Alternativa descartada**: permitir a `operator` para fluidez. Rechazada — Webcafeína prefiere fricción admin sobre riesgo de fuga de credenciales del cliente.

### Decisión A3 — Rollback requiere `{"confirm": true}` en body

**Comportamiento actual**: el endpoint `POST /api/v1/projects/{id}/rollback` exige `{"confirm": true}` en el body. Sin él → 409. Cualquier cliente programático (scripts CI, herramientas terceras) tiene que confirmar explícitamente.

**Por qué se mantiene**: es una acción destructiva (borra páginas WP, no se puede deshacer trivialmente). La doble confirmación (botón inline en UI + body `confirm`) evita disparos accidentales por scripts mal configurados o llamadas API duplicadas.

**Alternativa descartada**: solo confirmación inline en UI, sin `confirm` en body. Rechazada — la UI confirma al humano, el `confirm` en body protege de errores de máquina.

### Decisión B1 — Preflight con 4 chequeos (WP destino, plugins, origen, credenciales back)

**Comportamiento actual**: el preflight ejecuta 4 chequeos en paralelo (`asyncio.gather`, timeout 10s c/u). Más check no añade valor proporcional al coste.

**Por qué se mantiene**: tras la mejora de ADR-037 (Bricks bloqueante), los 4 cubren los failure modes reales del primer arranque: target inaccesible, plugin esencial faltante, origen caído, credenciales API inválidas. Otros checks evaluados (Lighthouse pre-deploy del origen, DNS del target, espacio en disco) tienen ROI bajo — el operador raramente los necesita.

**Alternativa descartada**: añadir más checks. Rechazada — la latencia del preflight (~10s) ya es la máxima tolerable en un wizard interactivo; añadir checks empujaría hacia 20-30s y deterioraría el UX del wizard.

### Decisión C1 — Pipeline secuencial, sin paralelismo entre fases

**Comportamiento actual**: el `Orchestrator` ejecuta las 15 fases una a una en orden, dentro de una sesión SQLAlchemy larga. El paralelismo intra-fase (ej. descargar 5 assets a la vez) sí existe; el inter-fase no.

**Por qué se mantiene**: cada fase tiene dependencias implícitas con la anterior (extract_content necesita scraped_pages, transpile_bricks necesita content_blocks, etc.). Paralelizar requeriría grafo de dependencias explícito + tracking de inputs/outputs, complejidad sustancial. El tiempo total del pipeline (~10-25 min) es aceptable para batch — no es real-time.

**Alternativa descartada**: paralelizar fases independientes (preserve_seo + optimize_assets pueden correr en paralelo, por ejemplo). Rechazada hasta tener evidencia de que el tiempo del pipeline es problema operativo real. Es over-engineering preventivo.

### Decisión D2 — No respeta `robots.txt` en migración (sí en prospección)

**Comportamiento actual**: `scrape_origin` ignora `robots.txt` del origen — accede a todas las URLs accesibles. La fase de **prospección** comercial sí lo respeta (es scraping no consentido).

**Por qué se mantiene**: en migración el cliente (dueño del origen) **nos da consentimiento explícito** al crearse el proyecto. Es "su" web — `robots.txt` es directiva para crawlers terceros, no para el dueño que ha contratado servicio de migración. La distinción está bien hecha y es legal/éticamente correcta.

**Alternativa descartada**: respetar `robots.txt` siempre (más conservador). Rechazada — bloquearía migración legítima de áreas como `/admin/`, `/checkout/`, `/cart/` que el cliente sí quiere conservar.

### Decisiones E2 + E4 — No migrar historial de envíos forms ni pasarela de pago

**Comportamiento actual**: el sistema NO migra historial de envíos de formularios (E2) ni configuración de pasarela de pago (E4). Ambos generan ResidualTask informativas para que el operador los gestione manualmente.

**Por qué se mantienen** (tras revisión completa en ADR-045 que sí automatizó E1 historial pedidos):

- **E2**: Wix Forms y Webflow Forms **NO exponen entries vía API pública**. La automatización sería técnicamente imposible sin permisos elevados que no obtenemos. El operador exporta manualmente del admin del origen si el cliente lo necesita (raramente lo pide — los entries históricos en sistema migrado tienen poco valor).
- **E4**: 5+ pasarelas (Stripe, Redsys, PayPal, Bizum, etc.), cada una con su API, sandbox, webhooks, plugin WC específico. Coste de mantenimiento no escala. La residual manual (~30-60 min/proyecto) es la decisión correcta y duradera. Cualquier cliente nuevo con pasarela rara abre frente nuevo de mantenimiento.

**Alternativa descartada**: automatizar al menos Stripe (la más común). Rechazada — incluso con UNA pasarela, el coste de mantener integración + tests del sandbox + manejo de webhooks ≈ 15-20 días/año. Mejor 30-60 min/proyecto manual.

---

**Consecuencias generales** de este ADR:

- ✅ Las 6 decisiones quedan **explícitamente confirmadas**. Futuras revisiones (operadores nuevos, auditorías) verán el ADR y entenderán por qué no cambiar.
- ✅ Cero código adicional. Cero coste de implementación.
- ✅ Reduce ruido en sprints futuros — estas 6 no compiten por atención.
- ⚠️ Las decisiones siguen siendo revisables si surge evidencia nueva (cliente exigiendo lo contrario, regulación cambiando, performance issue real). La confirmación es **provisional pero firme**.

---

## ADR-047 — UI sin auto-arranque + endpoint API combinado `POST /projects/with-start`

**Fecha**: 2026-05-19 (sprint de revisión de decisiones, post-v0.19.0)
**Estado**: 🟡 Aceptada — UI sin cambios; endpoint nuevo programado para v0.20.0+

**Contexto**: Tras el preflight del wizard (paso 4), aparecen 3 botones: "Crear y arrancar pipeline", "Re-ejecutar preflight", "Guardar sin arrancar". El proyecto NUNCA arranca solo, incluso con preflight perfecto. Decisión consciente: el "Start" del pipeline es momento irrevocable a corto plazo, debe ser acción explícita del humano.

Casos donde la doble acción "Crear → Arrancar" se siente burocrática:

- **Piloto interno batch**: Webcafeína quiere probar el pipeline con N URLs en secuencia (validar regresiones, comparar resultados). Click por click es fricción.
- **Trigger desde sistemas externos** (webhook ClickUp, integración CRM al cerrar lead, scripts CI): cada uno requiere lógica adicional para llamar `POST /projects` + `POST /start` secuencialmente.
- **Operador con confianza alta** tras N migraciones exitosas: el doble click se siente innecesario.

Se evaluaron 4 opciones (mantener actual, checkbox auto-arranque, preferencia global, endpoint combinado API).

**Decisión**: **Combinación (a) + (d)** — mantener UI sin cambios (3 botones siempre, "Start" explícito) **+ añadir nuevo endpoint API combinado** `POST /api/v1/projects/with-start` para uso programático.

Razones:

- La UI sigue siendo conservadora: cero footgun para operadores humanos. El modelo mental "nunca arranca solo" se preserva.
- Los scripts batch / webhooks / integraciones tienen su atajo limpio sin tener que orquestar 2 llamadas + manejar el preflight.
- Coste de implementación mínimo (~30 LOC + tests) porque es un combinador de endpoints existentes.

Contrato del endpoint nuevo:

```
POST /api/v1/projects/with-start
Auth: operator+
Body: {
  ...ProjectCreate (mismo schema que POST /projects),
  skip_preflight: bool = false,    # opcional, default false
  force_start: bool = false         # opcional, default false
}
```

Comportamiento:

1. Llama internamente `POST /projects` (crea el proyecto).
2. Si `skip_preflight=false` (default): ejecuta `POST /projects/{id}/preflight`.
   - Si `preflight.can_start=true` → arranca pipeline + devuelve `200 OK` con `{project_id, task_id, preflight_results}`.
   - Si `preflight.can_start=false` → **NO arranca** + devuelve `409 Conflict` con `{project_id, preflight_results, message: "preflight bloqueante, usa force_start=true si entiendes el riesgo"}`. El proyecto QUEDA creado en `queued` — el script puede consultar el preflight y decidir.
3. Si `skip_preflight=true`: arranca directamente sin preflight.
   - Útil para scripts donde el preflight ya se validó antes (re-ejecutar mismo target N veces).
   - **Riesgo**: salta protecciones. Documentar claramente que solo para scripts conscientes.
4. Si `force_start=true` (con `skip_preflight=false`): ejecuta preflight pero arranca aunque `can_start=false`. Devuelve `200 OK` con warnings. Para casos donde el operador sabe que el preflight da falso positivo (raro).

**Consecuencias**:

- ✅ UI intacta — cero cambios visuales, cero riesgo de regresión UX.
- ✅ Scripts/webhooks tienen atajo limpio: 1 llamada vs 2-3.
- ✅ El comportamiento por defecto del endpoint nuevo (sin flags) es seguro: ejecuta preflight, no arranca si bloqueante.
- ✅ Coste mínimo de implementación.
- ⚠️ Dos formas de hacer "crear proyecto" en la API: el endpoint base `POST /projects` (no arranca) y el combinado `POST /projects/with-start` (arranca tras preflight). La documentación OpenAPI debe aclarar el caso de uso de cada uno.
- ⚠️ Los flags `skip_preflight` y `force_start` son escapes peligrosos — solo deberían usarse en scripts conscientes. Documentar prominentemente y considerar marcarlos como `deprecated` si nadie los usa tras 6 meses.
- ⚠️ El endpoint combinado **no** está disponible en la UI ni en CLI. Si surge necesidad real, se añade entonces. Hoy es solo API.

**Implementación**: programada para v0.20.0+. Estimación ~1 día (~30 LOC + 6 tests cubriendo: happy path, preflight bloqueante 409, skip_preflight=true arranca directo, force_start=true ignora bloqueantes, payload inválido propaga 422 del create, 401/403 según rol). Tarea registrada en TaskList con prefijo `[ADR-047]`.

`docs/flujo-migracion.md` no requiere actualización — la sección actual del wizard sigue vigente al 100%. La existencia del endpoint nuevo se documenta solo en OpenAPI + breve mención en `docs/playbook-operativo.md` (cuando se implemente) bajo "Atajos para scripts/automatización".

---

## ADR-048 — `POST /projects/{id}/start` siempre re-ejecuta preflight

**Fecha**: 2026-05-19 (sprint de revisión de decisiones, post-v0.19.0)
**Estado**: 🟡 Aceptada — implementación programada para v0.20.0+

**Contexto**: Hoy el botón "Start" en `/projects/{id}` encola el pipeline directamente sin re-ejecutar preflight. Si el operador hizo el wizard hace 1 hora con bloqueantes y eligió "Guardar sin arrancar", luego puede pulsar Start y arrancar el pipeline con esos bloqueantes olvidados. El operador no recibe alerta — la migración falla (o entrega páginas vacías por Bricks ausente, etc.).

Adicionalmente: aunque el preflight haya pasado verde hace minutos, el WP destino puede haberse caído desde entonces, el plugin puede haberse desactivado, el origen puede estar 503. **El preflight tiene un TTL natural de validez muy corto** porque depende de estado externo volátil.

Se evaluaron 4 opciones (mantener actual, siempre re-ejecutar, cache 5 min, deshabilitar guardar sin arrancar).

**Decisión**: **`POST /api/v1/projects/{id}/start` siempre re-ejecuta preflight antes de encolar**. Sin cache. Sin TTL. Invariante estricta: "Start nunca arranca un pipeline sin preflight fresh OK".

Comportamiento:

1. Cliente llama `POST /api/v1/projects/{id}/start` (o pulsa botón Start en UI, o `wcm projects start ID` en CLI).
2. Endpoint internamente ejecuta `run_preflight(project)` (~10s en el caso típico).
3. Persiste el resultado en `projects.preflight_results_json` + `preflight_at` (sobrescribe el anterior).
4. Si `preflight.can_start == False` → **NO arranca**, devuelve `409 Conflict` con `{preflight_results}` para que el cliente lo vea. El proyecto queda en `queued`.
5. Si `preflight.can_start == True` → marca `status=RUNNING`, encola task Celery, devuelve `202 Accepted` con `{task_id}` como hoy.

Excepción documentada: el endpoint nuevo `POST /api/v1/projects/with-start` (ADR-047) acepta `skip_preflight=true` como flag para scripts conscientes. Eso sigue siendo válido — es endpoint distinto con público distinto (programático, no UI). El endpoint `/start` clásico no admite skip — siempre re-ejecuta.

UX en el dashboard:

- Botón "Start" en `<ProjectActions>` mantiene su apariencia visual.
- Al click, mostrar spinner inline "Ejecutando preflight (≤10s)…".
- Si 409: mostrar toast destructivo con el blocking_issue principal + redirect a `/projects/{id}` (que muestra el preflight actualizado en la UI).
- Si 202: toast success "Encolado · task {task_id[:8]}…" + `router.refresh()` para que el stepper se active.

CLI: `wcm projects start ID` mantiene comportamiento exterior; internamente espera el preflight. Si falla, exit 1 con detalle del primer blocking_issue.

**Consecuencias**:

- ✅ Invariante clara y defendible: **el pipeline NUNCA arranca sin preflight fresh OK**. Modelo mental simple.
- ✅ Detecta cambios en el entorno desde el último preflight (WP caído, plugin desactivado, origen 503). El operador no se sorprende a mitad de pipeline.
- ✅ Sin lógica de cache TTL — código más simple, menos casos límite.
- ✅ Coherente con la filosofía "Start es momento explícito + comprobado" del ADR-047.
- ⚠️ **Penalty UX de ~10s en cada Start**. Operador que acabó wizard hace 30s lo espera de nuevo. Aceptable porque (a) el operador ya esperó en el wizard, (b) la garantía vale el coste, (c) en CLI el delay es invisible si forma parte de un script batch.
- ⚠️ Si el endpoint del preflight tiene un bug que devuelve 5xx, el Start tampoco arranca — preflight pasa a ser dependencia dura del pipeline. Mitigación: el preflight ya tiene `try/except` por check individual; un check que falle no debe romper toda la respuesta (devuelve `ok=false` con `message="error: <tipo>"` y sigue).
- ⚠️ Operador en flujo iterativo (arrancar→fallar→arreglar→arrancar→fallar→...) suma ~10s por iteración. Acumulable pero soportable. Si surge problema real, ADR futuro puede revisitar la opción cache TTL 5 min como concesión.

**Implementación**: programada para v0.20.0+. Estimación ~2 días: refactor del endpoint `start` (invocar `run_preflight` + decidir según `can_start`) + actualizar tests del endpoint + UI spinner durante el preflight + actualizar `docs/flujo-migracion.md` §3.1 (encolado) explicando que ahora Start re-ejecuta preflight. Tarea registrada en TaskList con prefijo `[ADR-048]`.

`POST /api/v1/projects/{id}/resume` se mantiene SIN re-ejecutar preflight (es un reintento, no un arranque nuevo). Si en futuro queremos lo mismo para Resume, será ADR separado.

---

## ADR-049 — `Exception` genérica en fase no required: FAILED pero continúa

**Fecha**: 2026-05-19 (sprint de revisión de decisiones, post-v0.19.0)
**Estado**: 🟡 Aceptada — implementación programada para v0.20.0+

**Contexto**: El `Orchestrator` actual maneja 3 tipos de error en cada fase:

```python
except AgentNotImplementedError:    # SKIPPED + sigue
except AgentError:                    # FAILED + sigue si required=False, aborta si required=True
except Exception:                     # FAILED + aborta SIEMPRE (incluso si required=False)
```

El último caso (catch-all de `Exception`) es **más conservador** que `AgentError`: cualquier excepción no tipada aborta el pipeline aunque la fase sea `required=False`. La intención original: una excepción no esperada sugiere bug, mejor parar a investigar.

El problema en la práctica: hay excepciones legítimas que los agentes no anticiparon como `AgentError` tipado:

- `playwright._impl._errors.Error` si Chromium crashea con un PNG corrupto durante visual_diff.
- `httpx.ConnectError` si el W3C validator está caído (caso raro pero real).
- `PIL.UnidentifiedImageError` si una imagen del origen está corrupta en optimize_assets.

Hoy estas excepciones abortan TODO el pipeline aunque la fase es `required=False`. El operador investiga 30 min para descubrir que era una imagen rota que ya está marcada FAILED en `assets`.

Se evaluaron 4 opciones (mantener, alinear con AgentError, whitelist recuperables, cada agente declara).

**Decisión**: **Opción 2 — `Exception` genérica en fase `required=False` se trata igual que `AgentError`: FAILED + continúa**. La fase queda marcada como `failed_phase` para diagnóstico, pero el pipeline sigue procesando las siguientes fases.

Para `required=True` el comportamiento sigue siendo "aborta el pipeline" (sin cambios).

Comportamiento exacto del catch-all extendido:

```python
except Exception as e:
    log.exception("phase_unexpected_error", extra={"phase": spec.phase_name})
    self._mark_phase(
        project_id, spec.phase_name, ProjectPhaseStatus.FAILED,
        summary=f"{type(e).__name__}: {e}"
    )
    outcome.failed_phase = spec.phase_name
    if spec.required:
        # required → aborta como antes
        project.status = ProjectStatus.BLOCKED_HUMAN_INPUT
        outcome.final_status = ProjectStatus.BLOCKED_HUMAN_INPUT
        self.session.flush()
        return outcome
    # ADR-049: no required → continúa con la siguiente fase
    # (mismo comportamiento que AgentError en no required)
```

**Consecuencias**:

- ✅ Principio simple y predecible: **el flag `required` gobierna lo que para o no**, no el tipo de excepción.
- ✅ Una corrupción aislada (imagen rota, validator W3C caído, Chromium crash en una página) no detiene el pipeline entero. Las fases posteriores corren y entregan el valor parcial.
- ✅ Cambio mínimo (~3 LOC del except + tests). Bajo riesgo.
- ✅ Coherente con la filosofía "el pipeline degrada elegantemente" que ya gobierna `migrate_woo`, `rebuild_forms`, etc.
- ⚠️ Si la excepción es de un problema sistémico (OOM, disco lleno, BD corrupta), las fases siguientes probablemente también fallarán → el pipeline para naturalmente. No perdemos protección frente a problemas graves.
- ⚠️ Operador puede ver "QA_FAILED" al final del pipeline aunque ninguna fase required falló — porque alguna fase no required tuvo Exception genérica. La UI ya muestra `failed_phase` en el header, queda claro qué pasó.
- ⚠️ Los logs structlog con `phase_unexpected_error` siguen siendo críticos para diagnóstico — el operador debe revisar la fase concreta tras un `QA_FAILED`.

**Decisión adicional**: la regla "Exception genérica en `required=True` aborta + BLOCKED" se mantiene **estrictamente** porque las fases required son el camino crítico — un fallo allí no debe enmascararse. La asimetría required/no-required es deliberada.

**Implementación**: programada para v0.20.0+. Estimación ~1 día (3 LOC del orchestrator + 4 tests cubriendo: Exception en required=True sigue abortando, Exception en required=False ahora continúa, AgentError sigue siendo manejada como antes, sin regresión en `failed_phase` tracking). Tarea registrada en TaskList con prefijo `[ADR-049]`.

---

## ADR-050 — Cap configurable por proyecto en `scrape_origin` + residual si se alcanza

**Fecha**: 2026-05-19 (sprint de revisión de decisiones, post-v0.19.0)
**Estado**: 🟡 Aceptada — implementación programada para v0.20.0+

**Contexto**: `scrape_origin` tiene un cap hard-coded:

```python
max_pages = int(ctx.extra.get("max_pages", 50))
```

50 páginas cubre el 80% de leads corporativos (restauración, abogados, dentistas — típicamente 5-30 páginas). Pero hay 3 tipos de leads donde 50 se queda corto:

- **Tiendas Wix/Shopify con muchos productos**: shop con 200 productos = 200 páginas de producto + ~10 estructurales. Cap a 50 = pérdida silenciosa del 75% del catálogo.
- **Blogs activos**: 5 años × 1 post/semana = ~250 posts.
- **Sites multilang**: 20 páginas × 3 idiomas = 60 páginas. Cap a 50 deja un idioma incompleto.

**El cap es silencioso hoy**: no genera residual, el operador no se entera hasta visual_diff o QA (que ven pocas páginas vs lo esperado).

Se evaluaron 4 opciones (mantener, configurable + alerta, eliminar cap, configurable + pausar).

**Decisión**: **Opción 2 — cap configurable por proyecto vía cascada (project > env > default 50)** + **ResidualTask CLIENT_CONFIG si el BFS termina porque alcanzó el cap** (no porque vació el queue).

Cascada de configuración:

1. **Default global**: `SCRAPE_MAX_PAGES_DEFAULT` (env, default `50`).
2. **Override por proyecto**: `projects.max_pages_scrape INT NULL` (nueva col Alembic 0012). NULL = usa default global. Rango válido: 1-500.

Configuración del cap por proyecto:

- **Wizard `/projects/new`**: NO lo pide (sobrecarga decisión técnica del operador típico). Default sensato del env.
- **Ficha proyecto `/projects/[id]`**: campo numérico "Máximo de páginas a scrapear" en la sección **"Configuración avanzada"** (collapsible cerrada por defecto). Esa sección ya se planificó en ADR-044 para `visual_diff_threshold` — esta config se añade al mismo componente, agrupando los campos avanzados en un solo sitio.
- **CLI**: `wcm projects set-max-pages ID --value 200` (o `--default` para reset a NULL).

Comportamiento del agente al terminar el BFS:

```python
max_pages = (
    project.max_pages_scrape
    if project.max_pages_scrape is not None
    else int(os.environ.get("SCRAPE_MAX_PAGES_DEFAULT", "50"))
)
# ... BFS hasta len(results) >= max_pages o to_visit vacío ...

if len(results) >= max_pages and to_visit:
    # Cap alcanzado con URLs pendientes — residual visible
    ctx.session.add(ResidualTask(
        title=f"Scraping cortado a {max_pages} páginas — sitio podría tener más",
        description=(
            f"El scraper alcanzó el límite configurado de {max_pages} páginas. "
            f"Quedaban {len(to_visit)} URLs por procesar en la cola.\n\n"
            f"Si necesitas migrar más, ajusta `max_pages_scrape` en "
            f"`/projects/{project.id}` → Configuración avanzada → "
            f"'Máximo de páginas a scrapear' (default 50, máximo 500). "
            f"Luego re-arranca el pipeline (ADR-041 'Re-arrancar pipeline').\n\n"
            f"URLs detectadas no procesadas (primeras 20):\n"
            + "\n".join(f"- {url}" for url in to_visit[:20])
        ),
        category=ResidualCategory.CLIENT_CONFIG,
        estimated_minutes=5,
        generated_by="scrape-origin",
    ))
```

**Consecuencias**:

- ✅ El default 50 sigue cubriendo el 80% de leads corporativos — no penalty para el caso común.
- ✅ Cap configurable hasta 500 cubre webs grandes (shops, blogs activos, multilang).
- ✅ Pérdida silenciosa eliminada: la residual aparece en el checklist con instrucciones claras + lista de URLs no procesadas (top 20 para diagnóstico).
- ✅ Coherencia: el campo va en la misma sección "Configuración avanzada" que `visual_diff_threshold` (ADR-044). Un solo componente UI agrupa los campos avanzados.
- ✅ Coherente con ADR-041 (Re-arrancar): tras ajustar el cap, el operador re-arranca el proyecto manteniendo todo el historial.
- ⚠️ Cap máximo 500 es arbitrario. Para webs >500 páginas (raras pero existen — wikis, marketplaces, periódicos) habría que subirlo o paginar el scraping. Mitigación: el límite de 500 viene del coste de Playwright (500 páginas × ~3s = ~25 min solo scraping). Con SSE/polling el operador ve el progreso; si surge el caso, ADR futuro discute alternativas (scraping incremental, prioridad por sitemap, etc.).
- ⚠️ Tiempos del pipeline crecen linealmente con `max_pages`. Documentar en `/projects/[id]` config "valor afecta tiempos: 50→~10 min, 200→~30 min, 500→~75 min con Playwright".
- ⚠️ Coste de espacio (R2 / BD) también crece linealmente: 500 páginas × HTML raw + screenshots + visual_diff overlays. Para shops grandes podría sumar GB. Aceptable hoy; revisar si Webcafeína migra muchas shops grandes.

**Implementación**: programada para v0.20.0+. Estimación ~3 días.

Tareas listadas en TaskList con prefijo `[ADR-050]`:
- Migración Alembic 0012 — `projects.max_pages_scrape INT NULL` + CHECK constraint 1≤value≤500.
- Modelo Project + Schema ProjectRead/ProjectUpdate.
- ScraperOriginAgent — cascada (project > env > 50) + residual si cap alcanzado con queue pendiente.
- UI: extender sección "Configuración avanzada" (compartida con ADR-044) con campo "Máximo de páginas a scrapear".
- CLI `wcm projects set-max-pages ID --value X` (o `--default`).
- Tests: cap por proyecto, fallback env, residual generada con title correcto + URLs en queue, default 50 preservado.

`docs/flujo-migracion.md` se actualizará con nota en sección 4.6 (`scrape_origin` — Lo que NO hace) explicando la nueva configurabilidad.

---

## ADR-051 — Adapter API complementa el scraping (no sustituye) — confirmación

**Fecha**: 2026-05-19 (sprint de revisión de decisiones, post-v0.19.0)
**Estado**: ✅ Aceptada (confirmación tras evaluación explícita)

**Contexto**: Cuando un proyecto tiene `source_access_mode='api'` + credenciales válidas Wix/Webflow, el agente `scrape_origin` obtiene la lista canónica de URLs desde el adapter API. Esas URLs se **prepend al `to_visit`** del BFS — el crawler sigue buscando enlaces internos en cada página visitada via `<a href>`.

```python
seed_urls = self._seed_from_api(project)
to_visit = [source_url, *seed_urls]
# BFS sigue buscando enlaces internos en cada página visitada
```

Es decir, la API **complementa** el scraping (aporta URLs canónicas que el BFS podría no descubrir), pero el HTML se sigue obteniendo via fetch público — el BFS de enlaces internos también corre.

Se evaluaron 3 opciones (mantener, API sustituye totalmente, modo configurable por proyecto).

**Decisión**: **Mantener comportamiento actual** — API complementa, BFS también corre.

Razones para no cambiar:

- **Cobertura unión > cualquier fuente sola**: la API lista páginas canónicas del editor (incluso no enlazadas desde menú: legales, drafts publicados, blog posts antiguos). El BFS de enlaces cubre páginas creadas fuera del editor oficial (hooks, redirects custom, hardcoded en otras páginas). La unión es estrictamente mejor.
- **Penalty del BFS "redundante" es mínima**: el set `visited` evita re-fetch. Lo único redundante es parsear `<a href>` con BS4 (~ms por página), inferior al coste de Playwright (~3-5s/página) o el fetch HTTP en sí.
- **La opción 2 (API sustituye) tiene pérdida silenciosa**: gaps de la API (drafts ocultos del editor que se publican públicamente, páginas custom con hooks WordPress-style) no son visibles para el operador. Diagnóstico difícil.
- **La opción 3 (modo configurable) es over-engineering**: un campo técnico que pocos operadores entenderán. Sin caso real que lo justifique, es complejidad gratuita.

**Consecuencias**:

- ✅ Decisión confirmada explícitamente. Si dentro de 6 meses alguien cuestiona "¿por qué hacemos BFS si tenemos la API?", este ADR responde.
- ✅ Cero código adicional, cero coste.
- ⚠️ Si en el futuro detectamos que la API y el BFS producen el mismo set ≥95% del tiempo y el coste del BFS empieza a ser problemático (raro en webs medianas), revisar con datos reales — no a priori.
- ⚠️ La estrategia "complementa" depende de que `_seed_from_api` falle elegantemente (devuelve `[]` si la API cae). Ya implementado en v0.18.0 (fallback silencioso).

---

## ADR-052 — Bloques UNKNOWN: threshold + warning visible en header

**Fecha**: 2026-05-19 (sprint de revisión de decisiones, post-v0.19.0)
**Estado**: 🟡 Aceptada — implementación programada para v0.20.0+

**Contexto**: Cuando un extractor (Wix/Webflow/Hostinger) encuentra una estructura no reconocida, crea un `ContentBlock` con `block_type=UNKNOWN` + `notes` describiendo qué encontró. El `bricks_transpiler` posterior los marca como **residual task** "revisar manualmente este bloque" (VISUAL_CONTENT). La fase termina COMPLETED — los UNKNOWN son metadata, no causan fallo.

Filosofía MVP correcta: mejor entregar 95% que no entregar nada. Una página con 1 UNKNOWN de 20 bloques sigue siendo entregable.

El problema sutil: páginas con **muchos UNKNOWN** son "exitosas" técnicamente pero están vacías visualmente. Ejemplo: hero compleja con widget custom + sección testimonios con structure rara + galería plugin third-party = 3 bloques UNKNOWN sobre 5 totales = página destino prácticamente vacía. El operador ve "extract_content: completed" y no se entera hasta visual_diff (fase 11). Si `visual_diff` no se ejecuta (Playwright no instalado, otros motivos), no se entera nunca.

Las residuales individuales por bloque están en el checklist, pero **sin contexto agregado**: el operador ve "revisar bloque 17 página /servicios", "revisar bloque 23 página /servicios", "revisar bloque 31 página /servicios" — pero no ve "página /servicios tiene 3 de 5 bloques UNKNOWN".

Se evaluaron 4 opciones (mantener, FAIL la fase, threshold + warning, configurable).

**Decisión**: **Opción 3 — threshold + warning visible en el header del proyecto** sin FAIL de la fase.

Threshold sensato:

> Una página se marca como "muchos UNKNOWN" si **`unknown_count >= 3` Y `unknown_count / total_blocks >= 0.5`**.

Es decir: al menos 3 UNKNOWN absolutos Y al menos el 50% del total de la página. Una página con 1 UNKNOWN de 20 NO se marca (ratio 5%); una con 3 UNKNOWN de 5 SÍ (ratio 60%).

Razones:

- El doble criterio (absoluto + ratio) evita falsos positivos: páginas con 2 UNKNOWN de 3 (ratio 67%) no son problema real porque son páginas pequeñas; páginas con 5 UNKNOWN de 50 (ratio 10%) tampoco lo son.
- 3 absolute + 50% ratio captura el caso "página claramente rota" sin disparar el warning para páginas con 1-2 bloques exóticos pero contenido principal OK.

Implementación:

- **Sin nueva columna en BD**: el conteo es **calculable on-the-fly** desde `content_blocks` con una query agregada en el endpoint `GET /api/v1/projects/{id}/summary`. Decisión consciente: la fuente de verdad sigue siendo `content_blocks`, no duplicar estado.
- **Query**:
  ```sql
  SELECT page_id,
         COUNT(*) FILTER (WHERE block_type = 'unknown') AS unknown_count,
         COUNT(*) AS total
  FROM content_blocks
  WHERE project_id = :project_id
  GROUP BY page_id
  HAVING COUNT(*) FILTER (WHERE block_type = 'unknown') >= 3
     AND COUNT(*) FILTER (WHERE block_type = 'unknown') * 1.0 / COUNT(*) >= 0.5
  ```
- **Endpoint `/summary` extendido**: campo nuevo `pages_with_many_unknowns: int` (default 0).
- **UI — header del proyecto**:
  - Si `pages_with_many_unknowns > 0` → badge ámbar visible junto a otros KPIs: "⚠ 3 páginas con muchos UNKNOWN".
  - Click → navega a `/projects/{id}/checklist?filter=generated_by:bricks-transpiler` (filtrado por generador del residual). Las residuales individuales ya existen — el badge solo agrega contexto visual.
- **No afecta el pipeline**: la fase `extract_content` sigue COMPLETED. No nuevo status, no nuevo bloqueante.

**Consecuencias**:

- ✅ Detecta el caso "página visualmente rota" temprano (en `extract_content`, fase 2 de 15) sin bloquear.
- ✅ Complementa visual_diff (fase 11) y residuales individuales — capas de detección redundantes pero baratas.
- ✅ Sin migración Alembic: cálculo on-the-fly con query agregada barata. Sin estado duplicado.
- ✅ Click en el badge lleva al checklist filtrado — el operador entra con contexto directo.
- ⚠️ El threshold (3 absolutos + 50% ratio) es arbitrario. Podría no capturar páginas problemáticas con UNKNOWN concentrados visualmente (todos en el hero) pero diluidos en ratio (1 UNKNOWN de 10 que es el hero gigante). Mitigación: visual_diff captura esos casos en fase 11.
- ⚠️ Si el operador tiene 30 proyectos en la fleet view, el badge ámbar puede ser visualmente ruidoso para los que tienen "muchos UNKNOWN". Aceptable — es señal real, no false positive.
- ⚠️ La query agregada se ejecuta cada vez que el dashboard fetcha `/summary` (cada 2s via polling o SSE). Coste por proyecto: ~5-10ms. Para 30 proyectos en fleet view = ~150-300ms agregados. Aceptable; si surge problema, cachear 30s.

**Implementación**: programada para v0.20.0+. Estimación ~2 días.

Tareas listadas en TaskList con prefijo `[ADR-052]`:
- Extender `GET /api/v1/projects/{id}/summary` con `pages_with_many_unknowns` (query agregada SQL).
- UI: badge ámbar en `<ProjectHeader>` con count + link al checklist filtrado.
- Tests: query con varios escenarios (0 UNKNOWN, 1 UNKNOWN de 20, 3 UNKNOWN de 5, 3 UNKNOWN de 100, página sin blocks).

`docs/flujo-migracion.md` se actualizará con nota en sección 5.1 explicando el comportamiento.

---

## ADR-053 — Thresholds QA: Lighthouse a11y/best-practices/SEO + broken links proporcional

**Fecha**: 2026-05-19 (sprint de revisión de decisiones, post-v0.19.0)
**Estado**: 🟡 Aceptada — implementación programada para v0.20.0+

**Contexto**: El agente `qa_runner` aplica thresholds para generar `ResidualTask` automáticas tras los chequeos. Hoy:

| Check | Threshold | Genera residual |
|---|---|---|
| Lighthouse Perf desktop/mobile | `< 50` | POST_GO_LIVE |
| Lighthouse a11y/best-practices/SEO | sin threshold | NO (solo persiste score) |
| Broken links | `> 5` absoluto | BLOCKING_GO_LIVE |

Dos gaps reales:

1. **a11y/best-practices/SEO sin threshold**: scores bajos no generan nada. a11y < 70 indica problemas serios para usuarios con discapacidades (potencial demanda legal en algunos países: WCAG 2.1 AA en UE para sitios públicos). best-practices < 75 implica warnings de seguridad (mixed content, console errors). SEO < 80 sugiere títulos/descriptions faltantes, robots.txt errors. El operador no recibe alerta.
2. **Broken links absoluto desproporcionado**: una web de 5 páginas con 6 broken links es desastrosa (>1 broken/página). Una de 200 páginas con 6 broken links es ~3% del total — aceptable. Mismo threshold, contextos completamente diferentes.

Se evaluaron 4 opciones (mantener, añadir thresholds + proporcional, todo configurable, otras combinaciones).

**Decisión**: **Opción 4 — añadir thresholds a a11y/best-practices/SEO + cambiar broken links a fórmula proporcional**.

### Cambios en G2 — Lighthouse

Constantes nuevas (env-overridable para flexibilidad):

```python
LIGHTHOUSE_PERF_MIN_CRITICAL = 50           # sin cambios
LIGHTHOUSE_A11Y_MIN_CRITICAL = 70            # nuevo
LIGHTHOUSE_BEST_PRACTICES_MIN_CRITICAL = 75  # nuevo
LIGHTHOUSE_SEO_MIN_CRITICAL = 80             # nuevo
```

Razones de los umbrales (alineados con la convención de Lighthouse: "good" ≥90, "needs improvement" 50-89, "poor" <50):

- **a11y < 70**: bajo el "needs improvement" claro. WCAG 2.1 AA típicamente exige ≥90 para sitios públicos. < 70 = problemas estructurales graves (sin alt en imágenes, contraste insuficiente, navegación por teclado rota).
- **best-practices < 75**: warnings de seguridad activos (https mixed content, vulnerabilidades JS conocidas, console errors). Bajo este umbral suele indicar plugins/scripts del cliente con problemas.
- **SEO < 80**: títulos/descriptions duplicados o faltantes, robots.txt mal, structured data ausente. Bajo este umbral compromete posicionamiento.

Cada uno → `ResidualTask` POST_GO_LIVE (no bloqueante) con title `Mejorar X (score N/100)` + description con causas comunes + link a documentación Lighthouse.

### Cambios en G3 — Broken links proporcional

Fórmula nueva (env-overridable):

```python
BROKEN_LINKS_MIN_ABSOLUTE = 2      # umbral absoluto mínimo
BROKEN_LINKS_RATIO_THRESHOLD = 0.03  # 3% del total checkeado

threshold = max(
    BROKEN_LINKS_MIN_ABSOLUTE,
    int(total_links_checked * BROKEN_LINKS_RATIO_THRESHOLD)
)
if broken_links > threshold:
    # ResidualTask BLOCKING_GO_LIVE (sigue siendo bloqueante como hoy)
```

Tabla efectiva resultante:

| total_links_checked | threshold efectivo | Vs. actual |
|---|---|---|
| 10 | 2 (mínimo absoluto) | más estricto |
| 50 | 2 | más estricto |
| 100 | 3 (3%) | más estricto |
| 200 | 6 (3%) | comparable |
| 500 | 15 (3%) | menos estricto |
| 1000 | 30 (3%) | menos estricto |

Para webs pequeñas, el mínimo absoluto 2 evita que sitios mini parezcan limpios con 4-5 broken. Para webs grandes, el 3% evita que sitios decentes (250 páginas con 8 broken) salten alarma por threshold demasiado bajo.

**Consecuencias**:

- ✅ Cobertura completa de los 5 scores Lighthouse + métrica de links proporcional al tamaño.
- ✅ Operador recibe alertas accionables sobre accesibilidad, seguridad y SEO técnico — áreas hoy invisibles que pueden tener implicaciones legales/SEO reales.
- ✅ Broken links proporcional reduce falsos positivos en webs grandes y aumenta sensibilidad en webs pequeñas.
- ✅ Constantes env-overridable (`LIGHTHOUSE_A11Y_MIN_CRITICAL`, etc.) sin requerir nuevos campos por proyecto — el override por proyecto puede venir en futuro ADR si surge necesidad.
- ⚠️ Más residuales por migración: ~1-3 nuevas en promedio (cliente típico tiene a11y o SEO con margen de mejora). Aceptable: van todas a POST_GO_LIVE (no bloqueantes). El operador puede cerrarlas como "no aplica" tras revisión.
- ⚠️ Los thresholds elegidos son opinionados. Si Webcafeína decide ser más laxo (a11y < 50 en lugar de < 70), ajusta env vars. Documentar valores recomendados en `docs/despliegue.md`.
- ⚠️ La regla "broken_links > threshold → BLOCKING" se mantiene (sin cambio en severidad). Solo cambia cuándo se dispara. Para webs muy pequeñas, esto endurece (2 broken pueden bloquear el go-live ahora vs 5 antes); decisión consciente — un sitio de 5 páginas con 2 broken está mal.

**Implementación**: programada para v0.20.0+. Estimación ~2 días.

Tareas listadas en TaskList con prefijo `[ADR-053]`:
- `qa_runner._create_residual_tasks` extendido: 3 nuevas constantes Lighthouse + fórmula proporcional broken_links + 4 ResidualTask generators nuevos (a11y, bp, seo, broken proporcional).
- Plantillas de description con causas comunes + links Lighthouse docs.
- Tests: 8 nuevos cubriendo cada threshold + casos límite (broken=2 con total=10, broken=15 con total=1000, a11y=70 exact, a11y=69 dispara).
- Actualizar `.env.example` con los 4 nuevos umbrales documentados.

`docs/flujo-migracion.md` se actualizará con la tabla nueva en sección 9.1 (qa - residual tasks generadas).

---

## ADR-054 — H2+H4 sin cambios + nuevo endpoint `DELETE /projects/{id}` separado

**Fecha**: 2026-05-19 (sprint de revisión de decisiones, post-v0.19.0)
**Estado**: 🟡 Aceptada — implementación programada para v0.20.0+

**Contexto**: El `RollbackAgent` MVP (v0.19.0) tiene dos comportamientos asumidos:

- **H2**: borra páginas WP con `force=true` (salta papelera, irrecuperable desde wp-admin).
- **H4**: tras rollback, las tablas BD del proyecto se conservan intactas (scraped_pages, content_blocks, bricks_pages.bricks_json, assets, visual_diffs, qa_reports, residual_tasks). Solo se resetea `bricks_pages.wp_post_id = NULL`.

Razones originales: H2 — la papelera es para clientes en wp-admin, no para nosotros; si hicimos rollback fue intencional. H4 — el rollback es "deshacer lo que llegó al destino", no "borrar el proyecto"; los datos pre-deploy son útiles para diagnóstico y re-deploy.

Problemas potenciales identificados:

- **H2**: si el operador rollback por error, no hay recuperación desde wp-admin. Algunos workflows usan papelera como moderación.
- **H4**: tras varios rollback+re-arrancar iterativos, las tablas crecen (30 scraped_pages viejas + 30 nuevas). Para proyectos cancelados ("el cliente decidió no continuar"), `scraped_pages.html_raw` contiene material del cliente que queremos liberar.

Se evaluaron 5 opciones combinadas.

**Decisión**: **Opción 5 — mantener H2 + H4 sin cambios + añadir endpoint `DELETE /api/v1/projects/{id}` separado** para el caso "limpieza profunda / cancelación del proyecto".

Razón clave: **rollback y delete son conceptualmente distintos** y merecen endpoints separados:

- **Rollback**: "deshago el deploy para iterar". 95% de los casos. Mantiene el proyecto vivo en BD.
- **Delete**: "el proyecto se canceló o terminó, libero recursos". Caso mucho menos frecuente pero claro. Borra todo.

Mezclar ambos en un mismo endpoint con flag `--purge` (opción 4 evaluada) confunde — el operador puede activar el flag por error pensando que es solo "rollback más limpio" y perder datos.

### Contrato del endpoint nuevo

```
DELETE /api/v1/projects/{id}
Auth: admin-only (no operator — esto es destructivo definitivo)
Body: {"confirm": "DELETE PROJECT 7"}  # texto exacto incluyendo el ID
```

Validación:

- Si `confirm != f"DELETE PROJECT {id}"` → 409 con mensaje claro "envía body `{\"confirm\": \"DELETE PROJECT {id}\"}` para confirmar".
- Solo permitido si `status ∈ {completed, cancelled, qa_failed, rolled_back, blocked_human_input}`. En `running` → 409 (el worker tiene la sesión).
- Auditoría obligatoria antes del DELETE.

Lo que hace en orden:

1. **Audit log entry** con datos preservados:
   ```
   AuditLog(
     action=DELETE,
     entity_type="project",
     entity_id=project_id,
     actor=current_user_id,
     payload={
       "client_name": project.client_name,
       "source_url": project.source_url,
       "target_domain": project.target_domain,
       "status_at_delete": project.status.value,
       "created_at": project.created_at.isoformat(),
       "deleted_at": now.isoformat(),
     }
   )
   ```
   La fila del audit_log queda permanentemente para trazabilidad (es la tabla que NO se borra en CASCADE).

2. **Si status != ROLLED_BACK**: ejecuta rollback inline primero. Aplica snapshot restore si está disponible (ADR-042) o DELETE de páginas (MVP).

3. **Borra assets**:
   - R2: enumerar y borrar `projects/{id}/...` (usar paginated listing si > 1000 objetos).
   - Local `file://` fallback: `rm -rf /tmp/wcm-{visual-diff,checklist}/projects/{id}`.

4. **CASCADE delete en BD**: `DELETE FROM projects WHERE id={id}`. Las tablas relacionadas (scraped_pages, content_blocks, assets, bricks_pages, woo_products, woo_orders, visual_diffs, qa_reports, residual_tasks, project_phases, seo_redirects) tienen FK `ON DELETE CASCADE` por diseño — se vacían automáticamente.

5. Devuelve `204 No Content`.

### UX en dashboard

- En `<ProjectActions>` cuando `status` ∈ {completed, cancelled, qa_failed, rolled_back, blocked_human_input} → segundo botón "Eliminar proyecto" (rojo destructivo, icon `Trash2`, separado visualmente del botón "Rollback").
- Click → confirmación inline DOBLE:
  - **Paso 1**: "¿Eliminar este proyecto y todo su historial?" + "Sí, eliminar" / "Cancelar".
  - **Paso 2 (modal)**: input que requiere escribir literal `DELETE PROJECT {id}`. Botón "Eliminar definitivamente" deshabilitado hasta que el texto coincida exacto.
- Tras éxito → redirect a `/projects` con toast destructivo "Proyecto N eliminado".

### CLI

```bash
wcm projects delete ID --confirm "DELETE PROJECT N"
```

Sin flag interactivo (no `typer.confirm`). Esto es admin destructivo — mejor explicitud forzada que prompt fácil de aceptar por hábito. Si el `--confirm` no coincide exacto, exit 2 con mensaje claro.

**Consecuencias**:

- ✅ H2 y H4 confirmadas como correctas para el caso "iteración con rollback".
- ✅ Separación conceptual clara: rollback = deshacer, delete = liberar.
- ✅ Doble confirmación (admin-only + body `confirm` exacto con ID + UI modal con input) protege contra disparos accidentales — análogo a `git push --force` que requiere `--force-with-lease`.
- ✅ Audit log preservado garantiza trazabilidad incluso tras delete completo (la entrada del audit_log es la fuente de verdad post-delete).
- ✅ CASCADE delete ya está implementado en los modelos (FK `ON DELETE CASCADE`) — el endpoint usa la infraestructura existente.
- ⚠️ Operador con permisos admin puede borrar proyectos definitivamente. Si hubo error humano (borró el equivocado), no hay recuperación — la fila se ha ido. Mitigación: el body `confirm` con ID literal hace casi imposible el "borré el equivocado" (escribirías `DELETE PROJECT 7` y pensarías "espera, ¿quería borrar el 7 o el 17?").
- ⚠️ Borrado de R2 puede ser lento para proyectos grandes (muchos screenshots, assets optimizados). El endpoint puede tardar 5-30s. Mitigación: encolar la limpieza R2 como task Celery + devolver 202 si > N assets; respuesta inmediata 204 si < N. Documentado en OpenAPI.
- ⚠️ Si el rollback inline (paso 2) falla, el DELETE se aborta — el proyecto queda parcialmente en su estado original. Mitigación: el operador puede pulsar "Eliminar" de nuevo (idempotente desde audit_log). O hacer rollback manualmente primero y luego delete.

**Implementación**: programada para v0.20.0+. Estimación ~3-4 días.

Tareas listadas en TaskList con prefijo `[ADR-054]`:
- `DELETE /api/v1/projects/{id}` admin-only con validación de `confirm` literal (~50 LOC + 6 tests).
- Service `_delete_project_cascade` que ejecuta los 5 pasos (audit → rollback inline → R2 cleanup → CASCADE DB → 204) (~80 LOC + 4 tests).
- UI: botón "Eliminar proyecto" en `<ProjectActions>` + modal con input literal de confirmación (~120 LOC + 5 vitest).
- CLI `wcm projects delete ID --confirm "DELETE PROJECT N"` (~30 LOC + 4 tests).
- Documentar en `docs/playbook-operativo.md` sección "Cuándo usar Delete vs Rollback".

`docs/flujo-migracion.md` se actualizará con sección 10.10 nueva ("Delete proyecto — distinto al rollback") explicando los dos caminos.

---

## ADR-040 — Vendoring h2b.skill v3.2.0 como corpus dorado de shapes Bricks JSON

**Fecha**: 2026-05-22 · **Sprint**: v0.24.0 · **Estado**: aceptado

### Contexto

El transpilador `wcm_bricks_transpiler` genera JSON para `_bricks_page_content_2` postmeta + options `bricks_global_classes` / `bricks_global_settings`. Necesitamos saber los **shapes exactos** que Bricks Builder acepta sin descartar silenciosamente.

Tras release v0.23.0 descubrimos que un detalle del shape (color como `{"raw": "..."}` vs string pelado) cambia si el estilo se aplica o no — Bricks descarta lo que no parsea sin error visible. Esto motivó investigar fuentes de referencia.

Opciones evaluadas:

1. **Captura manual desde editor Bricks** (#168 plan original): el operador monta páginas con slider+tabs+accordion+nav-menu+repeater+gallery en un sitio Bricks, exporta JSON elemento por elemento. **Pro**: canónico oficial. **Contra**: requiere 30-45 min del operador por sprint + Bricks 2.x licencia activa.

2. **academy.bricksbuilder.io/developer/**: documenta controles PHP por elemento pero NO publica JSON literal. Útil como reference secundaria pero incompleto. No documenta `bricks_global_classes` ni `bricks_global_settings`.

3. **`wpgaurav/bricks-skills`** (ya vendorado en `docs/referencias/bricks-skills/` desde v0.23.0): documentación pedagógica del approach Core Framework personal. **Pro**: shapes `_typography`/`_padding`/`_background` confirmados verbatim. **Contra**: no cubre slider/tabs/accordion/repeater. Pattern Core Framework atá a un sistema de tokens de terceros.

4. **`iamfilipp/html2bricks` v3.2.0** (https://github.com/iamfilipp/html2bricks, MIT): skill Claude que documenta verbatim shapes JSON de **31 elementos Bricks** (target 2.1.4), `BRICKS-NATIVE-PROPERTIES.md` con 99.5%+ cobertura, pitfalls confirmados (`_widthMax` no `_maxWidth`, `_cssClasses` string no array, etc.).

### Decisión

**Vendoring snapshot de `iamfilipp/html2bricks` v3.2.0 en `docs/referencias/h2b-skill/`** como corpus dorado de shapes Bricks JSON. No submódulo (el repo cambia y no queremos seguir tracking automático). Conserva `LICENSE` MIT + atribución en `README.md` del directorio.

Como **complemento**, `docs/referencias/bricks-skills/` (wpgaurav) se mantiene para shapes pedagógicos de typography/padding/globalClasses ya consolidados desde v0.23.0.

### Convenciones

1. **Implementación de mapper**: primero consultar `h2b-skill/h2b/references/BRICKS-ELEMENTS.md`; si shape no encontrado o ambiguo, validar manualmente con `code2bricks.netlify.app` (HTML mínimo → JSON real).
2. **Divergencia entre h2b y academy.bricksbuilder.io**: gana academy. Registrar excepción en `docs/referencias/h2b-skill/README.md` sección "Divergencias / overrides locales".
3. **Target Bricks**: 2.1.4 (a fecha de vendoring). Si Webcafeína actualiza Bricks a 2.2/2.3+, revisar gaps y registrar.
4. **Pitfalls v3.2.0** (recordatorio):
   - `_widthMax` (NO `_maxWidth`)
   - `_heightMin` (NO `_minHeight`)
   - `_cssClasses` es **string con espacios** (no array)
   - `_cssCustom` NO renderiza en frontend
   - Estructura **plana** con relaciones por ID (children = lista de IDs)

### Consecuencias

- **Positivas**:
  - Cero esfuerzo del operador para tener shapes verbatim de 31 elementos.
  - Validación contra fixtures verbatim posible en `test_*.py` de mappers (snapshot tests).
  - `code2bricks.netlify.app` queda como oracle de validación manual cuando dude el implementer.
- **Negativas**:
  - Si Filipp actualiza h2b a v3.3 con cambios relevantes, hay que re-vendorear manualmente.
  - Si Bricks cambia shape entre 2.1.4 y 2.3+, descubrimos divergencias en runtime hasta que vendoreemos nuevo snapshot.

### Tarea de seguimiento

- Tras release v0.24.0, smoke test contra Bricks **2.3+** (versión actual destino del operador) — si shape divergente, registrar overrides en `README.md` del directorio.
- Si gaps graves → reactivar tarea original #168 (captura manual del editor) como fallback puntual.

---

## ADR-055 — Pivote arquitectónico v0.25.0: rediseño desde origen vs replicación fiel

**Fecha**: 2026-05-22 · **Sprint**: v0.25.0 · **Estado**: aceptado

### Contexto

Tras 3 sprints invertidos en replicar fielmente el origen:

- **v0.22.0** — heurística + Claude Vision + RAW_HTML fallback.
- **v0.23.0** — element_styles + globalClasses (patrón h2b.skill).
- **v0.23.1** — desactivar Claude (sin tier pagado).
- **v0.24.0** — fidelidad alta: asset_uploader R2→WP, NAV/FOOTER reales,
  composite styles, hero composition, state_driver (slideshow/tabs/
  accordion), multibuilder Webflow + Hostinger AI.

**La validación visual del operador sobre mariya.design tras v0.24.0 confirma**:

- 89% assets subidos OK, 91 globalClasses aplicadas, 17 fases canónicas.
- PERO: el destino sigue sin parecerse al origen lo suficiente como
  para que el operador valide el producto como "migración fiel".
- Razón fundamental: replicar layouts complejos (Wix Studio composition,
  position absolute, computed styles por nodo, IX2 Webflow) es
  intrínsecamente complejo y siempre habrá pérdidas.

### Decisión

**Cambio de filosofía técnica + comercial**:

1. La promesa al cliente pasa de **"migramos tu Wix a WP"** a
   **"modernizamos tu web aprovechando tu contenido y branding actuales"**.
2. Lo que se extrae del origen sigue siendo input crítico: contenido,
   paleta, fonts, navigation, fingerprint sectorial, assets.
3. Pero el OUTPUT YA NO replica el layout origen. Es un rediseño limpio,
   editable, con elementos Bricks nativos, construido a partir de un
   contrato canónico intermedio (`Brief JSON`).
4. **Dos pipelines paralelos** de generación, operador elige por proyecto:
   - **Templates**: catálogo curado de `brickstemplate.com` +
     `SectionPicker` (determinista, hash(business.name) % N candidatos
     filtrados por sector+tone) + `SlotMapper` (reemplazo de placeholders
     en JSON Bricks). Sin coste API.
   - **AI**: OpenAI gpt-4o (no Anthropic — sin créditos) con
     function calling estructurado `emit_bricks_page`. ~$3-15/proyecto.
5. **BriefGenerator** auto-detecta business_description, sector, tone,
   target_audience, USPs con OpenAI gpt-4o-mini (~$0.01/proyecto) si los
   campos no están seteados por el operador en el wizard.
6. Pipeline legacy (`transpile_bricks` v0.24.0) se mantiene activo
   condicionado a `design_method=NULL` (proyectos pre-v0.25.0).
7. **Figma diferido a v0.26.0** como capa de revisión visual del
   Brief detrás de feature flag (`WCM_FIGMA_PREVIEW=1`), NO traductor
   Figma→Bricks (UiChemy no expone API pública, rompería automatización).

### Consecuencias

- **Positivas**:
  - Complejidad técnica del output baja drásticamente (sin replicación
    fiel de Wix Studio).
  - El operador puede validar "calidad del diseño nuevo" (subjetivo
    ≥80%) en lugar de "fidelidad pixel-perfect" (siempre <70%).
  - Promesa comercial más realista y atractiva.
  - Operador decide por proyecto: templates (gratis, determinista) o
    AI (flexible, coste recurrente).
  - Código v0.22-v0.24 NO se borra — sigue como input del Brief.
- **Negativas**:
  - El cliente final puede esperar "réplica fiel" si no se gestionan
    bien las expectativas comerciales. Refinar copy del producto.
  - Curación manual de `sections-index.json` (vibe, fits_sectors,
    fits_tones, slot_map) consume tiempo del operador hasta tener un
    catálogo robusto.
  - AI generativo tiene variabilidad — para algunos proyectos el output
    puede no ser óptimo (mitigado por fallback a templates).
- **Riesgos**:
  - Si los templates resultan insuficientes en variedad, complementar
    con BricksPlus (lifetime ~$249) o construir 20 templates propios.
  - GPT-4o coste por página puede escalar si el operador procesa
    decenas de proyectos/mes con AI puro. Monitorizar y mover a
    gpt-4o-mini si presupuesto lo requiere.

### Tarea de seguimiento

- **v0.25.1**: B7 edición iterativa Dashboard (preview por página +
  regenerate sección/página + editar Brief). No entró en v0.25.0 por
  scope.
- **v0.26.0**: Figma preview + híbrido por sección.
- Smoke test E2E con 3 proyectos (Wix mariya, Webflow demo, Hostinger
  demo) post-release v0.25.0 para validar el approach.
- Si tras 5 proyectos reales el operador valida la calidad subjetiva
  ≥80%, refinar copy comercial del producto y empezar prospección
  con nueva promesa.

---

## ADR-056 — Sprint v0.26.0: Híbrido por sección + Image generation + Thumbnails preview (Figma OUT)

**Fecha**: 2026-05-22 (sesión vespertina, post v0.25.1)
**Estado**: Aceptada

### Contexto

v0.25.0 instaló el Brief JSON canónico y los pipelines Templates/AI
mutuamente exclusivos a nivel proyecto. v0.25.1 cerró la edición
iterativa básica desde el dashboard. Quedaban 3 limitaciones para
cerrar el MVP del pivote:

1. **Granularidad gruesa**: `design_method` único por proyecto obliga
   a elegir "todo templates o todo AI". Lo natural es mezclar
   (hero/cta = AI generativo + features/services = templates curados).
2. **Sin preview visual real**: la pantalla `/preview` solo muestra
   metadata. Figma se valoró como capa de preview pero la investigación
   técnica concluye que la REST API es read-only y el MCP de Figma no
   permite generación persistente (solo `create_new_file` vacío +
   `upload_assets` imágenes + `use_figma` JS ephemeral).
3. **Imágenes faltantes/feas del origen** lastran el rediseño. OpenAI
   publicó **gpt-image-2** en abril 2026 con reasoning + 16 reference
   images + multilingual text accurate → rellena slots brand-consistent
   por ~$0.05/imagen.

### Decisión

1. **Figma OUT**. Sustituido por **thumbnails Playwright sobre WP draft**.
   Las páginas quedan como `draft` tras `wp_deployer`; un sidecar
   Playwright sobre esos drafts da fidelidad 100% sin Figma.
2. **Hybrid por sección**: cada sección del Brief gana `design_method`.
   Heurística: hero/cta → ai, resto → templates. Operador puede
   sobreescribir por sección desde `/preview` o por proyecto via wizard.
3. **OpenAI sube a gpt-5.5** para redesign (abril 2026, $5/$30 per MTok).
   Cambio vía env var.
4. **gpt-image-2** rellena slots de imagen vacíos en el Brief. Quality
   medium default. Budget por proyecto en `Project.image_generation_budget_usd`
   (default $1.00).
5. **Wizard default = Híbrido**. El operador sigue pudiendo elegir
   Templates puro o AI puro si lo necesita.

### Implementación

- Migración Alembic 0021 (Project.image_generation_budget_usd +
  BricksPage.preview_thumbnail_url + preview_captured_at).
- `RedesignTemplatesAgent` ahora corre en `templates` Y en Hybrid
  (None). Skip secciones AI + emite placeholders `_pending_ai=True`
  con marker `_brief_section_index`.
- `RedesignAIAgent` añade path Hybrid sección a sección. Llama
  `OpenAIClient.generate_section_redesign` por cada sección AI y
  mergea con bricks_pages existente reemplazando placeholders.
- `RedesignImagesAgent` (NUEVO) genera imágenes con gpt-image-2 para
  slots vacíos, persiste Asset, actualiza Brief.asset_id + metadata.
  Budget tracking duro con ResidualTask si se supera.
- `PreviewThumbnailsAgent` (NUEVO) captura Playwright sobre WP draft
  tras `wp_deployer`. Sube a R2 o local. ResidualTask si falla.
- API: nuevos endpoints `POST /preview/regenerate-section` y
  `POST /preview/regenerate-image`.
- Dashboard `/preview` muestra thumbnails + sections con dropdown
  design_method + botones regenerar sección/imagen + budget tracking.

### Consecuencias

- **Pros**: granularidad fina, preview visual fiel, imágenes IA
  brand-consistent, wizard simplificado (Híbrido default cubre 80%
  de casos).
- **Contras**: coste agregado (gpt-5.5 ~2× gpt-4o + image gen
  $0.20-0.40 típico → $1-5/proyecto en Hybrid; hasta $15 en AI puro).
- **Riesgos**: gpt-5.5 puede cambiar shape tool_use (fallback gpt-4o
  si retries fallan); image runaway (mitigación: budget duro +
  warning UI 80%); Figma queda fuera del producto (revisable con
  plugin custom en futuro sprint).

### Tarea de seguimiento

- **v0.26.0 B9**: E2E manual con cliente real (Templates + AI +
  Hybrid + Image gen). Output `docs/e2e-v026.md`.
- **v0.26.1+**: thumbnails real-time post-regenerate-section.
- **v0.27.0**: modernizar imágenes existentes feas, no solo slots vacíos.

---

## Cómo añadir una nueva decisión

1. Incrementar `ADR-NNN`.
2. Añadir entrada con: Fecha, Estado, Contexto, Decisión, Consecuencias.
3. Si supersede una decisión previa, marcar la anterior como "🟥 Superseded by ADR-MMM".
4. Commit con `docs(adr): ADR-NNN <título>`.
