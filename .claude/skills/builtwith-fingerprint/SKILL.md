---
name: builtwith-fingerprint
description: Patrones locales tipo Wappalyzer para detectar stack tecnológico (builder, CMS, frameworks, analytics, CDN). Sin depender de la API externa de Wappalyzer/BuiltWith — todos los patrones se mantienen localmente con tests.
---

# Skill — BuiltWith Fingerprint

## Propósito

Detectar tecnologías que usa una web a partir de señales en headers, HTML, JS y recursos cargados. **Sin llamadas a APIs externas** (no Wappalyzer.com, no BuiltWith.com): patrones locales mantenibles.

## Contrato

```python
class BuiltWithFingerprinter:
    def fingerprint(self, html: str, headers: dict, url: str, computed_js: dict | None = None) -> list[TechMatch]:
        """Devuelve tecnologías detectadas con confianza."""
```

`TechMatch`:
```python
@dataclass
class TechMatch:
    name: str               # "Wix", "Webflow", "Hostinger AI", "WordPress", "Squarespace", ...
    category: str           # "builder", "cms", "analytics", "cdn", "ecommerce"
    confidence: float       # 0.0 - 1.0
    evidence: list[str]     # señales que activaron la detección
```

## Patrones

Persistidos en `patterns.yml` (mantenible sin tocar código):

```yaml
- name: Wix
  category: builder
  signals:
    - {type: header, key: x-wix-request-id, weight: 0.4}
    - {type: header, key: server, value: "Pepyaka", weight: 0.3}
    - {type: html, regex: 'parastorage\.com', weight: 0.3}
    - {type: html, regex: 'wixstatic\.com', weight: 0.3}
    - {type: js_global, key: wixBiSession, weight: 0.4}

- name: Hostinger AI Builder
  category: builder
  signals:
    - {type: header, key: x-hosted-by, value: "hostinger", weight: 0.3}
    - {type: html, regex: 'data-hostai-loaded', weight: 0.5}
    - {type: html, regex: 'assets\.hostinger\.com', weight: 0.3}
    - {type: js_global, key: HOSTAI, weight: 0.4}

- name: Webflow
  category: builder
  signals:
    - {type: html, regex: 'website-files\.com', weight: 0.4}
    - {type: html, regex: 'data-w-id', weight: 0.3}
    - {type: js_global, key: Webflow, weight: 0.5}
    - {type: header, key: server, value: "Webflow", weight: 0.4}

- name: WordPress
  category: cms
  signals:
    - {type: html, regex: '/wp-content/', weight: 0.4}
    - {type: html, regex: '/wp-includes/', weight: 0.3}
    - {type: html, regex: 'meta\s+name="generator"\s+content="WordPress', weight: 0.5}
    - {type: header, key: x-pingback, weight: 0.3}

- name: Squarespace
  category: builder
  signals:
    - {type: html, regex: 'static1\.squarespace\.com', weight: 0.5}
    - {type: js_global, key: Static, weight: 0.2}  # contexto-dependiente

- name: Shopify
  category: ecommerce
  signals:
    - {type: header, key: x-shopify-stage, weight: 0.5}
    - {type: html, regex: 'cdn\.shopify\.com', weight: 0.4}
    - {type: js_global, key: Shopify, weight: 0.4}
```

## Suma de confianza

```python
def aggregate(signals_matched: list[Signal]) -> float:
    # Suma directa con cap a 1.0
    total = sum(s.weight for s in signals_matched)
    return min(total, 1.0)
```

## Resolución de conflictos

Si una web matchea WordPress + Wix (raro pero pasa con sitios migrados a medias):
- Quedarse con la de mayor confianza
- Si ambas > 0.6, devolver ambas con `notes="ambiguous"` y dejar que `lsr-fingerprint` desempate

## Mantenimiento de patterns.yml

- Cada cambio significativo debe acompañarse de tests fixture
- Versión semver del fichero (`patterns_version: 1.0.0`) para tracking
- Patterns retirados pasan a `patterns-deprecated.yml` para no romper proyectos viejos

## Tests

- Fixtures por tecnología (HTML + headers minimalistas que disparen detección)
- Tests anti-falso-positivo: web genérica WordPress no debe matchear Wix

## Dependencias

- `pyyaml` para cargar patterns.yml
- `regex` stdlib

## Cuándo invocar

- Desde `fingerprinter` agente (nivel 2/3 de la cascada).
- En recrawl periódico para detectar webs que han migrado (estado tracking).
