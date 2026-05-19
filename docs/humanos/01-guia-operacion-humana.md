# 01 — GUÍA DE OPERACIÓN HUMANA

> **Para quién**: Nacho (operador principal) y resto del equipo Webcafeína que vaya a lanzar y supervisar la construcción de Webcafeína Migrator con Claude Code Opus 4.7 en Antigravity.
>
> **Qué hace este documento**: te dice exactamente qué tienes que hacer tú como humano, en qué orden, antes/durante/después de cada fase. Todo lo que NO hace Claude Code automáticamente.

---

## 0. ANTES DE ABRIR ANTIGRAVITY

### 0.1 Cuentas y credenciales que necesitas tener listas

Marca cada una cuando esté lista. Las marcadas como **[FASE 0]** son obligatorias antes de empezar. Las demás puedes ir consiguiéndolas en paralelo.

| # | Servicio | Cuándo lo necesitas | Cómo conseguirlo | Coste aprox. |
|---|---|---|---|---|
| 1 | **GitHub** (cuenta organizacional `webcafeina`) | **[FASE 0]** | github.com → New Organization | Free plan suficiente |
| 2 | **Repositorio privado** `webcafeina-migrator` | **[FASE 0]** | Crear en GitHub, sin README ni .gitignore | — |
| 3 | **SSH key** del equipo local conectada a GitHub | **[FASE 0]** | `ssh-keygen -t ed25519`, añadir a GitHub Settings → SSH keys | — |
| 4 | **Acceso SSH root al WHM** | [FASE 12] | Ya confirmado | — |
| 5 | **Dominio para staging y producción del migrator** | [FASE 12] | Ej. `migrator-staging.webcafeina.com`, `migrator.webcafeina.com` | — |
| 6 | **Licencia Bricks Builder** | [FASE 2] | bricksbuilder.io, plan Lifetime o Annual | 249€ una vez / 99€ año |
| 7 | **Licencia WPML Multilingual Agency** | [FASE 6] | wpml.org | 199€/año |
| 8 | **Licencia Gravity Forms Pro/Elite** | [FASE 6] | gravityforms.com | 159-309€/año |
| 9 | **WordPress sandbox** instalado con Bricks + WPML + Gravity + Woo | [FASE 2] | Subdominio en tu WHM ej. `sandbox-migrator.webcafeina.com` | — |
| 10 | **Cloudflare account + R2 bucket** | [FASE 10] | dash.cloudflare.com → R2 → Create bucket `webcafeina-migrator-assets` | Free 10GB/mes, después barato |
| 11 | **Bright Data account** | [FASE 10] | brightdata.com, plan Pay-As-You-Go residencial | ~10-50€/mes según uso |
| 12 | **2captcha account + API key** | [FASE 10] | 2captcha.com, deposita 5€ inicial | ~3€/1000 captchas |
| 13 | **Resend account + dominio verificado** | [FASE 10] | resend.com, verificar `webcafeina.com` con DNS | Free 100 emails/día |
| 14 | **Sentry account + proyectos creados** | [FASE 11] | sentry.io, crear proyectos `migrator-api` y `migrator-dashboard` | Free 5k errores/mes |
| 15 | **Logtail/BetterStack account** | [FASE 11] | betterstack.com/logtail | Free 1GB/mes |
| 16 | **Google Cloud project + Places API key** | [FASE 9] | console.cloud.google.com, habilitar Places API, obtener key | 200$ crédito inicial gratis |
| 17 | **ClickUp Personal API Token** | [FASE 10] | ClickUp → Settings → Apps → API → Generate | Free |
| 18 | **Brevo o Lemlist** (para envío manual de outreach desde la herramienta) | [FASE 9] | brevo.com o lemlist.com | Variable |

### 0.2 Software local que necesitas instalado

| # | Software | Versión | Cómo lo verificas |
|---|---|---|---|
| 1 | Antigravity con Claude Code Opus 4.7 habilitado | Última | Abrir Antigravity y comprobar modelo disponible |
| 2 | Git | 2.40+ | `git --version` |
| 3 | GitHub CLI (opcional pero recomendado) | Última | `gh --version` |
| 4 | Node 20 LTS | 20.x | `node --version` |
| 5 | pnpm | 9.x | `pnpm --version` |
| 6 | Python 3.12 | 3.12.x | `python3.12 --version` |
| 7 | PostgreSQL 16 local (para desarrollo) | 16.x | `psql --version` |
| 8 | Redis local | 7.x | `redis-cli --version` |
| 9 | Editor de código (VS Code, Cursor, Zed) | — | — |

