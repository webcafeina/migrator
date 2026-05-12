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
**Estado**: ✅ Aceptada (provisional)

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

## Cómo añadir una nueva decisión

1. Incrementar `ADR-NNN`.
2. Añadir entrada con: Fecha, Estado, Contexto, Decisión, Consecuencias.
3. Si supersede una decisión previa, marcar la anterior como "🟥 Superseded by ADR-MMM".
4. Commit con `docs(adr): ADR-NNN <título>`.
