# Performance baseline — Webcafeína Migrator

Objetivos de performance del MVP y cómo medirlos post-deploy.

## 1. Objetivos (SLO MVP)

### API

| Métrica | Target | Crítico |
|---|---|---|
| `/health` p95 latency | < 10 ms | > 50 ms |
| `/api/v1/leads` (listado 50 leads) p95 | < 100 ms | > 500 ms |
| `/api/v1/projects/{id}` p95 | < 150 ms | > 1 s |
| `/api/v1/auth/login` p95 | < 250 ms (argon2 hash es lento por diseño) | > 1 s |
| Throughput sostenido | 50 RPS sin degradación | < 20 RPS |

### Worker

| Métrica | Target | Crítico |
|---|---|---|
| Migración 10-páginas Wix → WP | < 90 min (objetivo MVP §13 CLAUDE.md) | > 180 min |
| Campaña prospección 30 leads | < 10 min | > 30 min |
| `transpile_bricks` por página | < 5 s | > 30 s |
| `optimize_assets` 50 imágenes | < 2 min | > 10 min |
| `retention_sweep` (10k leads) | < 30 s | > 5 min |

### Dashboard

| Métrica | Target | Crítico |
|---|---|---|
| Lighthouse Performance | > 85 | < 70 |
| First Contentful Paint (FCP) | < 1.2 s | > 3 s |
| Largest Contentful Paint (LCP) | < 2.5 s | > 4 s |
| Cumulative Layout Shift (CLS) | < 0.1 | > 0.25 |

---

## 2. Cómo medir

### API con `wrk` (sustituto de `k6`, sin instalación pesada)

Tras el primer deploy, desde una máquina cliente:

```bash
# Healthcheck (sin auth)
wrk -t4 -c50 -d30s https://api.migrator.webcafeina.com/health

# Endpoint autenticado (suministrar cookie wcm_session)
wrk -t4 -c50 -d30s -H "Cookie: wcm_session=<token>" \
    https://api.migrator.webcafeina.com/api/v1/leads
```

Lectura: el ouput muestra Requests/sec + Latency p50/p95/p99.

### Worker con tracing real

Tras lanzar una migración o campaña real, mirar:

```bash
# Tiempo total proyecto
psql -c "
  SELECT id, started_at, completed_at,
         EXTRACT(EPOCH FROM (completed_at - started_at)) AS seconds
  FROM projects
  WHERE status = 'completed'
  ORDER BY completed_at DESC LIMIT 10;
"

# Tiempo por fase
psql -c "
  SELECT phase_name,
         ROUND(AVG(EXTRACT(EPOCH FROM (completed_at - started_at))), 1) AS avg_sec,
         COUNT(*) AS runs
  FROM project_phases
  WHERE status = 'completed' AND started_at > now() - interval '30 days'
  GROUP BY phase_name
  ORDER BY 2 DESC;
"
```

O directamente desde Prometheus:

```promql
# p95 latencia por endpoint
histogram_quantile(0.95, sum by (path, le) (rate(wcm_http_request_duration_seconds_bucket[5m])))

# Throughput total
sum(rate(wcm_http_requests_total[1m]))

# Tasa de fallos Celery por task
rate(wcm_celery_tasks_total{status="failure"}[5m]) / rate(wcm_celery_tasks_total[5m])
```

### Dashboard con Lighthouse CI

```bash
# Una vez instalado lighthouse-cli en el runner
pnpm dlx @lhci/cli@0.13 collect --url=https://migrator.webcafeina.com
```

Pendiente integrar en GitHub Actions (WCM-018).

---

## 3. Plan de tuning si no se cumplen targets

### API lenta (`/health` > 50 ms)

1. Verificar uvicorn `--workers` ≥ 2.
2. Comprobar carga del nodo: `htop`, `free -h`.
3. Si `db` query (`/ready` p95 > 100 ms): ver pg_stat_statements para top slow queries; añadir índices.

### Worker lento (`transpile_bricks` > 30 s/página)

1. Comprobar uso de Pillow: `optimize_assets` puede saturar CPU si el batch es grande. Reducir `WCM_WORKER_CONCURRENCY`.
2. Bricks transpiler trabaja en memoria — debería ser sub-segundo. Si tarda más, perfilar con cProfile.

### Migración total > 90 min

1. Identificar fase culpable con la query SQL de arriba.
2. Si es `scrape_origin`: el site origen es lento o el proxy está reciclando IPs. Aumentar timeout o cambiar tier proxy.
3. Si es `deploy_wp`: el WP destino tiene rate limit REST. Cambiar a WP-CLI bulk (más rápido).

### Dashboard FCP > 3 s

1. Verificar que el build standalone se sirve (no `next dev`).
2. Verificar headers de cache estáticos en Nginx (`/_next/static` cache 1 año, immutable).
3. Verificar que Cloudflare CDN está delante (si DNS apunta directo al servidor).

---

## 4. Pendientes

| ID | Descripción |
|---|---|
| WCM-018 | Integrar Lighthouse CI en GitHub Actions workflow |
| WCM-019 | Configurar Grafana dashboard con paneles para SLOs |
| WCM-020 | Alertas en Grafana cuando p95 > critical durante 5 min |
