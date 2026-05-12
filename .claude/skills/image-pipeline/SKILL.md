---
name: image-pipeline
description: Pipeline de optimización de imágenes — descarga, validación, conversión a WebP (Pillow + cwebp), generación de tamaños responsive WordPress (thumbnail/medium/large/full), strip EXIF, hash SHA-256. Maneja formatos exóticos (HEIC, AVIF) y casos de imágenes corruptas.
---

# Skill — Image Pipeline

## Propósito

Procesar todos los assets de imagen de un proyecto: descargar, normalizar, optimizar, generar derivadas, subir al destino (R2 o WP local).

## Contrato

```python
class ImagePipeline:
    def process_one(
        self,
        source_url: str,
        dest_storage: Literal["r2", "wp_local"],
        sizes: list[ImageSize] = WP_DEFAULT_SIZES,
        webp: bool = True,
        strip_exif: bool = True,
    ) -> ImageResult:
        """Devuelve hash, paths, dimensions, attachment_id si wp_local."""

    def process_batch(self, sources: list[str], **kwargs) -> list[ImageResult]:
        """Paraleliza process_one (ThreadPoolExecutor, max 8 workers)."""
```

## Tamaños WordPress por defecto

```python
WP_DEFAULT_SIZES = [
    ImageSize("thumbnail", 150, 150, crop=True),
    ImageSize("medium", 300, 300, crop=False),
    ImageSize("medium_large", 768, 0, crop=False),
    ImageSize("large", 1024, 1024, crop=False),
    ImageSize("full", None, None, crop=False),  # original
]
```

(El cliente puede definir tamaños adicionales como `hero-bg-2400` en el theme; configurable por proyecto.)

## Pipeline

```
URL origen
   ↓
1. HEAD para validar (200, content-type imagen, size razonable)
   ↓
2. GET con headers que no exijan referer estricto
   ↓
3. Detectar formato real con Pillow.Image.verify() — NO confiar en extensión
   ↓
4. HEIC/AVIF/RAW: convertir a PNG intermedio antes de seguir
   ↓
5. Strip EXIF (excepto orientation, que se aplica antes de eliminarlo)
   ↓
6. Hash SHA-256 del binario normalizado (key idempotente)
   ↓
7. Generar derivadas (crop o resize manteniendo aspect ratio)
   ↓
8. Convertir cada derivada a WebP (cwebp binario, Q=82, método=6)
   ↓
9. Mantener original como fallback (formato original o JPEG si era RAW)
   ↓
10. Subir según storage:
    - r2: PUT a R2 con clave `projects/<id>/assets/<hash>/<size>.webp`
    - wp_local: POST /wp-json/wp/v2/media + custom meta sizes via WP-CLI
   ↓
11. Persistir en `assets` (BD)
```

## cwebp binario

- Path por defecto: `/usr/bin/cwebp` (Linux) o `/opt/homebrew/bin/cwebp` (macOS dev).
- Si no instalado: fallback a Pillow `save(format="WEBP", quality=82, method=6)` (más lento pero suficiente).
- Comando: `cwebp -q 82 -m 6 -mt -o out.webp in.png`.

## Strip EXIF

```python
img = Image.open(path)
img = ImageOps.exif_transpose(img)  # aplicar orientación
img.info.pop("exif", None)
img.info.pop("icc_profile", None)  # opcional, ICC pesa
img.save(path)
```

Razones:
- **RGPD**: EXIF puede contener GPS, fecha, dispositivo. Datos personales si la foto es de un evento.
- **Tamaño**: EXIF añade KBs innecesarios.

## Casos límite

| Caso | Manejo |
|---|---|
| Imagen 404 | Marcar asset `status=missing`, generar tarea residual "imagen rota: <slug>" |
| Imagen > 25 MB | Recomprimir agresivamente; si tras compresión > 8 MB, marcar para revisión humana |
| Formato HEIC | Convertir a JPEG con `pyheif` o `pillow-heif` |
| GIF animado | Mantener formato (no convertir a WebP animado en MVP, problemas de compatibilidad) |
| SVG | NO convertir a WebP. Mantener como SVG y sanitizar con `bleach` (eliminar `<script>`, `on*`) |
| Imagen con transparencia | Convertir a WebP lossy con `alpha=true`; o WebP lossless si peso < 200 KB |

## Paralelismo

- `ThreadPoolExecutor(max_workers=8)` para downloads y conversiones.
- Cuidado con memoria: imágenes 4K en RGB ≈ 50 MB en RAM. Limitar pico a 8 × 50 MB = 400 MB.
- Para sitios con >500 imágenes: usar lotes secuenciales de 50 con progreso.

## Reportes

Al finalizar, generar resumen:
```
proyecto X — image pipeline
  procesadas: 247
  saltadas (404): 3
  total origen: 78 MB
  total destino: 22 MB (WebP)
  ahorro: 71%
```

## Dependencias

- Python: `Pillow`, `pillow-heif` (HEIC), `requests`, `bleach` (SVG sanitization)
- Binario: `cwebp` (opcional pero recomendado)

## Tests

- Fixtures de imágenes con cada formato problemático
- Test idempotencia: procesar 2x la misma URL debe dar mismo hash
- Test strip EXIF: verificar que GPS, fecha, dispositivo no están en el output
