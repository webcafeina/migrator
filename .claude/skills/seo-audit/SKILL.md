---
name: seo-audit
description: Extracción y auditoría SEO completa de la web origen. Preserva meta tags, OG, Twitter Cards, JSON-LD, sitemap, robots.txt, hreflang. Adicionalmente detecta oportunidades de mejora (titles cortos, descriptions vacías, H1 múltiples, alts vacíos, etc.) y las propone como sugerencias revisables.
---

# Skill — SEO Audit

## Propósito

Auditar el SEO de la web origen, preservarlo en destino y proponer mejoras concretas que el operador puede aceptar o rechazar.

## Contrato

```python
class SeoAuditor:
    def audit_page(self, html: str, url: str) -> PageSeoAudit:
        """Extrae + audita una sola página."""

    def audit_site(self, project_id: int) -> SiteSeoAudit:
        """Auditoría agregada del proyecto entero."""

    def preserve_to_yoast(self, project_id: int) -> dict[int, YoastMeta]:
        """Mapping page_id -> YoastMeta listo para inyectar tras wp-deployer."""

    def suggest_improvements(self, audit: SiteSeoAudit) -> list[Suggestion]:
        """Listado de mejoras priorizadas."""
```

## Qué se extrae por página

```python
@dataclass
class PageSeoAudit:
    url: str
    title: str | None
    description: str | None
    og: dict[str, str]            # og:title, og:description, og:image, og:type, og:url
    twitter: dict[str, str]       # twitter:card, twitter:title, twitter:description, twitter:image
    canonical: str | None
    hreflang: list[Hreflang]      # [(lang, url), ...]
    robots: str | None             # noindex, nofollow, etc.
    json_ld: list[dict]            # structured data blocks
    h1: list[str]                  # debería ser 1, marcar si > 1 o 0
    headings_outline: list[Heading]  # h1...h6 en orden
    images_without_alt: list[str]
    internal_links: list[str]
    external_links: list[str]
    word_count: int
    content_score: float | None    # heurística (legibilidad básica)
```

## Detección de oportunidades

| Hallazgo | Umbral / regla | Severidad |
|---|---|---|
| `<title>` vacío | length == 0 | crítica |
| `<title>` > 60 chars | length > 60 | aviso |
| `<title>` < 30 chars | length < 30 | aviso |
| meta description vacía | missing | crítica |
| meta description > 160 chars | length > 160 | aviso |
| Sin canonical | missing | aviso |
| og:image faltante | missing o 404 | aviso |
| og:image < 1200×630 | dim check | info |
| H1 múltiples | count > 1 | aviso |
| Sin H1 | count == 0 | crítica |
| Heading skip levels (h2 → h4 sin h3) | outline analysis | info |
| Alts vacíos | count > 0 | aviso |
| Enlaces internos 404 | http status | crítica |
| Falta JSON-LD Organization en home | missing | aviso |
| Sitemap incompleto (faltan páginas del crawl) | diff | aviso |
| robots.txt sin Sitemap declarado | missing line | info |

## Output: plan de mejoras

`docs/seo-improvements-<project_id>.md`:

```markdown
# Mejoras SEO sugeridas — Proyecto N

## Resumen
- 3 hallazgos críticos
- 12 avisos
- 7 informativos

## Críticos

### /servicios — meta description vacía
**Acción**: Generar con plantilla "Servicios profesionales de [sector] en [región]..."
**Aceptar / Rechazar / Editar**

### /contacto — sin H1
**Acción**: Añadir `<h1>Contacto</h1>` antes del formulario.
**Aceptar / Rechazar / Editar**
```

(En dashboard, cada sugerencia es interactiva. Las aceptadas se aplican al destino vía `wp-rest-bulk`.)

## Preservación a Yoast SEO

Mapping:

| Origen | Yoast meta |
|---|---|
| `<title>` | `_yoast_wpseo_title` |
| meta description | `_yoast_wpseo_metadesc` |
| canonical | `_yoast_wpseo_canonical` |
| og:title | `_yoast_wpseo_opengraph-title` |
| og:description | `_yoast_wpseo_opengraph-description` |
| og:image | `_yoast_wpseo_opengraph-image` + `_yoast_wpseo_opengraph-image-id` |
| robots noindex | `_yoast_wpseo_meta-robots-noindex` (1/0) |
| JSON-LD Organization | Yoast Schema graph (vía settings globales en `yoast.knowledge_graph`) |

## Hreflang y multilang

- Si `project.is_multilang=true`, WPML genera hreflang automáticamente; no inyectar manualmente.
- Si `project.is_multilang=false` pero origen tenía hreflang: ignorar (sería ruido).

## Tests

- Fixtures HTML con cada tipo de hallazgo
- Validación de YoastMeta mapping
- Test de idempotencia: ejecutar 2x sobre misma página → misma sugerencia

## Dependencias

- `beautifulsoup4`, `lxml`, `extruct` (JSON-LD parsing), `requests`
