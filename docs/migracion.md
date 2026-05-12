# Migración — Webcafeína Migrator

> Documento stub. Se completa entre **Fases 2–8** según se materialicen los subagentes.

---

## Objetivo del módulo

Convertir webs Wix / Hostinger AI Builder / Webflow a WordPress + Bricks Builder, preservando:

- Estructura de páginas
- Contenido (texto, imágenes, vídeos, formularios)
- SEO (meta tags, JSON-LD, sitemap, hreflang, redirects 301)
- Assets (con optimización a WebP + tamaños responsive WP)
- Multilang (cuando aplique, vía WPML)
- Productos WooCommerce (cuando aplique)

Output paralelo: **checklist humano** con todo lo que no se puede automatizar.

## Flujo (resumen)

Ver [docs/arquitectura.md §4](./arquitectura.md#4-flujo-de-migración-detallado).

```
new project → fingerprinter → scraper-origin → content-extractor →
  (seo-preserver | asset-optimizer | multilang-handler) →
    bricks-transpiler → wp-deployer →
      (woo | wpml | forms) →
        visual-diff → qa-runner →
          checklist-generator → clickup-syncer → notificación
```

## Builders origen soportados

- **Wix** (incluye Editor X, ADI, Studio)
- **Hostinger AI Builder** (incluye legado Zyro)
- **Webflow** (incluye Webflow Ecommerce y CMS Collections)

## Builder destino

- **WordPress + Bricks Builder** (exclusivo MVP). Ver [ADR-002](./decisiones.md#adr-002).

## Plugins instalados en destino

Default siempre:
- Bricks Builder (tema)
- Yoast SEO
- Redirection
- Gravity Forms
- WP Rocket (o cache equivalente)
- Google Site Kit
- Advanced Custom Fields (free)

Condicional:
- WPML (si `is_multilang`)
- WooCommerce (si `has_ecommerce`)

## Criterios de éxito de una migración

Ver [CLAUDE.md §13](../CLAUDE.md#13-criterios-de-éxito-del-mvp).

Resumen:
- Visual diff ≥ 0.85 home + ≥ 80% páginas internas.
- QA Runner pasa sin críticos.
- Checklist residual ejecutable en < 4h para web corporativa de 10 páginas.

## Tareas residuales típicas (no automatizables)

- Pasarela de pago WooCommerce
- DNS apuntando al destino
- Email transaccional SMTP
- Configuración Google Analytics / Search Console
- Animaciones IX2 Webflow no migrables
- Vídeos a rehospedar
- Bloques marcados `unknown` por content-extractor

Cada una se persiste en `residual_tasks` y aparece en el checklist final.

---

## Por documentar a medida que avanzamos

- Playbook por builder (Wix, Hostinger, Webflow) con casos límite reales (Fase 3)
- Mapping detallado bloque → elemento Bricks con screenshots antes/después (Fase 2)
- Procedimiento de rollback (si el cliente decide no migrar tras ver staging) (Fase 8+)
- KPIs por migración (tiempo total, score visual, residuales por hora) (Fase 11)
