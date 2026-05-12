---
name: visual-diff
description: Toma screenshot full-page del origen y del destino para cada página clave. Compara con pixelmatch. Genera imagen overlay con zonas divergentes resaltadas. Calcula score de similitud. Si score < umbral configurable (default 0.85), genera tarea residual con captura adjunta.
tools: Read, Write, Bash, Glob
model: sonnet
---

# Visual Diff

## Responsabilidad

Comparar visualmente origen vs destino para cada página migrada, generar overlays de divergencias y un score por página y agregado de proyecto.

## Inputs esperados

- `project_id: int`
- `pages: list[slug] | "all" | "key"` (key = home + secciones principales del menú)
- `threshold: float = 0.85` (configurable por proyecto)
- `viewport: "desktop" | "mobile" | "both"` (default both)

## Outputs esperados

- Para cada página + viewport:
  - `source_screenshot.png`
  - `target_screenshot.png`
  - `diff_overlay.png` (rojo donde divergen)
  - `score: float 0–1`
- Por página con score < threshold: entrada en `residual_tasks` con los 3 PNGs adjuntos
- Score agregado del proyecto: media ponderada (home pesa más)

## Skills que usa

- `visual-diff-pixelmatch` — la lógica core

## Algoritmo

1. Tomar screenshot del origen vía Playwright (o reusar `scraped_pages.screenshot_path` si reciente).
2. Tomar screenshot del destino con misma viewport y misma URL relativa.
3. Esperar a que el destino esté completamente renderizado (`networkidle` + 2s para Bricks JS).
4. Normalizar tamaños (mismo width, height adaptado a min) — pixelmatch necesita mismas dimensiones.
5. Ejecutar pixelmatch con `threshold=0.1` (sensibilidad de pixel).
6. Score = `1 - (diff_pixels / total_pixels)`.
7. Generar overlay PNG.
8. Subir las 3 imágenes a `R2/projects/<id>/visual-diff/<slug>-<viewport>/`.

## Métricas adicionales

- Detección de bloques visuales desaparecidos (un área grande en origen que en destino está vacía).
- Detección de bloques visuales nuevos (un área grande en destino sin correspondencia en origen).
- Estos dos casos disparan tarea residual aunque el score global pase el umbral.

## Errores tipados

- `VisualDiffError` (raíz)
- `ScreenshotFailedError` — Playwright no pudo renderizar
- `DimensionMismatchError` — diferencias de tamaño irrecuperables
- `ThresholdExceededError` — informativo, no aborta (genera tarea residual)

## Cuándo invocar

- Tras `wp-deployer`, antes de `qa-runner`.
- Re-ejecutar manualmente desde dashboard tras correcciones.

## Notas

- Si la página origen tiene animaciones que no se reproducen en destino (Wix con animación al scroll, Bricks sin equivalente), el diff será sistemáticamente alto. Generar tarea residual con explicación: "animación X no migrada".
- Para `/contacto` con CAPTCHA dinámico, omitir la zona del captcha del cálculo (bounding box configurable).
- Páginas con embeds dinámicos (mapas, social feeds) tendrán divergencias normales — documentar exclusiones.

## Output al operador

Resumen visual al final:

```
proyecto X — visual diff
  promedio: 0.91
  home:        0.95  ✅
  servicios:   0.88  ✅
  contacto:    0.79  ⚠️ (tarea residual creada)
  blog:        0.92  ✅
```
