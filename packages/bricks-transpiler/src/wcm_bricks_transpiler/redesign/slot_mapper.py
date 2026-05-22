"""SlotMapper — rellena placeholders del template con datos del Brief.

Sprint v0.25.0 B5. Pieza determinista: dado un JSON Bricks template +
`Brief.section` + `slot_map`, reemplaza los valores en las paths
indicadas por el contenido real del Brief, regenera los IDs Bricks
para evitar colisiones, y devuelve el árbol listo para concatenar al
page content.

`slot_map` shape:
    {
      "content[0].settings.text": "headline",       # path → brief key
      "content[1].settings.text": "subheadline",
      "content[2].settings.text": "cta.text",      # nested con dot
      "content[2].settings.link.url": "cta.url",
      "content[3].settings.image.url": "image_url",  # asset URL
      "content[3].settings.image.id": "image_id",    # WP attachment ID
    }

Cada PATH es JSONPath simplificado: solo soporta `key.key[idx].key`
(NO wildcards, NO filters JSONPath completos). Si el path no existe
en el template, se ignora (con warning).

Cada BRIEF_KEY usa dot-notation también: `cta.text` significa
`section["cta"]["text"]`. Si el path del Brief no existe, se ignora
(el template queda con el contenido del demo original — operador edita
después).

Assets: si el path apunta a `.image.url`, intenta resolver via
`asset_resolver` callable (inyectado por el agente).
"""

from __future__ import annotations

import copy
import logging
import re
from collections.abc import Callable
from typing import Any

log = logging.getLogger("wcm.bricks_transpiler.redesign.slot_mapper")


class SlotMapperError(Exception):
    """Error al aplicar un slot_map (template malformado, paths inválidos)."""


#: Pattern para parsear paths tipo `content[0].settings.text` o
#: `level1.level2[2].name`.
_PATH_TOKEN_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_-]*)(\[(\d+)\])?")