### 0.3 Variables sensibles — preparar un gestor

Antes de empezar, crea un sitio donde vas a guardar credenciales según las consigas. Opciones:

- **1Password / Bitwarden**: campo "Notes" con bloque dedicado al proyecto
- **Archivo cifrado local** `.credenciales.gpg` con GPG
- **Doppler** o **Infisical** (gestores cloud) — recomendado si vais a operar varios

NO guardes credenciales en el repo, ni en notas planas, ni en ClickUp.

### 0.4 Preparación de la sandbox WordPress

Esta es la parte que más se suele olvidar y la que más bloquea. Tienes que tener una instalación WordPress de pruebas funcionando ANTES de Fase 2 porque sin ella el transpilador de Bricks no puede testearse.

Pasos:

1. Crear subdominio `sandbox-migrator.webcafeina.com` en WHM
2. Instalar WordPress última estable (Softaculous o manual)
3. Subir y activar el tema **Bricks** con tu licencia
4. Crear página de prueba con variedad de elementos: heading, text, image, gallery, button, columns, form, section con background
5. **Exportar la página** vía Bricks → "Templates" → Export como JSON
6. Guardar ese JSON en sitio accesible. Lo necesitarás en Fase 2.

Repetir el ejercicio con WPML activado, WooCommerce activado, y Gravity Forms activado.

---

## 1. SECUENCIA DE TRABAJO CON CLAUDE CODE

### 1.1 Sesión inicial — Bootstrap

```
1. Abre Antigravity
2. Crea carpeta vacía local: ~/proyectos/webcafeina-migrator
3. Abre terminal dentro de esa carpeta
4. Lanza Claude Code en modo plan
5. Pega el contenido COMPLETO de CLAUDE_CODE_PROMPT.md
6. Espera el plan generado
7. NO apruebes el plan todavía
8. Revisa el plan con la checklist del doc 03
9. Pide ajustes si procede
10. Aprueba SOLO Fase 0
11. Deja que ejecute Fase 0
12. Tras Fase 0 → revisión humana → commit y push
13. Aprobar Fase 1, y así sucesivamente
```

### 1.2 Regla de oro: una fase, una sesión

NO dejes que Claude Code encadene fases sin tu revisión. Cada fase:

1. Plan de la fase
2. Aprobación tuya
3. Ejecución
4. Tests verdes obligatorios
5. Tú revisas el código generado
6. Tú haces commit (o lo hace el agente con tu aprobación)
7. Tú haces push
8. STATE.md actualizado
9. Cierras sesión
10. Abres sesión nueva para la siguiente fase

¿Por qué? Porque a partir de unos 200k tokens de contexto, la calidad de las decisiones del agente baja. Sesiones cortas y enfocadas mantienen la calidad alta.

### 1.3 Qué decir al iniciar cada sesión nueva (después de Fase 0)

```
Hola. Voy a continuar con la construcción de Webcafeína Migrator.

Por favor:
1. Lee CLAUDE.md
2. Lee STATE.md
3. Identifica la fase actual y la siguiente tarea pendiente
4. Genera un plan SOLO de esa fase, no de las siguientes
5. Antes de aprobarlo dime qué prerequisitos humanos necesitas y si hay algún bloqueo
```

### 1.4 Qué hacer cuando termine cada fase

1. Lee `STATE.md` y verifica que refleja lo hecho
2. Mira el diff: `git diff main..feature/fase-X`
3. Ejecuta los tests localmente: `pnpm test` y `pytest`
4. Levanta lo construido en modo dev y comprueba manualmente
5. Si todo OK: `git commit` + `git push`
6. Crea PR de la rama de la fase a `develop` y mergeala
7. Notas tuyas en `docs/notas-revision-fase-X.md` si hay cosas que comentar

---

## 2. QUÉ HACE CLAUDE CODE Y QUÉ HACES TÚ

