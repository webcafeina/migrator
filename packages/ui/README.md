# packages/ui

Componentes shadcn/ui customizados con la paleta Webcafeína. Compartidos por `apps/dashboard` (y futuras UIs si las hubiera).

## Estado

Vacío en Fase 0. Se materializa en **Fase 8 — Dashboard**.

## Qué contendrá

- Componentes shadcn re-temados (Button, Input, Table, Card, Dialog, Toast, Select, etc.) con la paleta:
  - Background primario `#171009`
  - Background secundario `#2B1A0E`
  - Texto claro `#F2E8D2`
  - Detalle marrón `#5A3519`
  - Acento `#B1F100` (lima — solo CTAs, numeración, iconos, subrayados)
- Componentes específicos del producto:
  - `<ProjectTimeline>` — timeline de fases con estados
  - `<VisualDiffViewer>` — viewer interactivo de overlay
  - `<ChecklistRenderer>` — markdown + PDF preview
  - `<LeadTable>` — tabla densa con filtros
  - `<MetricCard>` — cards de overview
- Tokens Tailwind en `tailwind.config.ts` con paleta + tipografía.
- Storybook (opcional, ver decisión en Fase 8).

Ver [STATE.md](../../STATE.md).
