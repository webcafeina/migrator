# packages/wp-client

Cliente unificado para el WordPress destino. Dos canales:

- **`WpRestClient`** (skill `wp-rest-bulk`) — REST API + Application Password basic auth. Para CRUD puntual e inserts <= 100 items.
- **`WpCliSshClient`** (skill `wpcli-ssh`) — paramiko + WP-CLI vía SSH. Para bulks >100 items, búsqueda-reemplazo en BD, importación de Bricks JSON grande, instalación de plugins/temas.

## Estado

Materializado en **Fase 4**. Validado contra sandbox real **Local by Flywheel** (WordPress 6.9.4) con 8 tests integración pasando contra el sandbox + 21 tests unit con mocks. Total 29 tests del paquete.

## API resumida

```python
from wcm_wp_client import (
    WpClientConfig, WpRestClient, WpCliSshClient,
    WpAuthError, WpRateLimitError, WpNotFoundError,
    WpCliExecutionError, WpBulkPartialError,
)

cfg = WpClientConfig.from_env()  # lee WP_DEFAULT_* del entorno

async with WpRestClient(cfg) as rest:
    page = await rest.upsert_page_by_slug({
        "slug": "contacto",
        "title": "Contacto",
        "status": "publish",
        "content": "<p>...</p>",
    })
    await rest.upload_media(Path("hero.webp"), alt_text="Hero")
    await rest.bricks_import_page(page["id"], bricks_json)

async with WpCliSshClient(cfg) as cli:
    version = await cli.core_version()
    await cli.plugin_install("redirection", activate=True)
    # Bricks pages grandes mejor por CLI (post meta directo):
    await cli.bricks_import_content(page["id"], bricks_json)
    result = await cli.search_replace("https://origen/", "https://destino/", dry_run=False)
```

## Setup del sandbox Local by Flywheel (dev)

Local tiene particularidades que el cliente gestiona transparentemente. Si vas a desarrollar contra Local:

1. **Activar SSH a localhost**:
   - System Settings → General → Sharing → Remote Login → ON
   - `cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys`
2. **Descargar `wp-cli.phar`** (Local no lo trae preinstalado):
   ```
   curl -sSL -o "/Users/<tu>/Local Sites/<site>/app/wp-cli.phar" \
        https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
   ```
3. **Localizar el PHP binary y MySQL socket de Local** (paths volátiles):
   ```bash
   find "/Users/<tu>/Library/Application Support/Local" -name php -path '*php-8*bin*'
   find "/Users/<tu>/Library/Application Support/Local/run" -name 'mysqld.sock'
   ```
4. **Generar Application Password** en wp-admin → Users → tu user → Application Passwords.
5. **Rellenar `.env`** con las paths absolutos en `WP_LOCAL_PHP_BIN` y `WP_LOCAL_MYSQL_SOCKET`.

El socket de MySQL tiene un ID volátil (`run/<ID>/mysql/mysqld.sock`); si Local lo cambia, actualiza el `.env`. Una mejora futura (WCM-010) será autodescubrir el socket.

## Tests

```bash
# Unit (sin red, con mocks):
pytest packages/wp-client/tests/unit -q

# Integración contra sandbox real (requiere .env cargado):
set -a; source .env; set +a
pytest packages/wp-client/tests/integration -m integration -v
```

Los tests integración hacen REST GET /users/me, list pages, create+delete page de prueba, upsert idempotente, WP-CLI core version, option get siteurl, search-replace dry-run. Todos contra WordPress 6.9.4 real.

## ADRs relacionados

- ADR-004 — WP-CLI vía SSH desde host de control
- ADR-018 — Workarounds Local by Flywheel (PHP absoluto + socket MySQL)

## Errores tipados

| Excepción | Cuándo |
|---|---|
| `WpAuthError` | 401/403 — credenciales o permiso. NO se reintenta. |
| `WpNotFoundError` | 404 — recurso inexistente. NO se reintenta. |
| `WpRateLimitError` | 429/503 con Retry-After. Reintenta con backoff respetándolo. |
| `WpSchemaError` | Payload recibido no encaja con lo esperado. |
| `WpRestError` | Otros 4xx/5xx tras agotar retries. |
| `WpBulkPartialError` | Bulk con éxitos parciales (en modo `strict=True`). |
| `WpSshConnectionError` | No se pudo abrir SSH (DNS/puerto/key). |
| `WpSshAuthError` | Key rechazada. |
| `WpCliExecutionError` | `wp <comando>` devolvió exit_code != 0. |
