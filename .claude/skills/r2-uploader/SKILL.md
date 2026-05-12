---
name: r2-uploader
description: Upload a Cloudflare R2 con boto3 (R2 es S3-compatible). Bucket por proyecto o bucket global con prefijos. URLs públicas firmadas o públicas según configuración. Maneja multipart upload para ficheros grandes.
---

# Skill — R2 Uploader

## Propósito

Subir assets (imágenes optimizadas, PDFs, screenshots) a Cloudflare R2, S3-compatible y sin egress fees. Sirve como CDN cuando `project.asset_storage = "r2"`.

## Contrato

```python
class R2Uploader:
    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        public_url_base: str | None = None,  # https://assets.webcafeina.com
    ):
        self.client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )

    def upload_file(
        self,
        local_path: Path,
        key: str,
        content_type: str | None = None,
        public: bool = True,
        cache_control: str = "public, max-age=31536000, immutable",
    ) -> R2UploadResult:
        """Sube fichero. Si > 100 MB, usa multipart."""

    def upload_bytes(self, data: bytes, key: str, content_type: str, **kwargs) -> R2UploadResult: ...

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str: ...

    def delete(self, key: str) -> None: ...
    def delete_prefix(self, prefix: str) -> int:  # devuelve count
        ...
```

## Esquema de claves

```
projects/<project_id>/
  assets/
    <hash>/full.webp
    <hash>/large.webp
    <hash>/medium.webp
    <hash>/thumbnail.webp
    <hash>/original.<ext>
  screenshots/
    visual-diff/<slug>-<viewport>/source.png
    visual-diff/<slug>-<viewport>/target.png
    visual-diff/<slug>-<viewport>/overlay.png
  exports/
    checklist-<project_id>.pdf
    qa-report-<project_id>.json

leads/
  enrichments/
    <lead_id>/raw-<source>.json
```

## URLs públicas

- Si el bucket está conectado a un dominio custom (`assets.webcafeina.com`), los assets son accesibles directamente: `https://assets.webcafeina.com/projects/42/assets/abc.../full.webp`.
- Si no, usar presigned URLs con TTL (mínimo 1h, recomendado 7d para assets de checklist).

## Multipart upload

Activar automáticamente si `file_size > 100 MB`:
- `chunk_size = 16 MB`
- `max_concurrency = 4`
- Vía `boto3` `Object.upload_file()` con `Config(TransferConfig)`.

Casos donde aplica: vídeos (raros), exports completos de proyecto.

## Idempotencia

- Antes de upload: comprobar si la clave ya existe (`head_object`).
- Si existe y mismo size + ETag: skip.
- Si existe y distinto: sobrescribir (R2 lo permite).

## CORS

Bucket necesita CORS habilitado para que el dashboard sirva assets via fetch:

```json
[
  {
    "AllowedOrigins": ["https://migrator.webcafeina.com"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3000
  }
]
```

(Configuración manual única en el panel Cloudflare; documentar en `docs/despliegue.md`.)

## Errores tipados

- `R2UploaderError` (raíz)
- `R2AuthError`
- `R2BucketNotFoundError`
- `R2UploadFailedError`

## Limpieza al borrar proyecto

`delete_prefix("projects/<id>/")` elimina todo lo del proyecto. Llamado por job Celery cuando se borra el proyecto.

## Tests

- `moto` (mock S3) para tests unit
- Test multipart con fichero de 150 MB en fixture

## Dependencias

- `boto3` (S3 compat)
- Credenciales: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_PUBLIC_URL_BASE`
