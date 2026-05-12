---
name: wpcli-ssh
description: Ejecutar WP-CLI sobre un servidor remoto vía SSH (paramiko). Cuándo usar WP-CLI vs REST. Gestión segura de credenciales SSH, ejecución idempotente, parsing de output.
---

# Skill — WP-CLI vía SSH

## Propósito

Ejecutar comandos WP-CLI en el servidor destino vía SSH, para operaciones bulk pesadas o transaccionales que vía REST API serían lentas o frágiles.

## Cuándo usar este skill (vs `wp-rest-bulk`)

- **N > 100 items**: WP-CLI gana por eficiencia (sin overhead HTTP).
- **Operaciones que requieren acceso a filesystem**: `wp config`, `wp core install`, `wp theme/plugin install --version=`.
- **Bulk transaccional**: `wp db query` con BEGIN/COMMIT.
- **Operaciones que el REST API no expone**: search-replace, db export, salt rotation, etc.

## Contrato

```python
class WpCliSsh:
    def __init__(
        self,
        host: str,
        user: str,
        port: int = 22,
        key_path: str = "~/.ssh/id_ed25519",
        wp_path: str = "/home/<user>/public_html",
        wpcli_bin: str = "/usr/local/bin/wp",
    ):
        ...

    def run(self, args: list[str], stdin: str | None = None, timeout: float = 60.0) -> WpCliResult:
        """Ejecuta `wp <args>` y devuelve stdout/stderr/exit_code."""

    def core_download(self, locale: str = "es_ES", version: str = "latest") -> None: ...
    def core_install(self, site: SiteConfig) -> None: ...
    def theme_install(self, theme_zip_path: str | None = None, slug: str | None = None, activate: bool = True) -> None: ...
    def plugin_install(self, slug_or_path: str, activate: bool = True, version: str | None = None) -> None: ...
    def bricks_import(self, json_payload: dict, post_id: int) -> None: ...
    def search_replace(self, old: str, new: str, tables: list[str] | None = None, dry_run: bool = True) -> SearchReplaceResult: ...
```

## Conexión SSH

- Usar `paramiko` (Python).
- Autenticación por clave (default `id_ed25519`).
- Validar `known_hosts` (no permitir auto-add en producción).
- Timeout default 60 s por comando; 600 s para operaciones largas (core install, bulk import).

## Patrón de ejecución

```python
def run(self, args):
    cmd = [self.wpcli_bin, f"--path={self.wp_path}"] + args
    # En servidores con WP-CLI proxy o phpfpm: prefijar `php -d memory_limit=512M`
    stdin, stdout, stderr = self.ssh_client.exec_command(shlex.join(cmd), timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    return WpCliResult(stdout.read(), stderr.read(), exit_code)
```

## Manejo de output

- WP-CLI por defecto imprime tabla humana. Para parsing usar `--format=json` o `--format=csv`.
- Si el comando tiene side-effects pero no output explícito: comprobar `exit_code == 0`.

## Idempotencia

| Comando | Idempotente | Notas |
|---|---|---|
| `wp core download` | ✅ | Si existe, no descarga |
| `wp core install` | ❌ | Falla si ya instalado; usar `wp core is-installed` antes |
| `wp theme install --activate` | ✅ | |
| `wp plugin install --activate` | ✅ | Si ya está, solo activa |
| `wp option update` | ✅ | |
| `wp post create` | ❌ | Crea duplicados; comprobar slug antes |

Patrón: cada operación destructiva precede de check de estado.

## Seguridad

- **Nunca pasar credenciales en argumentos**. Usar:
  - Archivos temporales con permisos `0600` (transferidos por SFTP, ejecutar, borrar).
  - Variables de entorno (`MYSQL_PWD` para `wp db`).
- **No loguear stdout completo si contiene secrets** (p. ej. `wp config shuffle-salts`). Redactar.
- Cerrar el `ssh_client` siempre (context manager).

## Casos límite

- **Servidor con safe-mode o `disable_functions`** que bloquea `exec`: WP-CLI puede fallar. Detectar y caer a REST API si posible.
- **WP-CLI en path no estándar**: `which wp` antes de asumir `/usr/local/bin/wp`.
- **Permisos del usuario SSH**: si el user no tiene permisos sobre `wp_path`, fallar pronto con mensaje claro.
- **Memoria PHP insuficiente**: añadir `php -d memory_limit=512M` al comando.

## Tests

- Mocks de `paramiko.SSHClient` para tests unitarios
- Tests integración contra VM/contenedor (LXC, sin Docker) con WP-CLI preinstalado

## Dependencias

- `paramiko`
- `shlex` (stdlib)