class SlotMapper:
    """Aplica un slot_map para rellenar un template con datos del Brief.

    Reusable entre secciones (mismo instance puede procesar múltiples
    `apply()` calls con templates distintos).
    """

    def __init__(
        self,
        *,
        id_generator: Callable[[], str] | None = None,
        asset_resolver: Callable[[int], dict[str, Any]] | None = None,
    ) -> None:
        """`id_generator`: callable que devuelve un ID Bricks nuevo (6
        chars `[a-z0-9]{6}`). Si None, se genera UUID4 truncado.

        `asset_resolver`: callable `(asset_id) -> {url, wp_attachment_id, alt}`
        para resolver imágenes. Si None, los slots de imagen se intentan
        rellenar con el valor crudo del Brief (URL externa o asset_id).
        """
        self._id_gen = id_generator or _default_id_generator
        self._asset_resolver = asset_resolver

    def apply(
        self,
        *,
        template: dict[str, Any],
        section: dict[str, Any],
        slot_map: dict[str, str],
    ) -> dict[str, Any]:
        """Devuelve un nuevo dict (deep copy) con slots rellenados +
        IDs regenerados.

        El template puede tener shape:
        - `{"content": [...elements...]}` (export Bricks completo)
        - `[...elements...]` (array directo)
        - dict suelto (un solo elemento)

        Normalizamos internamente a `{"content": [...]}` para procesarlo.
        """
        if not isinstance(template, dict):
            raise SlotMapperError(
                f"template debe ser dict, recibido {type(template).__name__}"
            )
        normalized = self._normalize_template(template)

        # 1) Deep copy para no mutar el template original (compartido
        # entre secciones del mismo proyecto).
        working = copy.deepcopy(normalized)

        # 2) Reasignar IDs Bricks (id_map: old_id → new_id).
        id_map = self._regenerate_ids(working["content"])
        self._rewrite_id_references(working["content"], id_map)

        # 3) Aplicar slot replacements.
        for path, brief_key in slot_map.items():
            value = self._extract_brief_value(section, brief_key)
            if value is None:
                continue
            # Si el slot es de imagen y tenemos asset_resolver,
            # interpreta `value` como asset_id (int) y resuelve.
            if self._is_asset_slot(path) and self._asset_resolver is not None and isinstance(value, int):
                resolved = self._asset_resolver(value)
                if path.endswith(".url"):
                    value = resolved.get("url", "")
                elif path.endswith(".id"):
                    value = resolved.get("wp_attachment_id", "")
                elif path.endswith(".alt"):
                    value = resolved.get("alt_text", "")
            try:
                self._set_path(working, path, value)
            except SlotMapperError as e:
                log.warning(
                    "slot_mapper_path_failed",
                    extra={"path": path, "key": brief_key, "error": str(e)},
                )

        return working

    # ---------- helpers ----------

    @staticmethod
    def _normalize_template(template: dict[str, Any]) -> dict[str, Any]:
        """Devuelve `{content: [...]}` aunque el template no lo tenga."""
        if "content" in template and isinstance(template["content"], list):
            return template
        # Si el template ES un elemento Bricks individual (`{id, name, settings}`):
        if "name" in template and "settings" in template:
            return {"content": [template]}
        raise SlotMapperError(
            "template shape no reconocido — debe ser {content: [...]} o un elemento Bricks"
        )

    def _regenerate_ids(self, elements: list[dict[str, Any]]) -> dict[str, str]:
        """Regenera el id de cada elemento. Devuelve `old_id → new_id`."""
        id_map: dict[str, str] = {}
        for el in elements:
            old_id = el.get("id")
            if not old_id:
                continue
            new_id = self._id_gen()
            id_map[old_id] = new_id
            el["id"] = new_id
        return id_map

    @staticmethod
    def _rewrite_id_references(elements: list[dict[str, Any]], id_map: dict[str, str]) -> None:
        """Reescribe `parent` y `children` de cada elemento usando el id_map.

        - `parent`: si está en id_map → reemplazar.
        - `children`: lista de IDs → reemplazar cada uno si está en id_map.
        - top-level (parent "0") se preserva.
        """
        for el in elements:
            if (parent := el.get("parent")) in id_map:
                el["parent"] = id_map[parent]
            if isinstance(el.get("children"), list):
                el["children"] = [
                    id_map.get(c, c) for c in el["children"]
                ]

    def _extract_brief_value(self, section: dict[str, Any], brief_key: str) -> Any:
        """Lee `section[brief_key]` con dot-notation (`cta.text`)."""
        if not brief_key:
            return None
        parts = brief_key.split(".")
        cur: Any = section
        for p in parts:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(p)
            if cur is None:
                return None
        return cur

    def _set_path(self, root: dict[str, Any], path: str, value: Any) -> None:
        """Aplica `root[path] = value` para path tipo
        `content[0].settings.text`. Levanta `SlotMapperError` si el path
        no existe.
        """
        if not path:
            raise SlotMapperError("path vacío")
        tokens = self._parse_path(path)
        if not tokens:
            raise SlotMapperError(f"path no parseable: {path!r}")

        cur: Any = root
        for token_key, token_idx in tokens[:-1]:
            if isinstance(cur, dict):
                cur = cur.get(token_key)
            else:
                raise SlotMapperError(
                    f"path {path!r}: esperaba dict en token {token_key!r}, "
                    f"encontré {type(cur).__name__}"
                )
            if token_idx is not None:
                if not isinstance(cur, list) or token_idx >= len(cur):
                    raise SlotMapperError(
                        f"path {path!r}: índice [{token_idx}] fuera de rango o no es lista"
                    )
                cur = cur[token_idx]
        # Último token: set.
        last_key, last_idx = tokens[-1]
        if not isinstance(cur, dict):
            raise SlotMapperError(
                f"path {path!r}: último container no es dict ({type(cur).__name__})"
            )
        if last_idx is not None:
            # Array set: requiere que cur[last_key] sea lista.
            target = cur.get(last_key)
            if not isinstance(target, list) or last_idx >= len(target):
                raise SlotMapperError(
                    f"path {path!r}: índice final fuera de rango"
                )
            target[last_idx] = value
        else:
            cur[last_key] = value

    @staticmethod
    def _parse_path(path: str) -> list[tuple[str, int | None]]:
        """`content[0].settings.text` → `[(content, 0), (settings, None), (text, None)]`."""
        tokens: list[tuple[str, int | None]] = []
        for part in path.split("."):
            match = _PATH_TOKEN_RE.match(part)
            if not match:
                return []
            key = match.group(1)
            idx_str = match.group(3)
            idx = int(idx_str) if idx_str is not None else None
            tokens.append((key, idx))
        return tokens

    @staticmethod
    def _is_asset_slot(path: str) -> bool:
        """True si el path apunta a una imagen Bricks (`.image.url`,
        `.image.id`, `.image.alt`)."""
        return ".image." in path


# ---------- helpers privados ----------


def _default_id_generator() -> str:
    """Genera ID Bricks de 6 chars `[a-z0-9]{6}`. UUID4 truncado +
    sanitizado para evitar dashes/uppercase."""
    import uuid
    raw = uuid.uuid4().hex
    # Filtra solo lowercase + dígitos y trunca.
    return "".join(c for c in raw if c.islower() or c.isdigit())[:6].ljust(6, "0")


__all__ = ["SlotMapper", "SlotMapperError"]
