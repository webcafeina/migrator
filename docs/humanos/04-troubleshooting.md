# 04 — TROUBLESHOOTING DURANTE LA CONSTRUCCIÓN

> Problemas comunes que vas a encontrar trabajando con Claude Code Opus 4.7 en Antigravity para este proyecto y cómo resolverlos rápido.

---

## A. PROBLEMAS CON CLAUDE CODE

### A.1 "El agente se ha desviado del prompt original"

**Síntoma**: empieza a hacer cosas no pedidas, sugiere arquitecturas distintas, propone librerías no listadas.

**Causa**: contexto saturado, han pasado muchas interacciones, perdió el hilo.

**Solución**:
1. Cierra la sesión
2. Abre sesión nueva
3. Primer mensaje: "Lee CLAUDE.md y STATE.md. Estamos en Fase X tarea Y. Continúa desde ahí siguiendo estrictamente el plan original. No tomes decisiones nuevas."

### A.2 "Está editando archivos que no debería tocar"

**Síntoma**: modifica archivos de fases anteriores ya cerradas, rompe tests existentes.

**Solución**:
1. Detén la sesión inmediatamente
2. `git diff` para ver el daño
3. `git restore <archivo>` para revertir los cambios indeseados
4. Continúa con un mensaje aclaratorio: "Solo modifica archivos relacionados con la tarea actual. No toques fases anteriores."

### A.3 "Ha inventado una versión de librería"

**Síntoma**: fija `playwright==2.99.0` cuando esa versión no existe.

**Solución**:
1. Detén
2. Mensaje: "Has fijado playwright==2.99.0 que no existe. Consulta pypi.org y usa la última estable. Verifica TODAS las versiones que fijaste en este commit."

### A.4 "Bucle infinito de iteraciones sobre el mismo archivo"

**Síntoma**: edita, ejecuta, falla, vuelve a editar el mismo archivo sin progreso.

**Solución**:
1. Después de 3-4 iteraciones, intervén
2. Pídele un diagnóstico: "Para. Explícame en qué punto exacto está fallando, qué hipótesis tienes, y qué información necesitas que yo aporte."
3. Frecuentemente el problema es ambiental (servicio no levantado, credenciales mal) y necesita input humano

### A.5 "Tests verdes pero el código no funciona en realidad"

**Síntoma**: dice que todo pasa, pero al ejecutarlo manualmente algo está roto.

**Causa**: tests mal escritos (mockean lo que deberían probar) o cobertura insuficiente.

**Solución**:
1. Pídele que ejecute manualmente el flujo y describa qué ve
2. Pídele que añada un test de integración real
3. Tú mismo ejecuta el flujo y describe el fallo concreto

### A.6 "Se queja de límite de tokens"

**Síntoma**: respuestas truncadas, "context window exceeded".

**Solución**:
1. Cierra sesión
2. Antes de cerrar, pídele actualizar `STATE.md` con todo el detalle de dónde se quedó
3. Sesión nueva, retoma desde `STATE.md`
4. Para tareas grandes, divide en subtareas más pequeñas

### A.7 "Modo plan sigue añadiendo cosas indefinidamente"

**Síntoma**: el plan crece sin terminar.

**Solución**:
1. Detén
2. Mensaje: "Limita el plan a la Fase X solamente. No incluyas Fase X+1 ni posteriores. Cierra el plan."

---

## B. PROBLEMAS DE ENTORNO

### B.1 PostgreSQL local no conecta

**Síntoma**: `psql: error: connection refused`

**Solución por OS**:

| OS | Comando |
|---|---|
| macOS (Homebrew) | `brew services restart postgresql@16` |
| Ubuntu/Debian | `sudo systemctl restart postgresql` |
| AlmaLinux/CentOS | `sudo systemctl restart postgresql-16` |

Si sigue fallando, revisa `pg_hba.conf` y permite `local all all md5`.

### B.2 pgvector no instalable

**Solución**:
```bash
# Ubuntu/Debian
sudo apt install postgresql-16-pgvector

# macOS
brew install pgvector

# AlmaLinux
sudo dnf install pgvector_16
```

Luego: `psql -d webcafeina_migrator_dev -c "CREATE EXTENSION vector;"`

### B.3 Redis no levanta

**Solución**:
```bash
# macOS
brew services start redis

# Linux
sudo systemctl start redis
```

