"""WpmlConfiguratorAgent — guía manual WPML, sin licencia (v0.17.0).

Decisión arquitectónica: Webcafeína NO tiene licencia WPML, por lo
que este agent NUNCA instala ni configura nada en el destino.
Su único trabajo es generar UNA ResidualTask muy detallada con:

- Lista de idiomas detectados por `multilang-handler`.
- Páginas agrupadas por idioma (con URL origen + slug destino).
- Guía paso-a-paso de configuración manual WPML.
- Estimación realista de horas para el operador.

Condicional: solo se invoca si `project.is_multilang=True`. Si por
algún motivo se llama con is_multilang=False, devuelve summary
explicativo sin crear residual.

Casos futuro: si Webcafeína adquiere licencia WPML, este agent se
extiende para llamar a `/wp-json/wpml/v1/languages` y crear las
traducciones — pero sin licencia es trabajo manual obligatorio.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from sqlalchemy import select

from wcm_db.models.projects import Project
from wcm_db.models.residual_tasks import ResidualTask
from wcm_db.models.scraped_pages import ScrapedPage
from wcm_types.enums import ResidualCategory, ResidualStatus
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import WpmlConfiguratorError

log = logging.getLogger("wcm.worker.wpml_configurator")


class WpmlConfiguratorAgent(BaseAgent):
    name = "wpml-configurator"
    phase_name = "configure_wpml"

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise WpmlConfiguratorError("WpmlConfiguratorAgent requiere project_id")

        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise WpmlConfiguratorError(f"Project {ctx.project_id} no encontrado")

        if not project.is_multilang:
            return AgentResult(
                summary=(
                    f"Project {project.id}: is_multilang=False, fase saltada."
                )
            )

        langs = list(project.langs or [])
        primary = project.primary_lang or (langs[0] if langs else None)

        pages = list(
            ctx.session.execute(
                select(ScrapedPage).where(ScrapedPage.project_id == project.id)
            ).scalars().all()
        )

        pages_by_lang: dict[str, list[ScrapedPage]] = defaultdict(list)
        for p in pages:
            short = (p.lang or "??")[:2].lower()
            pages_by_lang[short].append(p)

        description = _build_residual_description(
            client_name=project.client_name,
            target_domain=project.target_domain,
            langs=langs,
            primary=primary,
            pages_by_lang=pages_by_lang,
        )

        ctx.session.add(
            ResidualTask(
                project_id=project.id,
                title=f"Configurar WPML manualmente ({len(langs)} idiomas)",
                description=description,
                category=ResidualCategory.BLOCKING_GO_LIVE,
                status=ResidualStatus.OPEN,
                estimated_minutes=_estimate_minutes(pages_by_lang),
                generated_by="wpml-configurator",
            )
        )
        ctx.session.flush()

        return AgentResult(
            summary=(
                f"Project {project.id}: residual WPML creada · "
                f"{len(langs)} idiomas · {len(pages)} páginas total."
            ),
            outputs={
                "langs": langs,
                "primary_lang": primary,
                "pages_total": len(pages),
                "pages_per_lang": {k: len(v) for k, v in pages_by_lang.items()},
            },
            residual_tasks_created=1,
        )


def _build_residual_description(
    *,
    client_name: str,
    target_domain: str | None,
    langs: list[str],
    primary: str | None,
    pages_by_lang: dict[str, list[ScrapedPage]],
) -> str:
    """Texto largo, formato Markdown — lo renderiza checklist-generator."""
    lines: list[str] = []
    lines.append(
        "Webcafeína NO tiene licencia WPML. Esta tarea requiere "
        "configuración manual en el WordPress destino.\n"
    )

    lines.append("## Contexto detectado")
    lines.append(f"- Cliente: **{client_name}**")
    if target_domain:
        lines.append(f"- Destino: **{target_domain}**")
    lines.append(f"- Idioma principal: **{primary or '?'}**")
    lines.append(f"- Idiomas totales: **{', '.join(langs) if langs else 'ninguno'}**")
    lines.append("")

    lines.append("## Pasos de configuración WPML")
    lines.append(
        "1. **Adquirir licencia WPML Multilingual CMS** "
        "(https://wpml.org/purchase/) — plan mínimo recomendado: "
        "Multilingual CMS (~$99/año)."
    )
    lines.append(
        "2. Subir e instalar los plugins WPML al destino:\n"
        "   - WPML Multilingual CMS (core).\n"
        "   - WPML String Translation.\n"
        "   - WPML Translation Management.\n"
        "   - WPML Media Translation (si hay imágenes con copy)."
    )
    lines.append(
        "3. Activar la licencia desde WordPress admin → WPML → Soporte."
    )
    lines.append(
        f"4. WPML → Idiomas → seleccionar `{primary or 'es'}` como idioma "
        "principal y añadir los secundarios:"
    )
    for lang in langs:
        if lang != primary:
            lines.append(f"   - `{lang}`")
    lines.append(
        "5. Configurar el switcher (menú o widget) — recomendado: "
        "selector en menú principal con flags + códigos de idioma."
    )
    lines.append(
        "6. Para cada página del idioma principal, crear su versión "
        "traducida desde WPML → Translations → Plus icon junto a la página."
    )
    lines.append("")

    lines.append("## Páginas pendientes de traducir")
    if not pages_by_lang:
        lines.append("_(Scraping no detectó páginas por idioma)_")
    else:
        for lang in sorted(pages_by_lang.keys()):
            pages = pages_by_lang[lang]
            lines.append(f"### Idioma `{lang}` ({len(pages)} páginas)")
            for p in pages[:50]:
                slug = p.slug or p.url.rstrip("/").rsplit("/", 1)[-1] or "/"
                lines.append(f"- `{slug}` ← {p.url}")
            if len(pages) > 50:
                lines.append(f"- … y {len(pages) - 50} más")
            lines.append("")

    lines.append("## Validación final")
    lines.append(
        "- Cambiar el idioma del switcher en distintas páginas y verificar "
        "que el contenido se traduce correctamente."
    )
    lines.append(
        "- Verificar URLs hreflang en `<head>` de cada idioma "
        "(WPML las añade automáticamente)."
    )
    lines.append(
        "- Asegurar que el sitemap.xml incluye todas las versiones "
        "(WPML → SEO → integración con Yoast / Rank Math)."
    )

    return "\n".join(lines)


def _estimate_minutes(pages_by_lang: dict[str, list[ScrapedPage]]) -> int:
    """Estimación realista: 30 min setup + 5 min por página secundaria."""
    if not pages_by_lang:
        return 60
    total_secondary = sum(
        len(pages) for lang, pages in pages_by_lang.items() if lang != "??"
    )
    return 30 + total_secondary * 5