| Tarea | Claude Code | Tú |
|---|---|---|
| Crear estructura de carpetas | ✓ | — |
| Generar `.claude/agents/*.md` | ✓ | Revisar |
| Generar `.claude/skills/*/SKILL.md` | ✓ | Revisar |
| Escribir código de packages, apps | ✓ | Revisar diff |
| Escribir tests | ✓ | Verificar cobertura |
| Ejecutar tests | ✓ | Verificar resultado |
| Crear PR en GitHub | ✓ con permiso | Aprobar merge |
| Comprar licencias (Bricks, WPML, Gravity) | — | ✓ |
| Crear cuentas externas (Bright Data, Resend, etc.) | — | ✓ |
| Obtener API keys y meterlas en `.env` | — | ✓ |
| Instalar WordPress sandbox | — | ✓ |
| Exportar JSON real de Bricks para el transpilador | — | ✓ |
| Aprobar decisiones irreversibles | — | ✓ |
| Validar visualmente el resultado de una migración real | — | ✓ |
| Configurar DNS de subdominios | — | ✓ |
| Configurar Cloudflare R2 bucket policies | — | ✓ |
| Lanzar primera migración real piloto | — | ✓ |

---

## 3. CALENDARIO REALISTA

Con dedicación parcial (1-2h diarias) del equipo:

| Semana | Fases | Hito |
|---|---|---|
| 1 | 0, 1 | Bootstrap + DB + modelos listos |
| 2 | 2 | Transpilador Bricks funcional con cobertura básica |
| 3 | 3 | Scraper extrayendo Wix/Hostinger/Webflow |
| 4 | 4, 5 | WP client + API backend |
| 5 | 6, 7 | Worker pipeline E2E dry-run + CLI |
| 6 | 8 | Dashboard básico operable |
| 7 | 9 | Módulo prospección con cumplimiento |
| 8 | 10, 11 | Integraciones + observabilidad |
| 9 | 12, 13 | Despliegue WHM + tests E2E |
| 10 | 14, 15 | Docs + hardening |
| 11 | — | Piloto con web real interna |
| 12 | — | Primera migración cliente real |

Con dedicación full-time de Álvaro o Samuel, divide por 2.

---

## 4. PUNTOS DE NO RETORNO

Hay decisiones que una vez tomadas son caras de cambiar. Antes de cada una, para y confirma.

| Decisión | Cuándo | Por qué es difícil cambiar |
|---|---|---|
| Schema de DB inicial | Fase 1 | Migraciones posteriores complejas si hay datos reales |
| Schema del Bricks JSON output | Fase 2 | Si cambia, todas las webs migradas previas quedan inconsistentes |
| Convenciones de API REST | Fase 5 | Si cambia, hay que cambiar dashboard y CLI |
| Estructura de directorios assets en R2 | Fase 10 | Difícil reorganizar 1000s de imágenes ya subidas |
| Formato de checklist humano | Fase 10 | Si cambia, formación del equipo a rehacer |

---

## 5. COMUNICACIÓN INTERNA DURANTE LA CONSTRUCCIÓN

Sugerencia de canal en Slack o ClickUp:

- Canal `#migrator-build` para avances diarios
- Tarea principal en ClickUp lista Sprint actual: "Construcción Webcafeína Migrator — Fase X"
- Subtareas por fase asignadas a quien revise (probablemente Álvaro principalmente, tú revisas decisiones de producto)
- Cada commit notificado en el canal vía GitHub Slack integration

---

## 6. CHECKLIST FINAL ANTES DE LANZAR PRIMERA MIGRACIÓN REAL

Cuando el MVP esté "terminado" según los criterios del prompt, antes de aceptar un cliente real:

- [ ] Migración interna de una web Webcafeína (puede ser landing antigua) ejecutada end-to-end
- [ ] Resultado revisado por Adrián desde óptica marketing/conversión
- [ ] Resultado revisado por Álvaro desde óptica técnica
- [ ] Checklist residual revisado y ejecutado por humano: ¿es realmente claro y ejecutable?
- [ ] Tiempo total medido y comparado contra los criterios de éxito (90 min auto + 4h humano)
- [ ] Despliegue en producción del cliente probado con dominio temporal antes del switch DNS
- [ ] Plan de rollback documentado: si algo sale mal post-migración, cómo volver atrás
- [ ] Contrato cliente con cláusula de "tareas residuales asumidas por cliente o presupuesto adicional"
- [ ] Precio definitivo cerrado y defendido
