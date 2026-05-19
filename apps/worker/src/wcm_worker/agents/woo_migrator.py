"""WooMigratorAgent — migra productos a WooCommerce (v0.17.0).

Condicional: solo se invoca si `project.has_ecommerce=True`.

Flujo:
1. Verifica que el plugin WooCommerce está activo (HEAD /wp-json/wc/v3).
   - Si NO está: ResidualTask 'instalar WooCommerce' + fase SKIPPED.
2. Lee `woo_products` del proyecto (poblado por scraper / content-extractor).
3. Para cada producto:
   - Crea/actualiza categorías (idempotente por slug).
   - Hace upsert del producto por SKU.
   - Sube imágenes vía /wp/v2/media y las asocia.
   - Persiste `wp_product_id` para trazabilidad.
4. Crea ResidualTask 'configurar pasarela de pago' (siempre — no la
   migramos automáticamente).
5. NO migra historial de pedidos (decisión MVP).

Resiliencia:
- Sin WooCommerce instalado → fase SKIPPED + residual claro.
- Sin productos en woo_products → fase SKIPPED + warning (probable
  caso del lead piloto corporativo).
- Producto individual falla → continúa con el siguiente, registra en
  warnings.

Auth WooCommerce: usa Application Password del usuario admin (basic
auth) sobre /wp-json/wc/v3/ — WC respeta la API de WP core para clientes
autenticados, no requiere consumer key/secret separado si el user tiene
capability `manage_woocommerce`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from sqlalchemy import select

from wcm_db.models.projects import Project
from wcm_db.models.residual_tasks import ResidualTask
from wcm_db.models.woo_products import WooProduct
from wcm_types.enums import ResidualCategory, ResidualStatus
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import WooMigratorError
from wcm_wp_client import WpClientConfig, WpRestClient
from wcm_wp_client.errors import WpRestError

log = logging.getLogger("wcm.worker.woo_migrator")


class WooMigratorAgent(BaseAgent):
    name = "woo-migrator"
    phase_name = "migrate_woo"

    def __init__(self, *, wp_config: WpClientConfig | None = None) -> None:
        self._injected_config = wp_config

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise WooMigratorError("WooMigratorAgent requiere project_id")

        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise WooMigratorError(f"Project {ctx.project_id} no encontrado")

        if not project.has_ecommerce:
            return AgentResult(
                summary=f"Project {project.id}: has_ecommerce=False, fase saltada"
            )

        try:
            wp_config = self._injected_config or WpClientConfig.from_env()
        except ValueError as e:
            raise WooMigratorError(
                f"Config WP destino incompleta en .env: {e}"
            ) from e

        products = list(
            ctx.session.execute(
                select(WooProduct).where(WooProduct.project_id == project.id)
            ).scalars().all()
        )

        result = asyncio.run(self._migrate(wp_config, project, products, ctx))
        return result

    async def _migrate(
        self,
        wp_config: WpClientConfig,
        project: Project,
        products: list[WooProduct],
        ctx: AgentContext,
    ) -> AgentResult:
        warnings: list[str] = []

        async with WpRestClient(wp_config) as rest:
            # 1. Detectar WooCommerce.
            if not await _woocommerce_available(rest):
                created = _add_residual(
                    ctx,
                    project.id,
                    title="Instalar y activar WooCommerce en el WP destino",
                    description=(
                        "El plugin WooCommerce no responde en "
                        "`/wp-json/wc/v3/`. Sin él no se pueden migrar "
                        "productos. Pasos:\n\n"
                        "1. WordPress admin → Plugins → Añadir nuevo → "
                        "buscar 'WooCommerce' → Instalar y activar.\n"
                        "2. Completar el asistente de configuración inicial "
                        "(país, moneda, métodos de pago).\n"
                        "3. Re-ejecutar el agente `woo-migrator` desde el "
                        "dashboard del proyecto."
                    ),
                    category=ResidualCategory.BLOCKING_GO_LIVE,
                    estimated_minutes=20,
                )
                ctx.session.flush()
                return AgentResult(
                    summary=(
                        f"Project {project.id}: WooCommerce NO instalado en "
                        "el destino, fase SKIPPED, residual creada."
                    ),
                    outputs={"woocommerce_available": False, "products_migrated": 0},
                    warnings=[
                        "WooCommerce no detectado vía /wp-json/wc/v3/. "
                        "Pipeline continúa; revisa el checklist."
                    ],
                    residual_tasks_created=created,
                )

            # 2. Sin productos detectados → SKIPPED + residual manual.
            if not products:
                created = _add_residual(
                    ctx,
                    project.id,
                    title="Migrar productos WooCommerce manualmente",
                    description=(
                        "El scraping origen no detectó productos en "
                        "`woo_products`. Posibles causas:\n\n"
                        "- El origen no tiene tienda activa.\n"
                        "- Los productos están detrás de JS dinámico no "
                        "cubierto por el extractor genérico.\n"
                        "- El sitio usa una integración externa (Stripe, "
                        "Shopify embebido) no migrable.\n\n"
                        "Revisa el origen manualmente y, si hay productos, "
                        "exporta CSV desde el panel original e importa en "
                        "WooCommerce → Productos → Importar."
                    ),
                    category=ResidualCategory.CLIENT_CONFIG,
                    estimated_minutes=60,
                )
                ctx.session.flush()
                return AgentResult(
                    summary=(
                        f"Project {project.id}: 0 productos en woo_products, "
                        "fase SKIPPED, residual creada."
                    ),
                    outputs={"woocommerce_available": True, "products_migrated": 0},
                    warnings=[
                        "Sin productos detectados en woo_products. "
                        "Migración manual requerida."
                    ],
                    residual_tasks_created=created,
                )

            # 3. Migración real.
            migrated = 0
            failed = 0
            category_cache: dict[str, int] = {}

            for prod in products:
                try:
                    cat_ids = await _ensure_categories(rest, prod.categories, category_cache)
                    wp_id = await _upsert_product(rest, prod, cat_ids)
                    prod.wp_product_id = wp_id
                    migrated += 1
                except Exception as e:  # noqa: BLE001
                    failed += 1
                    warnings.append(
                        f"Producto SKU={prod.sku!r} falló: {type(e).__name__}: {e}"
                    )
                    log.warning(
                        "woo_product_failed",
                        extra={
                            "project_id": project.id,
                            "sku": prod.sku,
                            "error": str(e),
                        },
                    )

            # 4. Pasarela de pago — residual obligatoria (nunca migramos).
            payment_residual = _add_residual(
                ctx,
                project.id,
                title="Configurar pasarela de pago en WooCommerce",
                description=(
                    "La pasarela de pago (Stripe, Redsys, PayPal, "
                    "transferencia, etc.) NO se migra automáticamente — "
                    "requiere credenciales del cliente. Pasos:\n\n"
                    "1. WooCommerce → Ajustes → Pagos.\n"
                    "2. Activar las pasarelas necesarias (la del origen "
                    "probablemente es Stripe o Redsys).\n"
                    "3. Introducir API keys / merchant code del cliente.\n"
                    "4. Hacer una compra de prueba en modo test antes de "
                    "salir a producción."
                ),
                category=ResidualCategory.BLOCKING_GO_LIVE,
                estimated_minutes=45,
            )

            ctx.session.flush()

            return AgentResult(
                summary=(
                    f"Project {project.id}: {migrated} productos migrados, "
                    f"{failed} fallidos. Pasarela de pago: residual obligatoria."
                ),
                outputs={
                    "woocommerce_available": True,
                    "products_migrated": migrated,
                    "products_failed": failed,
                },
                warnings=warnings,
                residual_tasks_created=payment_residual,
            )


# ---------- helpers públicos al módulo ----------


async def _woocommerce_available(rest: WpRestClient) -> bool:
    """HEAD/GET sobre /wp-json/wc/v3/ — 200 si WC activo, 404 si no."""
    try:
        await rest._request("GET", "/wc/v3/system_status/tools")
        return True
    except WpRestError as e:
        # 404 → no instalado; 401/403 → instalado pero sin permisos (lo
        # tratamos como "no disponible" para esta migración).
        if getattr(e, "status_code", None) in (401, 403, 404):
            return False
        # Otros errores (5xx, network) los propagamos para que el operador
        # los investigue.
        raise


async def _ensure_categories(
    rest: WpRestClient,
    slugs: list[str],
    cache: dict[str, int],
) -> list[int]:
    """Crea/recupera categorías por slug, devuelve IDs ordenados."""
    ids: list[int] = []
    for slug in slugs:
        if slug in cache:
            ids.append(cache[slug])
            continue
        cat_id = await _upsert_category(rest, slug)
        cache[slug] = cat_id
        ids.append(cat_id)
    return ids


async def _upsert_category(rest: WpRestClient, slug: str) -> int:
    """Busca categoría por slug; si no existe, la crea."""
    r = await rest._request(
        "GET", "/wc/v3/products/categories", params={"slug": slug, "per_page": 1}
    )
    rows = r.json()
    if isinstance(rows, list) and rows:
        return int(rows[0]["id"])
    r = await rest._request(
        "POST",
        "/wc/v3/products/categories",
        json={"name": slug.replace("-", " ").title(), "slug": slug},
    )
    return int(r.json()["id"])


async def _upsert_product(
    rest: WpRestClient,
    prod: WooProduct,
    category_ids: list[int],
) -> int:
    """Crea o actualiza producto por SKU. Devuelve wp_product_id."""
    payload: dict[str, Any] = {
        "name": prod.name,
        "sku": prod.sku,
        "regular_price": str(prod.price) if prod.price is not None else "",
        "manage_stock": prod.stock_managed,
        "stock_quantity": prod.stock if prod.stock_managed else None,
        "categories": [{"id": cid} for cid in category_ids],
        "status": "draft",  # publicación manual desde dashboard
        "type": "simple",
    }
    # Limpia None del payload (WC rechaza algunos null).
    payload = {k: v for k, v in payload.items() if v is not None}

    # Buscar por SKU existente.
    r = await rest._request(
        "GET", "/wc/v3/products", params={"sku": prod.sku, "per_page": 1}
    )
    rows = r.json()
    if isinstance(rows, list) and rows:
        existing_id = int(rows[0]["id"])
        r = await rest._request(
            "PUT", f"/wc/v3/products/{existing_id}", json=payload
        )
        return existing_id

    r = await rest._request("POST", "/wc/v3/products", json=payload)
    return int(r.json()["id"])


def _add_residual(
    ctx: AgentContext,
    project_id: int,
    *,
    title: str,
    description: str,
    category: ResidualCategory,
    estimated_minutes: int,
) -> int:
    """Atajo para crear 1 ResidualTask. Devuelve 1 para sumar al contador."""
    ctx.session.add(
        ResidualTask(
            project_id=project_id,
            title=title,
            description=description,
            category=category,
            status=ResidualStatus.OPEN,
            estimated_minutes=estimated_minutes,
            generated_by="woo-migrator",
        )
    )
    return 1