### B.4 Node version mismatch

**Síntoma**: `engine "node" is incompatible`

**Solución**: instala fnm o nvm y fija Node 20.

```bash
fnm install 20
fnm use 20
```

### B.5 Playwright browsers no descargan

**Solución**:
```bash
pnpm exec playwright install chromium --with-deps
```

En Linux servidor puede faltar deps del sistema:
```bash
sudo apt install -y libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2
```

---

## C. PROBLEMAS CON LA SANDBOX WORDPRESS

### C.1 Bricks no acepta el JSON generado

**Síntomas posibles**:
- "Import failed: invalid format"
- Importa pero la página está vacía
- Importa pero los elementos están descolocados

**Diagnóstico**:
1. Exporta una página REAL de Bricks
2. Compara estructuralmente con tu JSON generado
3. Busca diferencias en: nombres de elementos, estructura de `children`, formato de `settings`, IDs

**Solución**:
- Si versión de Bricks cambió: regenerar fixtures
- Si schema mal inferido: ajustar transformador del bloque afectado
- Si IDs duplicados: revisar generador de IDs

### C.2 WP REST API devuelve 401

**Causas y soluciones**:
- Application Password mal pegado: revisa que no haya espacios extra
- Plugin de seguridad bloqueando REST: desactiva temporalmente Wordfence/iThemes
- HTTPS roto: verifica certificado válido

### C.3 WPML no aparece tras instalar

**Causa**: licencia no activada o plugins satellite no instalados.

**Solución**:
1. Activa licencia en WPML → Settings
2. Instala "WPML String Translation", "WPML Translation Management", "WPML Media"
3. Si Woo: instala "WooCommerce Multilingual"

### C.4 Bricks no carga sus estilos en frontend

**Causa**: caché de WordPress o caché de Bricks no regenerado.

**Solución**:
- Bricks → Settings → Performance → Regenerate CSS files
- Borrar caché de plugin de caché si lo hay
- Comprobar permisos de `/wp-content/uploads/bricks/`

---

## D. PROBLEMAS DE SCRAPING

### D.1 Wix devuelve 403 sistemáticamente

**Causa**: detección anti-bot por IP o User-Agent.

**Solución por orden**:
1. Activa `playwright-stealth`
2. Rota User-Agent con `fake-useragent`
3. Aumenta `wait_for: networkidle` y timeouts
4. Activa proxy residencial Bright Data
5. Reduce velocidad: max 1 request cada 5-8s

### D.2 Webflow muestra contenido vacío

**Causa**: SPA hidratación tardía.

**Solución**: espera `networkidle` y un selector específico como `body.w-mod-js`:
```python
await page.wait_for_load_state("networkidle")
await page.wait_for_selector("body.w-mod-js", timeout=10000)
```

### D.3 Hostinger AI Builder muy lento

**Causa**: páginas pesadas con assets grandes.

**Solución**:
- Aumenta timeout Playwright a 60s
- Bloquea descargas de video durante el scraping inicial: `await context.route("**/*.{mp4,webm}", lambda r: r.abort())`
- Procesa video aparte si el cliente lo necesita

### D.4 Imágenes no se descargan

**Causa**: URLs relativas, lazy-loading, srcset.

**Solución en `asset-optimizer`**:
- Detecta `data-src`, `data-lazy-src`, `srcset` además de `src`
- Resuelve URLs relativas contra el base URL de la página
- Para CDNs como `static.parastorage.com`, descarga la mayor resolución disponible

### D.5 Captcha aparece a media sesión

**Solución**: el agente debe detectar captcha (selector específico) y delegar a la skill `captcha-handling`. Si falla, anota la URL como tarea residual.

---

## E. PROBLEMAS DE DESPLIEGUE EN WHM

### E.1 systemd dice "service not found"

**Causa**: unit file no copiado a `/etc/systemd/system/` o no recargó daemon.

**Solución**:
```bash
sudo cp infra/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable webcafeina-api
sudo systemctl start webcafeina-api
```

### E.2 Nginx no proxy al backend

**Síntoma**: 502 Bad Gateway.

**Diagnóstico**:
1. `curl http://localhost:8000/health` directamente al backend — si falla, el problema es el backend
2. Si responde: el problema es nginx
3. Revisa `proxy_pass` en config

