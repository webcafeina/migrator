# packages/bricks-transpiler

**Núcleo crítico del producto.** Transpilador de `content_blocks` + CSS extraído a JSON nativo de Bricks Builder.

## Estado

Vacío en Fase 0. Se materializa en **Fase 2 — Bricks transpiler**.

> ⚠️ Bloqueado por **WCM-001** (obtener export real de Bricks). Sin él, no se puede definir el esquema canónico.

## Qué contendrá

- Tipos TS + Python (Pydantic) del esquema Bricks (sincronizados vía `packages/shared-types`).
- Mapeo `content_block.block_type` → elemento Bricks.
- Generación de IDs deterministas y únicos por página.
- Theme Styles globales a partir de CSS origen.
- Validación contra `bricks-json-schema/validate.py`.
- Tests con fixtures HTML/CSS → JSON Bricks esperado.

## Skill relacionado

- `bricks-json-schema` (contrato del JSON)

## Subagente que lo usa

- `bricks-transpiler` agente (orquesta el mapping y la validación)

Ver [STATE.md](../../STATE.md).
