# apps/dashboard

Dashboard del Webcafeína Migrator. **Next.js 15 (App Router) + React 19 + TypeScript 5 + Tailwind CSS + shadcn/ui**.

## Estado

Materializado en **Fase 8**. Cobertura completa de las 10 páginas del prompt maestro + auth middleware + paleta Webcafeína estricta + JetBrains Mono en toda la UI.

## Paleta y tipografía

| Token | Hex | Uso |
|---|---|---|
| `bg-wcm-primary` | `#171009` | Background base |
| `bg-wcm-secondary` | `#2B1A0E` | Cards, inputs, sidebar items activos |
| `text-wcm-text` | `#F2E8D2` | Texto principal |
| `border-wcm-detail` | `#5A3519` | Bordes, separadores, metadatos |
| `text-wcm-accent` | `#B1F100` | Lima — CTAs, numeración, datos clave, links |

**Tipografía**: **JetBrains Mono** en toda la UI (no solo código) por preferencia del operador. Cargada via `next/font/google` con weights 400/500/600/700. Da look denso, técnico, terminal-friendly — coherente con la naturaleza de la herramienta.

Logo SVG pendiente; mientras tanto **wordmark de texto en lima** ("WEBCAFEÍNA" + icono `Activity` de lucide).

## Páginas

Todas detrás de auth middleware (cookie `wcm_session`):

| Ruta | Contenido |
|---|---|
| `/login` | Form email+password → `/api/v1/auth/login`, set cookie http-only |
| `/` | Overview: métricas + proyectos activos + errores recientes |
| `/leads` | Tabla densa con filtros (sector, region, builder, status, min-score) |
| `/leads/[id]` | Detalle: identificación + fingerprint + contacto + evidencia JSON; botón re-fingerprint |
| `/projects` | Listado de proyectos con status |
| `/projects/[id]` | Detalle + timeline de fases + start/resume/cancel |
| `/projects/[id]/checklist` | Tareas residuales agrupadas por categoría |
| `/projects/[id]/diff` | Placeholder honesto: `packages/visual-diff/` ya existe, falta conectar a UI |
| `/campaigns` | Listado de campañas + LaunchForm + polling de runs activos |
| `/errors` | Log de errores con KPIs por severity + filtros chips + 5 colores |
| `/residual-tasks` | Tabla con `Done` action que sincroniza con ClickUp |
| `/settings` | Ajustes: usuario actual + estado del sistema (/system/info) + runbook operativo |

## Stack

- **Next.js 15** con App Router + Server Components por defecto
- **React 19**
- **TypeScript 5** estricto (`noUncheckedIndexedAccess`)
- **Tailwind CSS 3.4** con paleta WCM extendida en `tailwind.config.ts`
- **shadcn/ui** componentes customizados (Button, Input, Label, Card, Table, Badge, Skeleton)
- **lucide-react** iconos
- **sonner** para toasts
- **Vitest** + **happy-dom** para tests unit
- **next/font/google** para JetBrains Mono

## Setup local

```bash
# Desde la raíz del repo:
pnpm install          # instala TODO el workspace (incluye dashboard deps)

# Generar tipos TS si has tocado los Pydantic schemas:
pnpm gen:types

# Arrancar dev (puerto 3000):
cd apps/dashboard
pnpm dev

# El dashboard llama al API con rewrites configurados en next.config.mjs.
# Asegúrate de que el API esté arrancado:
#   uvicorn wcm_api.main:app --reload --port 8000
# Por defecto API_URL=http://localhost:8000.
```

## Build de producción

```bash
cd apps/dashboard
pnpm build                  # produce .next/standalone/server.js
pnpm start                  # node .next/standalone/server.js (puerto 3000)
```

El build es `output: "standalone"` para que systemd lo arranque con un único `node` sin necesitar `next` instalado en el servidor. Ver `infra/systemd/webcafeina-dashboard.service` (Fase 12).

## Autenticación

Cookie http-only `wcm_session` emitida por `/api/v1/auth/login`. En producción API + dashboard comparten dominio (`migrator.webcafeina.com`, API bajo `/api`) — la cookie viaja automáticamente.

En dev, Next.js rewrite reenvía `/api/v1/*` al API local. Esto evita CORS y mantiene la cookie operativa.

Middleware `src/middleware.ts` redirige a `/login?from=<path>` si no hay cookie. Excepciones: `/login`, `/api/*`, `/opt-out`, `/_next/*`, `/favicon.ico`.

## Tests

```bash
cd apps/dashboard
pnpm test                   # vitest run (CI)
pnpm test:watch             # modo desarrollo
```

15 tests cubren: `cn()`, `formatDate()`, `truncate()`, `ApiError` shape, `statusVariant()` mapping para todos los estados del dominio. Tests E2E con Playwright en Fase 13.

## Estructura

```
src/
├── app/
│   ├── layout.tsx              # JetBrains Mono + Toaster + dark
│   ├── globals.css             # Tailwind + paleta + scrollbar
│   ├── login/page.tsx          # form (sin layout app)
│   └── (app)/                  # route group con sidebar+header
│       ├── layout.tsx
│       ├── page.tsx            # overview
│       ├── leads/
│       │   ├── page.tsx
│       │   └── [id]/
│       │       ├── page.tsx
│       │       └── refingerprint-button.tsx
│       ├── projects/
│       │   ├── page.tsx
│       │   └── [id]/
│       │       ├── page.tsx
│       │       ├── actions.tsx
│       │       ├── checklist/page.tsx
│       │       └── diff/page.tsx
│       ├── campaigns/{page,launch-form}.tsx
│       ├── errors/page.tsx
│       ├── residual-tasks/{page,mark-done-button}.tsx
│       └── settings/page.tsx
├── components/
│   ├── ui/                     # shadcn customizados con paleta
│   │   ├── button.tsx
│   │   ├── input.tsx
│   │   ├── label.tsx
│   │   ├── card.tsx
│   │   ├── table.tsx
│   │   ├── badge.tsx           # incluye statusVariant() del dominio
│   │   └── skeleton.tsx
│   └── layout/
│       ├── sidebar.tsx         # nav con icons lucide
│       ├── header.tsx          # /auth/me + LogoutButton
│       └── logout-button.tsx
├── lib/
│   ├── api.ts                  # fetcher con error envelope + cookie
│   └── utils.ts                # cn, formatDate, truncate
├── types/api.ts                # re-export desde @webcafeina/shared-types
└── middleware.ts               # auth redirect
```

## ADRs relacionados

- ADR-022 — Dashboard Next.js 15 App Router con paleta Webcafeína estricta + JetBrains Mono en toda la UI por preferencia del operador (alternativa a sans-serif estándar)
