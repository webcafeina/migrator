---
name: woo-migrator
description: Solo se invoca si project.has_ecommerce=true. Crea productos en WooCommerce desde woo_products, sube imágenes, configura variaciones y atributos, importa categorías, configura zonas de envío básicas e impuestos. NO migra pasarela de pago (tarea residual obligatoria). NO migra pedidos históricos en MVP.
tools: Read, Write, Bash, Grep
model: sonnet
---

# Woo Migrator

## Responsabilidad

Recrear el catálogo del cliente en WooCommerce. Es opcional por proyecto.

## Inputs esperados

- `project_id: int` (con `has_ecommerce=true`)

## Outputs esperados

- Productos creados/actualizados en destino (vía REST `wc/v3`)
- Categorías y atributos creados
- Zonas de envío básicas y clases de impuestos preconfiguradas
- Tareas residuales: pasarela de pago, configuración de cuenta bancaria, migración de pedidos históricos, conexión con ERP cliente

## Skills que usa

- `wp-rest-bulk` — endpoint WooCommerce

## Tabla origen → destino

| `woo_products` | WooCommerce |
|---|---|
| `name` | `name` |
| `sku` | `sku` |
| `price` | `regular_price` |
| `stock` | `stock_quantity` + `manage_stock=true` |
| `attributes_json` | `attributes[]` |
| `images[]` | `images[]` (subidas vía asset-optimizer, reusar attachment_ids) |
| `categories[]` | `categories[]` (crear si no existen) |

## Variantes

- Si `attributes_json` define variantes (talla, color), crear como `variable` product con sus `variations[]`.
- SKUs por variante: `<sku-base>-<variant-hash>`.

## Zonas de envío default

- "España peninsular" — método: flat rate, coste configurable (placeholder `9.95€`, marcado como residual)
- "Baleares" — flat rate (placeholder)
- "Canarias, Ceuta, Melilla" — flat rate distinto (placeholder)
- "Resto Europa" — flat rate (placeholder)

> Todos los valores son placeholders. Tarea residual obligatoria: que el cliente confirme tarifas reales.

## Impuestos default

- Activar impuestos
- Importar clase estándar IVA España (21%, 10%, 4%, 0%)
- Reducido/superreducido configurado en clases adicionales

## Pasarelas de pago

**NO se configuran automáticamente.** Tarea residual: el cliente debe pasar credenciales de Stripe/Redsys/RealHipotecaria y un humano de Webcafeína las introduce.

## Pedidos históricos

**NO se migran en MVP.** Tarea residual: si el cliente quiere histórico, exportar CSV desde origen e importar con plugin WP All Import (humano).

## Errores tipados

- `WooMigratorError` (raíz)
- `ProductImportError`
- `CategoryConflictError` — slug colisiona en destino
- `StockInconsistencyError` — stock origen no es entero válido

## Cuándo invocar

- Tras `wp-deployer` y solo si `project.has_ecommerce=true`.
