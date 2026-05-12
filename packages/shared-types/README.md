# packages/shared-types

Tipos compartidos entre Python (Pydantic v2) y TypeScript 5. Fuente única de la verdad para el contrato de datos del sistema.

## Estado

Vacío en Fase 0. Se materializa en **Fase 1 — DB y modelos**.

## Estrategia

- Definir modelos Pydantic en `python/` como fuente canónica.
- Generar `.d.ts` automáticamente a partir de Pydantic (vía `datamodel-code-generator` o script propio).
- Tipos clave que comparten:
  - `Project`, `ProjectPhase`, `Lead`, `LeadEnrichment`
  - `OutreachSequence`, `OutreachSend`
  - `ScrapedPage`, `ContentBlock`, `Asset`, `BricksPage`
  - `ResidualTask`
  - `User`, `Role`
- Enums: `ProjectStatus`, `BuilderType`, `OutreachChannel`, etc.

## Cómo regenerar

(A documentar en Fase 1) — script `pnpm gen:types` que lee Python y produce TS.

Ver [STATE.md](../../STATE.md).
