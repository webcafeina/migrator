# h2b.skill v3.2.0 vendorado

Corpus dorado de referencia para los **shapes JSON de Bricks Builder** que el transpilador `wcm_bricks_transpiler` genera.

## Origen

- **Upstream**: https://github.com/iamfilipp/html2bricks (rama `main`, snapshot 2026-05-22).
- **Versión vendorada**: v3.2.0.
- **Target Bricks**: 2.1.4.
- **Licencia**: MIT (ver `LICENSE`).

## Contenido

```
h2b/
├── SKILL.md                                ← guía top-level (flat structure + IDs)
└── references/
    ├── BRICKS-ELEMENTS.md                  ← 31 elementos con shapes JSON verbatim
    ├── BRICKS-NATIVE-PROPERTIES.md         ← _typography, _padding, _background, etc.
    ├── PSEUDO-SELECTORS.md                 ← :hover, :focus, :nth-child
    ├── INTERACTIONS.md                     ← _interactions array
    └── JAVASCRIPT-HANDLING.md              ← embeds JS
```

## Cómo usarlo

1. **Cuando implementes un mapper Bricks** (slider, tabs, accordion, repeater, nav-menu, image-gallery, etc.), consulta primero `references/BRICKS-ELEMENTS.md` para el shape exacto.
2. **Cuando dudes de una propiedad CSS** (`_padding`, `_background`, `_border`...), consulta `references/BRICKS-NATIVE-PROPERTIES.md`.
3. **Si encuentras divergencia** entre h2b y la documentación oficial https://academy.bricksbuilder.io/developer/, **gana academy** → registrar la excepción en este `README.md`.

## Pitfalls conocidos (v3.2.0)

- `_widthMax` (NO `_maxWidth`)
- `_heightMin` (NO `_minHeight`)
- `_cssClasses` es **string con espacios** (no array)
- `_cssCustom` NO renderiza en frontend (usar globalClasses o external CSS)
- Estructura **plana** con relaciones por ID (no nested children objects)

## Divergencias / overrides locales

(ninguna por ahora — registrar aquí cuando surjan)

## ADR de referencia

Ver `docs/decisiones.md` → **ADR-040** "Vendoring h2b.skill como corpus dorado de shapes Bricks JSON".

## Atribución

Trabajo original © Filipp ([iamfilipp](https://github.com/iamfilipp)). Vendorado en Webcafeína Migrator bajo MIT License (ver `LICENSE`).
