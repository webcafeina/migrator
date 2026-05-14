"""Cliente Cloudflare R2 (S3-compatible) usando boto3.

R2 acepta el API S3 con un endpoint URL específico
(`https://<account_id>.r2.cloudflarestorage.com`). Usamos boto3 porque es
la lib estándar de la industria y se documenta así en los docs de
Cloudflare.

Operaciones del worker (AssetOptimizerAgent):
- `put_bytes(key, data, content_type)` → sube y devuelve la URL pública
  (si `public_url_base` está configurada) o el `r2://bucket/key` interno.
- `head_object(key)` → comprueba existencia (idempotencia).
- `delete_object(key)` → limpieza puntual.

ADR-026 documenta la decisión de S3-compat (boto3) vs SDK Cloudflare-only.
"""

from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger("wcm.worker.integrations.r2")


class R2UploadError(Exception):
    """Error al subir/leer un objeto en R2."""


class R2Client:
    """Cliente sincrónico. boto3 ya gestiona retries en su capa baja."""

    def __init__(
        self,
        *,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        public_url_base: str | None = None,
        s3_client: Any | None = None,
    ) -> None:
        if not all((account_id, access_key_id, secret_access_key, bucket)):
            raise R2UploadError("Credenciales R2 incompletas")
        self.account_id = account_id
        self.bucket = bucket
        self.public_url_base = public_url_base.rstrip("/") if public_url_base else None
        self._s3 = s3_client or self._build_s3(
            account_id=account_id,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
        )

    @classmethod
    def from_env(cls) -> R2Client | None:
        account = os.environ.get("R2_ACCOUNT_ID", "").strip()
        ak = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
        sk = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
        bucket = os.environ.get("R2_BUCKET", "").strip()
        if not all((account, ak, sk, bucket)):
            return None
        return cls(
            account_id=account,
            access_key_id=ak,
            secret_access_key=sk,
            bucket=bucket,
            public_url_base=os.environ.get("R2_PUBLIC_URL_BASE", "").strip() or None,
        )

    # ---------- public ----------

    def put_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        cache_control: str = "public, max-age=31536000, immutable",
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Sube `data` bajo `key`. Devuelve URL pública canónica si hay
        `public_url_base`, o `s3://<bucket>/<key>` si no.
        """
        if not key:
            raise R2UploadError("key vacía")
        kwargs: dict[str, Any] = {
            "Bucket": self.bucket,
            "Key": key,
            "Body": data,
            "ContentType": content_type,
            "CacheControl": cache_control,
        }
        if metadata:
            kwargs["Metadata"] = metadata
        try:
            self._s3.put_object(**kwargs)
        except Exception as e:  # noqa: BLE001 — boto raises ClientError sub-clases
            raise R2UploadError(f"put_object falló: {e}") from e
        if self.public_url_base:
            return f"{self.public_url_base}/{key.lstrip('/')}"
        return f"s3://{self.bucket}/{key.lstrip('/')}"

    def head_object(self, key: str) -> dict[str, Any] | None:
        """None si no existe. Cualquier otro error lanza R2UploadError."""
        try:
            return self._s3.head_object(Bucket=self.bucket, Key=key)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if "404" in msg or "Not Found" in msg or "NoSuchKey" in msg:
                return None
            raise R2UploadError(f"head_object falló: {e}") from e

    def delete_object(self, key: str) -> None:
        try:
            self._s3.delete_object(Bucket=self.bucket, Key=key)
        except Exception as e:  # noqa: BLE001
            raise R2UploadError(f"delete_object falló: {e}") from e

    # ---------- internals ----------

    @staticmethod
    def _build_s3(*, account_id: str, access_key_id: str, secret_access_key: str) -> Any:
        try:
            import boto3
        except ImportError as e:
            raise R2UploadError("boto3 no instalado") from e
        endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )
