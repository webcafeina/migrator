---
name: wp-rest-bulk
description: Operaciones masivas vía WP REST API — bulk insert posts/pages, ACF fields, taxonomías, Gravity Forms, WooCommerce, WPML. Maneja rate limits, retries con backoff exponencial, atomicidad por batch e idempotencia por slug.
---

# Skill — WP REST Bulk

## Propósito

Wrapper sobre WP REST API para operaciones masivas con buenas propiedades operacionales:
- Idempotencia por slug o identificador estable
- Retries con backoff exponencial
- Detección de rate limit y pausa adaptativa
- Atomicidad por batch (todo o nada)
- Logs detallados por operación

## Cuándo usar este skill (vs `wpcli-ssh`)

- **N <= 100 items**: usar este skill (REST).
- **N > 100 items** O **operación compleja transaccional**: usar `wpcli-ssh`.

## Contrato

```python
class WpRestBulk:
    def __init__(self, base_url: str, user: str, app_password: str, timeout: float = 30.0):
        ...

    def bulk_insert_posts(
        self,
        posts: list[PostPayload],
        post_type: str = "page",
        batch_size: int = 20,
        idempotency_key: Callable[[PostPayload], str] = lambda p: p.slug,
    ) -> BulkResult:
        """Inserta o actualiza posts. Idempotente por slug."""

    def upload_media(self, files: list[Path], alt_texts: dict[str, str] | None = None) -> dict[Path, int]:
        """Sube ficheros y devuelve mapping ruta -> attachment_id."""

    def import_redirects(self, redirects: list[Redirect]) -> BulkResult:
        """Vía plugin Redirection (REST endpoint)."""

    def upsert_yoast_meta(self, post_id: int, meta: YoastMeta) -> None:
        """Inyecta meta SEO en un post."""

    def create_gravity_forms(self, forms: list[GfForm]) -> dict[str, int]:
        """Crea forms y devuelve mapping name -> form_id."""

    def upsert_woo_product(self, product: WooProduct) -> int:
        """Idempotente por SKU."""
```

## Endpoints relevantes

| Operación | Endpoint |
|---|---|
| Listar/crear page | `GET/POST /wp-json/wp/v2/pages` |
| Listar/crear post | `GET/POST /wp-json/wp/v2/posts` |
| Subir media | `POST /wp-json/wp/v2/media` (multipart) |
| Crear menu | `POST /wp-json/wp/v2/menus` (con plugin REST API Menus o WP 5.9+) |
| Yoast SEO meta | `POST /wp-json/yoast/v1/get_head` (lectura) + meta vía `meta:` del post |
| Bricks import | `POST /wp-json/bricks/v1/import` |
| Gravity Forms | `POST /wp-json/gf/v2/forms`, `POST /wp-json/gf/v2/entries` |
| WooCommerce | `POST /wp-json/wc/v3/products`, `POST /wp-json/wc/v3/products/{id}/variations` |
| WPML | `POST /wp-json/wpml/v1/...` (varía por sub-plugin) |
| Redirection plugin | `POST /wp-json/redirection/v1/redirect` |

## Autenticación

- **Preferente**: Application Passwords (WP 5.6+). Usuario con rol `editor` o `administrator` según operación.
- Header: `Authorization: Basic <base64(user:app_password)>`.
- Si la operación requiere `manage_options` (p. ej. Bricks import), usuario debe ser admin temporal.

## Idempotencia

Estrategia por entidad:

| Entidad | Clave idempotente |
|---|---|
| Page/Post | `slug` |
| Media | hash SHA-256 del fichero (en filename: `<hash>-<original-name>`) |
| Producto Woo | `sku` |
| Form Gravity | `title` + custom `wcm_external_id` (meta) |
| Redirect | `source_path` |

Antes de POST, hacer GET con filtro por la clave. Si existe → PUT/PATCH con merge.

## Retries

- 3 reintentos
- Backoff exponencial: 2 s, 8 s, 32 s
- Solo reintentar en: 408, 429, 500, 502, 503, 504, errores de red transitorios
- En 401/403/404: no reintentar, escalar como error.

## Rate limit

- WP REST por defecto no limita, pero algunos hosts (incluido cPanel + ModSecurity) sí.
- Detectar `429` o `503` con header `Retry-After` y respetar.
- Si más de 3 batches consecutivos hit rate limit: reducir `batch_size` a la mitad.

## Atomicidad por batch

- Cada batch es una unidad. Si un item del batch falla:
  - Opción A (default): saltar ese item, marcar como `failed` en `BulkResult.failures`, continuar.
  - Opción B (`strict=true`): rollback del batch entero (DELETE de los ya creados).

## Logs

- structlog por operación: `op=bulk_insert_posts batch=3 size=20 successes=19 failures=1`
- Sentry breadcrumb por batch.

## Casos límite documentados

- **Cuerpo de post > 2 MB**: WP rechaza por defecto. Para Bricks pages grandes (>500 elementos), usar `wpcli-ssh` siempre.
- **Imágenes EXIF con datos personales**: WP NO sanitiza por defecto. Strip EXIF en `image-pipeline` antes de subir.
- **Slugs con caracteres acentuados**: WP los normaliza a ASCII. Verificar mapping en `seo_redirects`.

## Dependencias externas

- `requests` (Python) o `httpx` async
- Credenciales en `.env`: `WP_DEFAULT_REST_USER`, `WP_DEFAULT_REST_APP_PASSWORD`

## Tests

- Mocks contra una instancia WP de prueba (a documentar setup en Fase 4)
- Fixtures de respuestas API en `tests/fixtures/wp-rest/`
