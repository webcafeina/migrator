"""Servicio de embeddings — sentence-transformers + multilingual-e5-large.

Diseño:
- Singleton lazy: el modelo carga en la primera llamada (no en import).
  Esto evita coste de arranque en procesos worker que no calculen embeddings.
- `embed_text(text)` → list[float] de 1024 dim, con prefijo "passage: ".
- `embed_query(text)` para búsqueda semántica (prefijo "query: ").
- `embed_batch(texts)` para eficiencia.
- LRU cache para textos exactamente repetidos.

Para producción con miles de leads/min, considerar microservicio dedicado
con GPU. En MVP, CPU es suficiente (~50ms/texto en M2/x86 modernos).

ADR-023 documenta esta decisión (supersede ADR-010).
"""

from __future__ import annotations

import logging
import os
import threading
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from sentence_transformers import SentenceTransformer

log = logging.getLogger("wcm.worker.embedding")

#: Dimensión fija del schema (LEAD_EMBEDDING_DIM en db-schema).
#: Si cambia el modelo, mantener este match es obligatorio o migrar la
#: columna pgvector + reindex (operación cara).
EMBEDDING_DIM = 1024

#: Default model. Override con env var EMBEDDING_MODEL.
DEFAULT_MODEL = "intfloat/multilingual-e5-large"


class EmbeddingService:
    """Singleton lazy con thread-safe load.

    Uso típico desde un agent:
        from wcm_worker.embedding import get_embedding_service
        vec = get_embedding_service().embed_text("texto del lead")
    """

    _instance: "EmbeddingService | None" = None
    _lock = threading.Lock()

    def __init__(self, model_name: str | None = None, device: str | None = None) -> None:
        self.model_name = model_name or os.environ.get("EMBEDDING_MODEL", DEFAULT_MODEL)
        self.device = device or os.environ.get("EMBEDDING_DEVICE", "cpu")
        self._model: SentenceTransformer | None = None

    @classmethod
    def get(cls) -> "EmbeddingService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Solo para tests. Limpia el singleton."""
        with cls._lock:
            cls._instance = None

    @property
    def model(self):
        """Lazy load. La primera llamada tarda 20-40s descargando + cargando
        el modelo (~2.2GB primera vez)."""
        if self._model is None:
            log.info(
                "loading_embedding_model",
                extra={"model": self.model_name, "device": self.device},
            )
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise RuntimeError(
                    "sentence-transformers no instalado. Instala con: "
                    "pip install sentence-transformers"
                ) from e
            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def embed_text(self, text: str) -> list[float]:
        """Embedding de un texto único como pasaje (corpus indexable).

        Aplica el prefijo "passage: " automáticamente (convención e5).
        Para búsqueda semántica usar `embed_query`.
        """
        return list(self._cached_embed(_normalize(text), "passage: "))

    def embed_query(self, text: str) -> list[float]:
        """Embedding de una query de búsqueda semántica."""
        return list(self._cached_embed(_normalize(text), "query: "))

    def embed_batch(
        self, texts: list[str], *, batch_size: int = 16, as_query: bool = False
    ) -> list[list[float]]:
        """Batch sin cache (uso típico: enriquecer N leads de una campaña)."""
        if not texts:
            return []
        prefix = "query: " if as_query else "passage: "
        prepared = [f"{prefix}{_normalize(t)}" for t in texts]
        embeddings = self.model.encode(
            prepared,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return [vec.tolist() for vec in embeddings]

    # ---------- internos ----------

    @lru_cache(maxsize=256)
    def _cached_embed(self, text: str, prefix: str) -> tuple[float, ...]:
        """LRU cacheada — `tuple` para inmutabilidad/hashable."""
        vec = self.model.encode(
            f"{prefix}{text}",
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return tuple(float(x) for x in vec)


def _normalize(text: str) -> str:
    """Saneamiento mínimo: trim + colapsar whitespace + truncar a ~512 tokens.

    e5-large tiene ventana de 512 tokens; 1 token ≈ 4 chars en español →
    cortamos a 2000 chars para evitar truncado interno descontrolado.
    """
    cleaned = " ".join((text or "").split())
    if len(cleaned) > 2000:
        cleaned = cleaned[:2000]
    return cleaned


def get_embedding_service() -> EmbeddingService:
    """Helper conveniente: `get_embedding_service().embed_text(...)`."""
    return EmbeddingService.get()