### E.3 cPanel sobrescribe nginx config

**Causa**: cPanel regenera configs Nginx en algunos casos.

**Solución**: usar la sección "Include Editor" de WHM para añadir tu config sin que sea sobrescrita, o configurar las apps en puerto distinto y reverse-proxy desde el frontend principal.

### E.4 Python 3.12 no disponible en el WHM

**Causa**: CloudLinux por defecto trae versiones más antiguas.

**Solución**: usa `cloudlinux-pyver` para activar Python 3.12 en la cuenta, o compila desde fuentes en `/opt/python3.12`.

### E.5 Permisos de archivos rotos

**Síntoma**: la app no puede escribir logs ni leer configs.

**Solución**:
```bash
sudo chown -R webcafeina:webcafeina /opt/webcafeina-migrator
sudo chmod -R 755 /opt/webcafeina-migrator
sudo chmod 600 /opt/webcafeina-migrator/.env
```

---

## F. PROBLEMAS DE OBSERVABILIDAD

### F.1 Sentry no recibe errores

**Checks**:
- DSN correcto en `.env`
- `sentry_sdk.init()` llamado al arranque
- Test manual: `raise Exception("test")` en un endpoint y mira Sentry

### F.2 Logtail no recibe logs

**Checks**:
- Token correcto
- `structlog` configurado con `sink` Logtail
- Verifica conexión: `curl -X POST https://in.logtail.com/ -H "Authorization: Bearer $TOKEN" -d '{"message":"test"}'`

### F.3 No llegan emails de error

**Checks**:
- Resend API key correcta
- Dominio verificado en Resend
- Email destino correcto en config
- Severidad del error supera el umbral configurado

---

## G. PROBLEMAS DE INTEGRACIÓN CLICKUP

### G.1 Tareas no se crean

**Checks**:
- Token API válido
- IDs correctos: Team `20483773`, lista Microtareas `900102088242`
- Permisos del token para esa lista

### G.2 Sincronización bidireccional no funciona

**Causa**: webhook de ClickUp no configurado.

**Solución**: en ClickUp → Settings → Integrations → Webhooks, añade endpoint del migrator `https://migrator.webcafeina.com/api/webhooks/clickup`.

---

## H. CUANDO TODO FALLA — RESET CONTROLADO

Si algo está muy roto y no sabes cómo arreglarlo:

1. **Identifica la última fase verde**: el último commit donde tests pasaban y todo funcionaba
2. **Crea rama de rescate**: `git checkout -b rescate-fase-X <hash-último-verde>`
3. **Re-evalúa qué quieres conservar de lo posterior**: a veces es mejor reimplementar 2 días que arrastrar problemas
4. **Aborta merge problemático**: `git merge --abort` si estás a mitad
5. **Si la BD está corrupta**: drop + recreate + alembic upgrade head + reseed

NO hagas `git reset --hard` sin backup. Crea siempre rama antes.

---

## I. PROTOCOLO DE ESCALADO

Cuándo parar y consultar a una persona externa (foros, Discord de Bricks, Anthropic Discord):

| Situación | A quién consultar |
|---|---|
| Bricks JSON schema confuso | Discord oficial de Bricks Builder |
| WPML API problema | Soporte WPML (de pago, vale la pena) |
| Claude Code se comporta raro | Discord Anthropic, canal #claude-code |
| Playwright + Wix anti-bot | Stack Overflow, GitHub Issues de playwright-stealth |
| WHM/cPanel + systemd | Foros cPanel, Stack Overflow ServerFault |
| RGPD y prospección | Tu asesor legal, NO foros |

---

## J. MÉTRICAS DE SALUD QUE DEBES VIGILAR

Durante la construcción y operación, monitoriza:

| Métrica | Valor saludable | Cuándo preocuparse |
|---|---|---|
| Cobertura de tests packages | >70% | <60% |
| Cobertura de tests apps | >50% | <40% |
| Tiempo de CI | <10 min | >20 min |
| Errores Sentry por día (prod) | <10 | >50 |
| Tiempo medio de migración | <90 min | >180 min |
| Score visual-diff medio | >0.85 | <0.75 |
| Tasa de éxito de fingerprinting | >85% | <70% |
| Coste mensual de servicios externos | <100€ | >200€ |
