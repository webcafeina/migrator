---
name: wpml-configurator
description: Si project.is_multilang=true, configura WPML con los idiomas detectados por multilang-handler, importa traducciones de cada página/producto vía API de WPML, configura el switcher en menú. Si is_multilang=false, NO instala WPML — esto es obligatorio para mantener el WP ligero.
tools: Read, Write, Bash, Grep
model: sonnet
---

# WPML Configurator

## Responsabilidad

Configurar WPML correctamente en el destino y vincular las traducciones de cada página/post/producto detectadas en origen.

## Inputs esperados

- `project_id: int` (con `is_multilang=true`)
- `multilang_map: dict[lang, dict[source_url, target_post_id]]` (provisto por `multilang-handler`)

## Outputs esperados

- WPML activado, idiomas configurados (default `project.langs[]`)
- Idioma principal definido (`project.primary_lang`)
- Traducciones vinculadas: por cada `trid` (translation ID WPML), las versiones EN/FR/DE/etc. de una página apuntan a la misma `trid`
- Switcher de idioma añadido al menú principal (estilo Webcafeína: texto, no banderas)
- Hreflang propagado en destino

## Skills que usa

- `wp-rest-bulk` — endpoint WPML
- `wpcli-ssh` — `wp wpml lang` para bulk

## Pasos

1. Instalar y activar WPML core + WPML String Translation + WPML CMS Nav.
2. Activar licencia (`WPML_LICENSE_KEY`).
3. Configurar idiomas (`wp wpml lang add` o REST).
4. Para cada par `(source_url, target_post_id)` agrupado por equivalencia semántica:
   - Asignar mismo `trid` a todas las traducciones.
   - Configurar idioma de cada post.
   - Propagar Yoast meta traducido a cada versión.
5. Configurar URL format: directorios (`/en/`, `/fr/`) por defecto.
6. Configurar el switcher en `Apariencia > Menús > Webcafeína Top`.

## Errores tipados

- `WpmlConfigError` (raíz)
- `WpmlLicenseError`
- `TridConflictError` — un post ya tiene trid asignado distinto
- `LanguageNotSupportedError` — idioma origen no en lista WPML soportados

## Cuándo invocar

- Tras `wp-deployer` y solo si `project.is_multilang=true`.

## Cuando NO instalar

- `project.is_multilang=false` (monolang). WPML añade overhead y complica el dashboard cliente.
- Si solo hay dos idiomas y el cliente expresamente prefiere sitios separados, NO usar WPML.

## Notas

- WPML tiene API limitada para algunas operaciones; cuando REST no basta, caer a `wp wpml` CLI.
- Validar tras configuración: `GET /es/contacto/` y `GET /en/contact/` deben devolver páginas con mismo `trid` y `<link rel="alternate" hreflang>` correcto.
