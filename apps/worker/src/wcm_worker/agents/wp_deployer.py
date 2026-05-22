"""WpDeployerAgent — provisiona páginas Bricks en el WP destino.

MVP: asume que el WP destino ya tiene Bricks Builder activo (no
instalamos plugins automáticamente en esta fase; eso es responsabilidad
de Fase 10/12 con WPCLI).

Para cada `bricks_pages` exitosa, hace upsert de la página WP via REST y
escribe el `_bricks_page_content_2` post meta via WP-CLI (más fiable
para JSONs grandes).
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from wcm_db.models.bricks_pages import BricksPage
from wcm_db.models.projects import Project
from wcm_types.enums import ScrapeStatus
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import WpDeployerError
from wcm_wp_client import (
    WpClientConfig,
    WpCliSshClient,
    WpRestClient,
)

log = logging.getLogger("wcm.worker.wp_deployer")


class WpDeployerAgent(BaseAgent):
    name = "wp-deployer"
    phase_name = "deploy_wp"

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise WpDeployerError("WpDeployerAgent requiere project_id")
        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise WpDeployerError(f"Project {ctx.project_id} no encontrado")

        # Para MVP, la config WP destino viene del entorno global (sandbox
        # Local). En producción, project.hosting_target_json llevará los
        # parámetros específicos del cliente.
        try:
            wp_config = WpClientConfig.from_env()
        except ValueError as e:
            raise WpDeployerError(
                f"Config WP destino incompleta en .env: {e}"
            ) from e

        stmt = select(BricksPage).where(
            BricksPage.project_id == ctx.project_id,
            BricksPage.status == ScrapeStatus.SUCCESS,
        )
        bricks_pages = ctx.session.execute(stmt).scalars().all()

        if not bricks_pages:
            return AgentResult(summary="No hay bricks_pages listas para desplegar")

        # Ejecutar el async loop dentro de la task sync Celery.
        deployed, failed, theme_applied, homepage_set = asyncio.run(
            self._deploy_all(wp_config, bricks_pages, ctx, project)
        )

        return AgentResult(
            summary=(
                f"{deployed} páginas desplegadas, {failed} fallidas"
                + (", theme global aplicado" if theme_applied else "")
                + (", home marcada como portada" if homepage_set else "")
            ),
            outputs={
                "deployed": deployed,
                "failed": failed,
                "theme_applied": theme_applied,
                "homepage_set": homepage_set,
                "target": wp_config.site_url,
            },
        )

    async def _deploy_all(
        self,
        wp_config: WpClientConfig,
        bricks_pages: list[BricksPage],
        ctx: AgentContext,
        project: Project,
    ) -> tuple[int, int, bool, bool]:
        deployed = 0
        failed = 0
        theme_applied = False
        homepage_set = False

        async with WpRestClient(wp_config) as rest, WpCliSshClient(wp_config) as cli:
            # v0.24.0 — Bloque N. Crear WP menu antes del import si el
            # extractor capturó items reales. Bricks `nav-nested` con
            # `menu` apuntando a ID numérico de WP menu necesita que
            # el menu exista. Idempotente: si ya tenemos `wp_menu_id`,
            # skip.
            if project.nav_items_json and project.wp_menu_id is None:
                try:
                    menu_id = await self._create_wp_menu(
                        cli, project.nav_items_json
                    )
                    if menu_id:
                        project.wp_menu_id = menu_id
                        ctx.session.add(project)
                        log.info(
                            "wp_deployer_menu_created",
                            extra={"project_id": project.id, "menu_id": menu_id, "items": len(project.nav_items_json)},
                        )
                except Exception as e:  # noqa: BLE001
                    log.warning(
                        "wp_deployer_menu_create_failed",
                        extra={"project_id": project.id, "error": str(e)[:300]},
                    )

            for bp in bricks_pages:
                try:
                    # 1. Upsert de la página WP (idempotente por slug)
                    page_payload = {
                        "slug": bp.slug,
                        "title": bp.title,
                        "status": "draft",  # publicar manualmente desde dashboard
                        "content": "",  # Bricks usa post meta, no post_content
                    }
                    wp_page = await rest.upsert_page_by_slug(page_payload)
                    wp_post_id = wp_page["id"]

                    # 2. Escribir el bricks_json en post_meta via WP-CLI
                    #    (REST puede fallar con payloads grandes)
                    await cli.bricks_import_content(wp_post_id, bp.bricks_json)

                    bp.wp_post_id = wp_post_id
                    bp.last_import_error = None
                    deployed += 1
                except Exception as e:  # noqa: BLE001
                    bp.last_import_error = f"{type(e).__name__}: {e}"[:1000]
                    failed += 1

            # C.9 — aplicar el Bricks global theme una sola vez por
            # proyecto, tras importar las páginas. Reconstruimos el
            # theme desde `project.theme_styles_origin` con el mismo
            # builder que usa el transpiler, así no hay drift de schema.
            #
            # Bug I (2026-05-21) — MERGE en lugar de OVERWRITE.
            # `wp option update` con --format=json reemplaza la option
            # completa. Bricks tiene otras keys propias en
            # `bricks_global_settings` (postTypes, defaultBreakpoints,
            # customCode, etc.) que se perderían si las sobrescribimos.
            # Sin `postTypes` el botón "Edit with Bricks" NO aparece.
            # Estrategia: leer el option actual, fusionarlo con nuestro
            # theme (nuestros valores ganan en keys colisionadas), y
            # update con el resultado merged.
            #
            # Si falla por cualquier motivo (SSH timeout, WP-CLI no
            # encuentra Bricks aún) lo dejamos como warning y seguimos
            # — el theme se puede aplicar manualmente.
            try:
                from wcm_bricks_transpiler.theme import build_theme_styles

                theme = build_theme_styles(project.theme_styles_origin)
                theme_payload = theme.model_dump(by_alias=True)

                # Leer existing y hacer merge superficial. Si la option
                # no existe (instalación fresca de Bricks), partimos de
                # dict vacío.
                merged: dict = {}
                if await cli.option_exists("bricks_global_settings"):
                    existing_raw = await cli.option_get(
                        "bricks_global_settings", format="json"
                    )
                    if existing_raw:
                        import json as _json
                        try:
                            parsed = _json.loads(existing_raw)
                            if isinstance(parsed, dict):
                                merged = parsed
                        except _json.JSONDecodeError:
                            log.warning(
                                "wp_deployer_existing_option_non_json",
                                extra={"project_id": project.id},
                            )
                merged.update(theme_payload)
                # v0.25.0 — Si hay BRICKSTEMPLATE_API_URL configurado,
                # añadir Remote Templates URL al option. Idempotente:
                # operador cura una vez en setup hosting; los proyectos
                # comparten. El password de licencia NO se persiste en
                # el option (Bricks lo cachea en wp_options aparte). Esto
                # solo apunta a la URL que Bricks va a consultar.
                import os as _os
                remote_list = merged.get("remoteTemplates") or []

                # v0.25.0 — BricksTemplate.com (catálogo default).
                bt_url = _os.environ.get(
                    "BRICKSTEMPLATE_REMOTE_URL",
                    "https://brickstemplate.com/wp-json/bricks/v1/templates",
                ).strip()
                if bt_url and not any(
                    r.get("url") == bt_url for r in remote_list
                ):
                    remote_list.append({
                        "name": "BricksTemplate.com",
                        "url": bt_url,
                        # password lo añade el operador manualmente
                        # en Bricks > Settings la primera vez.
                    })

                # v0.27.0 B8 — BricksPlus opcional. Si env configurado,
                # se añade junto al anterior (Bricks acepta múltiples
                # Remote Template URLs simultáneos).
                bp_url = _os.environ.get("BRICKSPLUS_REMOTE_URL", "").strip()
                if bp_url and not any(
                    r.get("url") == bp_url for r in remote_list
                ):
                    remote_list.append({
                        "name": "BricksPlus",
                        "url": bp_url,
                    })

                if remote_list:
                    merged["remoteTemplates"] = remote_list
                await cli.option_update(
                    "bricks_global_settings", merged, format="json"
                )
                theme_applied = True
            except Exception as e:  # noqa: BLE001
                log.warning(
                    "wp_deployer_theme_apply_failed",
                    extra={"project_id": project.id, "error": str(e)[:300]},
                )

            # v0.23.0 — Persistir `bricks_global_classes` en el option
            # WP. Sin esto, los elementos del bricks_json que
            # referencian `_cssGlobalClasses: ["wcm-h2-abc123"]` NO
            # resuelven ningún CSS en el frontend (porque la clase no
            # existe). Bricks expone esta option como array de
            # `{id, name, settings}` y el frontend genera `<style>`
            # automáticamente con las reglas declaradas.
            try:
                global_classes = project.bricks_global_classes or []
                if global_classes:
                    # Merge con existing (otros proyectos pueden compartir
                    # destino y sobrescribir clases con mismo id es OK).
                    existing_classes: list = []
                    if await cli.option_exists("bricks_global_classes"):
                        existing_raw = await cli.option_get(
                            "bricks_global_classes", format="json"
                        )
                        if existing_raw:
                            import json as _json
                            try:
                                parsed = _json.loads(existing_raw)
                                if isinstance(parsed, list):
                                    existing_classes = parsed
                            except _json.JSONDecodeError:
                                pass
                    # Dedup por id: nuestras clases ganan a las existing.
                    new_ids = {c["id"] for c in global_classes if isinstance(c, dict) and c.get("id")}
                    merged_classes = [
                        c for c in existing_classes
                        if isinstance(c, dict) and c.get("id") not in new_ids
                    ]
                    merged_classes.extend(global_classes)
                    await cli.option_update(
                        "bricks_global_classes", merged_classes, format="json"
                    )
                    log.info(
                        "wp_deployer_global_classes_applied",
                        extra={
                            "project_id": project.id,
                            "n_classes": len(global_classes),
                            "n_merged": len(merged_classes),
                        },
                    )
            except Exception as e:  # noqa: BLE001
                log.warning(
                    "wp_deployer_global_classes_failed",
                    extra={"project_id": project.id, "error": str(e)[:300]},
                )

            # F — marcar la página `home` como página de inicio del WP
            # destino. WordPress por defecto muestra los posts; el
            # operador esperaría que la home migrada sea la portada.
            # Si no hay BricksPage con slug='home' (o no se importó OK)
            # se salta silenciosamente — no toda migración tendrá home.
            home_bp = next(
                (
                    bp for bp in bricks_pages
                    if bp.slug == "home" and bp.wp_post_id is not None
                ),
                None,
            )
            if home_bp is not None:
                try:
                    await cli.option_update("show_on_front", "page")
                    await cli.option_update(
                        "page_on_front", str(home_bp.wp_post_id)
                    )
                    homepage_set = True
                except Exception as e:  # noqa: BLE001
                    log.warning(
                        "wp_deployer_homepage_set_failed",
                        extra={
                            "project_id": project.id,
                            "wp_post_id": home_bp.wp_post_id,
                            "error": str(e)[:300],
                        },
                    )

        ctx.session.flush()
        return deployed, failed, theme_applied, homepage_set

    async def _create_wp_menu(
        self,
        cli: WpCliSshClient,
        nav_items: list[dict],
        *,
        menu_name: str = "main-menu",
    ) -> int | None:
        """v0.24.0 — Crea un WP menu vía wp-cli + añade items. Devuelve
        el ID numérico del menu (o None si falla).

        Idempotente al nivel de menu: si el menu ya existe, reusa su ID.
        NO es idempotente a nivel de items — re-runs duplicarían entries.
        El operador debe limpiar el menu manualmente si re-corre con
        nav cambiado.
        """
        # Crear menu (idempotente: wp menu create devuelve error si
        # existe, así que tratamos el caso).
        result = await cli.run_shell(
            f'wp menu create "{menu_name}" --porcelain || wp menu list --fields=term_id,name --format=csv | grep ",{menu_name}$" | head -n1 | cut -d, -f1'
        )
        if not result.ok or not result.stdout.strip():
            return None
        try:
            menu_id = int(result.stdout.strip().splitlines()[0])
        except (ValueError, IndexError):
            return None

        # Añadir items (top-level solo en MVP — children recursivos
        # diferidos a v0.25.0).
        for item in nav_items:
            label = item.get("label", "").replace('"', '\\"')
            url = item.get("url", "#")
            if not label or not url:
                continue
            await cli.run_shell(
                f'wp menu item add-custom {menu_id} "{label}" "{url}" --porcelain'
            )

        return menu_id
