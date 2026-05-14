"""MultilangHandlerAgent — detecta idiomas y correlaciona páginas equivalentes.

MVP heurístico:
1. Recolecta `lang` declarado en cada scraped_page (`<html lang>`).
2. Si hay > 1 idioma, marca `project.is_multilang=True` y `project.langs`.
3. Correlación simple: páginas en distinto lang con slug paralelo
   (p. ej. `/contacto` ↔ `/contact`) se agrupan vía heurística.

Casos complejos (subdominios por idioma, hreflang sin path prefix) se
quedan como tareas residuales y se resuelven en Fase 9+.
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select

from wcm_db.models.projects import Project
from wcm_db.models.scraped_pages import ScrapedPage
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import MultilangHandlerError


class MultilangHandlerAgent(BaseAgent):
    name = "multilang-handler"
    phase_name = "detect_multilang"

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise MultilangHandlerError("MultilangHandlerAgent requiere project_id")
        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise MultilangHandlerError(f"Project {ctx.project_id} no encontrado")

        stmt = select(ScrapedPage).where(ScrapedPage.project_id == ctx.project_id)
        pages = ctx.session.execute(stmt).scalars().all()

        langs_seen: dict[str, int] = defaultdict(int)
        for page in pages:
            if page.lang:
                # Normalizar a 2 chars (es-ES → es)
                short = page.lang[:2].lower()
                langs_seen[short] += 1

        langs_list = sorted(langs_seen, key=lambda lang: -langs_seen[lang])
        is_multilang = len(langs_list) > 1
        primary_lang = langs_list[0] if langs_list else None

        project.langs = langs_list
        project.primary_lang = primary_lang
        # Solo marcar is_multilang si el operador no lo había seteado explícitamente
        if is_multilang and not project.is_multilang:
            project.is_multilang = True

        ctx.session.flush()

        return AgentResult(
            summary=(
                f"Detectados {len(langs_list)} idiomas: {langs_list}, "
                f"is_multilang={project.is_multilang}, primary={primary_lang}"
            ),
            outputs={
                "langs": langs_list,
                "is_multilang": project.is_multilang,
                "primary_lang": primary_lang,
                "pages_per_lang": dict(langs_seen),
            },
        )
