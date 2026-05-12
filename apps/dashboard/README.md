# apps/dashboard

Dashboard web del Webcafeína Migrator basado en **Next.js 15 (App Router)** + TypeScript 5 + shadcn/ui + Tailwind CSS.

## Estado

Vacío en Fase 0. Se materializa en **Fase 8 — Dashboard**.

## Qué contendrá

Páginas (App Router):

- `/login` — auth
- `/` — overview (métricas, errores, proyectos activos)
- `/leads` — listado filtrable, scoring, "convertir a proyecto"
- `/leads/[id]` — detalle, secuencias outreach
- `/projects` — listado de migraciones
- `/projects/[id]` — vista completa con timeline de fases
- `/projects/[id]/checklist` — checklist humano renderizado
- `/projects/[id]/diff` — diff visual interactivo
- `/campaigns` — campañas de prospección
- `/errors` — panel de errores agrupados
- `/settings` — config global, credenciales (cifradas), usuarios

## Estilo

- **Dark mode por defecto**.
- Paleta Webcafeína estricta (`#171009` background, `#B1F100` solo para CTAs/numeración/acentos).
- Tablas densas (Nacho prefiere ver mucho dato por scroll).
- Sin emojis en UI.

## Build de producción

Modo standalone para servir desde systemd (`node .next/standalone/server.js`).

Ver [STATE.md](../../STATE.md).
