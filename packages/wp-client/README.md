# packages/wp-client

Cliente unificado para WordPress destino — REST API + WP-CLI vía SSH.

## Estado

Vacío en Fase 0. Se materializa en **Fase 4 — WP client**.

## Qué contendrá

- `WpRestClient` (REST API, idempotencia, retries, rate limit) — implementa skill `wp-rest-bulk`.
- `WpCliSshClient` (paramiko, ejecución remota) — implementa skill `wpcli-ssh`.
- Wrappers de alto nivel:
  - `install_plugin(slug, version=None, activate=True)`
  - `import_bricks_page(post_id, bricks_json)`
  - `bulk_insert_redirects(redirects)`
  - `configure_wpml(langs, primary)`
  - `create_woo_product(payload)`
  - `create_gravity_form(schema)`
- Manejo de credenciales SSH key + Application Password.

## Subagentes que lo usan

- `wp-deployer`, `woo-migrator`, `wpml-configurator`, `forms-rebuilder`

Ver [STATE.md](../../STATE.md).
