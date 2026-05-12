---
name: visual-diff-pixelmatch
description: Comparación visual de screenshots con pixelmatch (algoritmo Node port a Python o invocación nativa). Threshold configurable, output overlay PNG con divergencias resaltadas, score numérico y bounding boxes de las zonas críticas.
---

# Skill — Visual Diff Pixelmatch

## Propósito

Algoritmo core para el subagente `visual-diff`. Comparar dos screenshots y producir score + overlay.

## Implementación

Dos opciones, fallback automático:

1. **Preferida**: invocar binario Node con `pixelmatch` y `pngjs` (rápido, bien probado).
2. **Fallback**: implementación pura Python con Pillow + numpy (más lenta pero portable).

Elección automática: si `node` está en PATH y `pixelmatch` instalado globalmente o en `apps/worker/node_modules`, usar opción 1.

## Contrato

```python
class VisualDiff:
    def compare(
        self,
        source_path: Path,
        target_path: Path,
        threshold: float = 0.1,         # sensibilidad pixel (0=estricto, 1=ignorar)
        anti_aliasing: bool = True,
        ignore_regions: list[BoundingBox] | None = None,
        diff_color: tuple[int,int,int] = (255, 0, 0),
        alpha: float = 0.5,
    ) -> DiffResult:
        ...
```

`DiffResult`:
```python
@dataclass
class DiffResult:
    score: float                            # 0..1; 1 = idénticos
    diff_image_path: Path                   # overlay PNG
    diff_pixels: int
    total_pixels: int
    bounding_boxes: list[BoundingBox]       # áreas con divergencias significativas
    width: int
    height: int
```

## Normalización previa

Antes de comparar:

1. Si dimensiones difieren:
   - Si difieren < 5%: redimensionar la grande al tamaño de la pequeña (preservando aspect ratio si > 5%, registrar warning).
   - Si difieren > 5%: fallar con `DimensionMismatchError` y avisar al operador (probable problema de viewport).
2. Si formato difiere (PNG vs JPEG): convertir todo a PNG.
3. Si DPI difiere: reescalar a DPI mínimo común.

## Ignore regions

Áreas a excluir del cálculo (rellenadas con mismo color en ambas imágenes antes del diff):

- Captcha widget en formularios
- Mapa Google Maps embebido
- Social feeds dinámicos
- Carruseles con estado de slide indeterminado
- Fecha/hora del footer

Se configuran por proyecto en `project.visual_diff_ignore`.

## Bounding boxes

Tras pixelmatch:
1. Convertir diff image a binary mask (pixel red ≠ pixel transparent).
2. Encontrar componentes conexos (connected components, `scipy.ndimage.label` o equivalente).
3. Filtrar componentes < 50 px² (ruido aliasing).
4. Devolver bounding boxes de los significativos.

Esto permite que `checklist-generator` recorte el origen y destino solo de la zona divergente, no el screenshot entero (más útil para el humano).

## Output overlay

Imagen PNG con:
- Background: target screenshot (con alpha 0.7)
- Overlay: pixels divergentes en rojo (255, 0, 0, alpha=0.5)
- Bordes de cada bounding box en amarillo
- Texto pequeño superior izquierda: "score: 0.87"

## Tests

- Fixtures: 2 imágenes idénticas → score 1.0
- Fixtures: 2 imágenes con un bloque cambiado → bounding box correcta
- Test dimensiones distintas: comportamiento esperado
- Test ignore_regions: aplicación correcta

## Dependencias

- **Opción 1**: Node + `pixelmatch` (npm) + `pngjs`
- **Opción 2**: Pillow, numpy, scipy
