"""Errores tipados del worker y de cada subagente.

Cada subagente define su `*Error` que hereda de `AgentError`. El
orchestrator captura por tipo y decide: reintentar (transitorios),
escalar a humano (no recuperables), o saltar fase (opcionales).
"""

from __future__ import annotations


class AgentError(Exception):
    """Raíz de la jerarquía de errores de subagentes."""

    is_retriable: bool = False  # default: error definitivo
    blocks_pipeline: bool = True  # default: bloquea el pipeline


class AgentNotImplementedError(AgentError):
    """El subagente es un stub. Se usa para diferenciar de bugs reales."""

    blocks_pipeline = False  # los stubs no deben tirar la pipeline en MVP


# ---------- Por subagente ----------

class ProspectorError(AgentError): ...
class FingerprinterError(AgentError): ...
class EnricherError(AgentError): ...
class OutreachComposerError(AgentError): ...
class OutreachSenderError(AgentError): ...

class ScraperOriginError(AgentError):
    """Pueden ser transitorios (red) o definitivos (auth/404)."""


class ContentExtractorError(AgentError): ...
class SeoPreserverError(AgentError): ...
class AssetOptimizerError(AgentError): ...
class MultilangHandlerError(AgentError): ...
class BricksTranspilerError(AgentError): ...
class WpDeployerError(AgentError): ...
class WooMigratorError(AgentError): ...
class WpmlConfiguratorError(AgentError): ...
class FormsRebuilderError(AgentError): ...
class VisualDiffError(AgentError): ...
class ChecklistGeneratorError(AgentError): ...
class ClickupSyncerError(AgentError): ...
class QaRunnerError(AgentError): ...
class ResendNotifierError(AgentError): ...
class RollbackAgentError(AgentError): ...
class PreDeploySnapshotError(AgentError): ...
class ThemeStylesError(AgentError):
    """No bloqueante: si el theme no se puede sintetizar, el pipeline
    sigue con theme=None y el destino usa defaults Bricks."""

    blocks_pipeline = False


class AssetUploaderError(AgentError):
    """v0.24.0 — No bloqueante: si N uploads fallan, marca SKIPPED y
    sigue. El destino renderea con URLs R2 (resolver doble seguridad)
    hasta que el operador re-corra la fase."""

    blocks_pipeline = False


class OpenAIClientError(AgentError):
    """v0.25.0 — Error genérico del cliente OpenAI.

    No bloqueante por sí solo: cada agente (BriefGenerator, RedesignAI)
    decide su política. BriefGenerator tolera fallo (operador rellena
    manualmente). RedesignAIAgent intenta 1 retry y luego cae a
    templates.
    """

    blocks_pipeline = False


class OpenAIAuthError(OpenAIClientError):
    """401/403 — API key inválida o expirada. Bloquea inmediatamente
    sin reintentar para no quemar requests inútiles."""


class OpenAIRateLimitError(OpenAIClientError):
    """429 — rate-limit del tier. El cliente reintenta con pausa larga."""


class OpenAIInvalidOutputError(OpenAIClientError):
    """El JSON devuelto no pasa el schema esperado (tool_use roto)."""


class BriefGeneratorError(AgentError):
    """v0.25.0 — No bloqueante: si BriefGenerator falla, el pipeline
    para en `BLOCKED_HUMAN_INPUT` y el operador edita brief desde el
    wizard."""

    blocks_pipeline = False


class RedesignAgentError(AgentError):
    """v0.25.0 — Error de RedesignTemplatesAgent o RedesignAIAgent."""

    blocks_pipeline = False


class BriefRefinementError(AgentError):
    """v0.27.0 — Error de BriefRefinementAgent.

    No bloquea pipeline (es un agente reactivo lanzado bajo demanda por
    el operador desde dashboard, no parte del flujo principal)."""

    blocks_pipeline = False


class BriefAggregatorError(AgentError):
    """v0.29.0 — Error de BriefSectionAggregator.

    No bloquea pipeline: si el agregador falla en una página, esa página
    mantiene sus secciones de bajo nivel (las que ya tenía el Brief) y se
    emite warning. Las demás páginas siguen siendo agregadas. Si OpenAI no
    está disponible globalmente, el pipeline continúa con el Brief
    plano — RedesignTemplates emitirá residuals como en v0.28.0."""

    blocks_pipeline = False


class AiAssistError(AgentError):
    """No bloqueante: si la AI vision falla, los bloques se mapean
    como RAW_HTML o quedan como UNKNOWN. El pipeline sigue.

    Sub-errores: AiAssistApiError (5xx persistente), AiAssistBudgetError
    (presupuesto alcanzado), AiAssistInvalidOutputError (Claude devuelve
    JSON que no pasa validator)."""

    blocks_pipeline = False


class ClaudeVisionError(Exception):
    """Errores del cliente Claude Vision (transitorios o definitivos)."""


class ClaudeVisionApiError(ClaudeVisionError):
    """5xx persistente o problema de red tras N retries."""


class ClaudeVisionAuthError(ClaudeVisionError):
    """401/403 — API key inválida o sin permisos."""


class ClaudeVisionInvalidOutputError(ClaudeVisionError):
    """Claude respondió pero el JSON Bricks no pasa el schema validator."""


# ---------- Orchestrator ----------

class OrchestrationError(Exception):
    """Errores del orquestador en sí (no de subagente)."""


class PhaseDependencyError(OrchestrationError):
    """Una fase intentó ejecutarse antes que su prerequisito."""


class UnrecoverableProjectError(OrchestrationError):
    """Estado inconsistente del proyecto, requiere intervención humana."""
