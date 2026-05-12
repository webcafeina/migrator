---
name: multilang-handler
description: Detecta versiones idiomáticas en origen (hreflang, paths /es/ /en/, subdominios), correlaciona páginas equivalentes entre idiomas, prepara el mapa de traducciones para wpml-configurator. Se ejecuta tras content-extractor y antes de bricks-transpiler.
tools: Read, Write, Bash, Grep
model: sonnet
---

# Multilang Handler

## Responsabilidad

Si la web origen es multilingüe, identificar qué idiomas tiene y correlacionar cada página origen con sus equivalentes en otros idiomas.

## Inputs esperados

- `project_id: int`

## Outputs esperados

- Actualización de `project.langs[]` con códigos ISO 639-1 detectados (`["es", "en", "fr"]`)
- Actualización de `project.primary_lang` (basado en `<html lang>` de la home o config cliente)
- Para cada `scraped_pages.url`, marcado de su lang
- Tabla intermedia `page_translations(trid, lang, page_id)` lista para WPML

## Skills que usa

- Lectura de `scraped_pages` (no scraping nuevo)

## Estrategia de detección

### 1. Hreflang
- Parsear `<link rel="alternate" hreflang>` en cada página.
- Si presente, es la fuente de verdad. Construir mapa directo.

### 2. Patrón de path
- `/es/`, `/en/`, `/fr/` (prefijo) → directorio por idioma
- `/contacto`, `/contact`, `/kontakt` → mismo trid si título/contenido coinciden semánticamente (heurística: misma posición en menú + clase navigation match)

### 3. Subdominio
- `es.dominio.com`, `en.dominio.com` → cada uno es un idioma

### 4. Cookie / IP redirect
- Si origen redirige por IP, NO confiar. Crawl con header `Accept-Language` específico por idioma.

## Correlación entre traducciones

Una página `/es/sobre-nosotros` y `/en/about-us` se consideran equivalentes (mismo `trid`) si:

1. Coinciden en posición del menú principal/footer, O
2. Tienen el mismo `og:url canonical` translation declarado, O
3. La similitud semántica de su contenido principal supera 0.7 (vector embedding cosine).

## Errores tipados

- `MultilangHandlerError` (raíz)
- `LangDetectionAmbiguityError` — múltiples señales conflictivas
- `TranslationCorrelationLowError` — equivalencia < umbral; se marca para revisión humana

## Cuándo invocar

- Tras `content-extractor`, antes de `bricks-transpiler`.
- Re-ejecutar si el cliente añade un idioma a posteriori.

## Casos límite

- Web origen es bilingüe pero solo tradujo 60% de las páginas → marcar las páginas sin traducción como `trid` único (no compartido) y registrar tarea residual.
- Web origen tiene un idioma "informal" (variante regional, p. ej. `es-AR`) → mapear a `es` por defecto, registrar en notas del proyecto.

## Notas

- Si `project.is_multilang=true` se fija manualmente por el operador antes de crawl, este subagente sigue validando coherencia.
- Si detecta multilang pero `project.is_multilang=false`, pausar y pedir confirmación al operador.
