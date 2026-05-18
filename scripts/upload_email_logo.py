#!/usr/bin/env python3
"""Sube el logo del header de los correos de outreach a Cloudflare R2.

Uso:
    python scripts/upload_email_logo.py

Lee `apps/api/assets/webcafeina-email-logo.png` (el equipo deja el PNG
ahí en su versión final ~600px ancho, fondo transparente, oscuro para
fondo blanco), lo sube al bucket R2 configurado en .env bajo la key
`branding/webcafeina-email-logo.png` y printa la URL pública para
pegarla en `.env` como `EMAIL_LOGO_URL`.

Operación idempotente: la key es fija, así que ejecutar varias veces
sobrescribe la misma URL (no genera duplicados). Cache-control: 1 año
inmutable — si necesitas cambiar el logo, súbelo con un suffix `?v=2`
o cambia la key (tras editar el layout HTML maestro).

Requiere R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET,
R2_PUBLIC_URL_BASE en el entorno (o en `.env` adyacente). Si falta
cualquier credencial sale con código 2 — usa el mismo R2Client del
worker para garantizar consistencia con el resto del pipeline de
assets (ADR-026).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Cargamos .env de la raíz si está disponible (mismo patrón que la API
# y el worker en arranque local).
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from wcm_worker.integrations.r2 import R2Client, R2UploadError

LOGO_LOCAL_PATH = (
    Path(__file__).resolve().parents[1] / "apps" / "api" / "assets" / "webcafeina-email-logo.png"
)
LOGO_R2_KEY = "branding/webcafeina-email-logo.png"

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("wcm.scripts.upload_email_logo")


def main() -> int:
    if not LOGO_LOCAL_PATH.exists():
        log.error(
            "No encuentro el PNG del logo en %s. Déjalo ahí (~600px ancho, "
            "transparente, versión oscura para fondo blanco) y vuelve a ejecutar.",
            LOGO_LOCAL_PATH,
        )
        return 1

    client = R2Client.from_env()
    if client is None:
        log.error(
            "Credenciales R2 incompletas. Verifica R2_ACCOUNT_ID, "
            "R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET y "
            "R2_PUBLIC_URL_BASE en .env."
        )
        return 2

    data = LOGO_LOCAL_PATH.read_bytes()
    try:
        url = client.put_bytes(
            LOGO_R2_KEY,
            data,
            content_type="image/png",
            metadata={"purpose": "email-header-logo", "version": "v0.14.0"},
        )
    except R2UploadError as e:
        log.error("Subida a R2 falló: %s", e)
        return 3

    log.info("Logo subido. Pega esta línea en tu .env:")
    log.info("EMAIL_LOGO_URL=%s", url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
