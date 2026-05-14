"""Generación determinista de IDs de elementos Bricks.

Bricks Builder requiere IDs `[a-z0-9]{6}` únicos por página. Generar
determinísticamente a partir del contexto (project_id, page_id,
order_index, block_type, sub_index) tiene tres ventajas:

1. **Idempotencia**: re-transpilar la misma página produce el mismo JSON,
   por lo que `wp-deployer` puede hacer diff/upsert estable.
2. **Trazabilidad**: dado un ID Bricks en producción, se reconstruye su
   origen lógico.
3. **Sin colisiones intra-página** cuando los componentes del tuple son
   distintos.

Implementación: blake2b con `digest_size=8`, codificado a base32 minúscula
y truncado a 6 chars (espacio ≈ 36^6 ≈ 2.18·10^9, suficiente para
páginas con miles de elementos). Colisiones se detectan por el generador.
"""

from __future__ import annotations

import hashlib
import string

_ALPHA = string.digits + string.ascii_lowercase  # 36 chars


def _encode_base36(num: int, length: int) -> str:
    """Encode entero a base36 con longitud fija (zero-padded a la izquierda)."""
    chars: list[str] = []
    for _ in range(length):
        chars.append(_ALPHA[num % 36])
        num //= 36
    return "".join(reversed(chars))


def make_element_id(
    project_id: int,
    page_id: int,
    order_index: int,
    block_type: str,
    sub_index: int = 0,
    salt: str = "wcm-bricks-v1",
) -> str:
    """Devuelve un ID Bricks determinista `[a-z0-9]{6}`.

    `sub_index` es para cuando un único `ContentBlock` genera múltiples
    elementos Bricks (p. ej. un hero genera section + container +
    heading + text + button; cada uno con su sub_index ∈ {0..N}).

    `salt` permite invalidar todos los IDs en bloque cambiando una sola
    constante (útil si se introduce un cambio incompatible de mapping).
    """
    key = f"{salt}|{project_id}|{page_id}|{order_index}|{block_type}|{sub_index}"
    digest = hashlib.blake2b(key.encode("utf-8"), digest_size=8).digest()
    num = int.from_bytes(digest, byteorder="big") % (36**6)
    return _encode_base36(num, 6)


class IdGenerator:
    """Generador con detección de colisiones intra-página.

    Aunque `make_element_id` es determinista por tuple, dos tuples distintos
    podrían (con probabilidad ~ 1/2.18B) producir el mismo hash. Si ocurre,
    el generador incrementa `sub_index` hasta encontrar un ID libre.
    """

    def __init__(self, project_id: int, page_id: int) -> None:
        self.project_id = project_id
        self.page_id = page_id
        self._used: set[str] = set()

    def fresh(self, order_index: int, block_type: str, sub_index: int = 0) -> str:
        """Devuelve un ID nuevo y único en esta página."""
        attempt = sub_index
        # max_attempts > 100 ya implicaría 100 colisiones consecutivas (probabilidad astronómica);
        # 1000 es un techo defensivo barato.
        for _ in range(1000):
            candidate = make_element_id(
                self.project_id, self.page_id, order_index, block_type, attempt
            )
            if candidate not in self._used:
                self._used.add(candidate)
                return candidate
            attempt += 1
        raise RuntimeError(
            f"IdGenerator: 1000 colisiones consecutivas para "
            f"(order={order_index}, block_type={block_type}). "
            f"Aumentar digest_size o cambiar salt."
        )

    @property
    def used(self) -> frozenset[str]:
        return frozenset(self._used)
