# Bricks Native Properties Reference

Complete guide to Bricks Builder's native properties (99.5%+ CSS coverage).

## Layout Properties

### Spacing
```json
"_padding": {"top": "20", "right": "20", "bottom": "20", "left": "20"}
"_margin": {"top": "0", "right": "auto", "bottom": "0", "left": "auto"}
"_gap": "16"
```

### Dimensions

**CRITICAL:** Property naming pattern is `_[property][Min/Max]` NOT `_[min/max][Property]`

```json
"_width": "100%"
"_widthMin": "320"
"_widthMax": "1200"
"_height": "500"
"_heightMin": "200"
"_heightMax": "800"
```

**Examples:**
- ✅ CORRECT: `"_widthMax": "1200"`
- ❌ WRONG: `"_maxWidth": "1200"`
- ✅ CORRECT: `"_heightMin": "100vh"`
- ❌ WRONG: `"_minHeight": "100vh"`

### Display & Position
```json
"_display": "flex"  // block, flex, grid, inline-block, none
"_position": "relative"  // static, relative, absolute, fixed, sticky
"_top": "0"
"_right": "0"
"_bottom": "0"
"_left": "0"
"_zIndex": "10"
```

---

## Flexbox Properties

```json
"_display": "flex"
"_direction": "row"  // row, row-reverse, column, column-reverse
"_alignItems": "center"  // flex-start, flex-end, center, baseline, stretch
"_justifyContent": "space-between"  // flex-start, flex-end, center, space-between, space-around
"_flexWrap": "wrap"  // nowrap, wrap, wrap-reverse
"_gap": "20"
```

---

## Grid Properties

```json
"_display": "grid"
"_gridTemplateColumns": "repeat(3, 1fr)"
"_gridTemplateRows": "auto"
"_gridGap": "20"
"_gridColumnGap": "20"
"_gridRowGap": "20"
```

---

## Typography

```json
"_typography": {
  "font-family": "Arial, sans-serif",
  "font-size": "16",
  "font-weight": "600",
  "line-height": "1.5",
  "letter-spacing": "0.5",
  "text-align": "center",  // left, center, right, justify
  "text-transform": "uppercase",  // none, uppercase, lowercase, capitalize
  "text-decoration": "underline",  // none, underline, line-through
  "color": {"hex": "#000000"}
}
```

---

## Background

### Solid Color
```json
"_background": {
  "color": {"hex": "#0066cc"}
}
```

### Image
```json
"_background": {
  "image": {
    "url": "https://...",
    "size": "cover",  // cover, contain, auto
    "position": "center center",
    "repeat": "no-repeat"  // repeat, no-repeat, repeat-x, repeat-y
  }
}
```

### Gradient
```json
"_background": {
  "gradient": {
    "type": "linear",  // linear, radial
    "angle": "90",
    "stops": [
      {"color": {"hex": "#667eea"}, "position": "0"},
      {"color": {"hex": "#764ba2"}, "position": "100"}
    ]
  }
}
```

---

## Border

```json
"_border": {
  "style": "solid",
  "width": {"top": "1", "right": "1", "bottom": "1", "left": "1"},
  "color": {"hex": "#cccccc"},
  "radius": {"top": "8", "right": "8", "bottom": "8", "left": "8"}
}
```

**Border Radius Shorthand:**
```json
"_borderRadius": {
  "topLeft": "8",
  "topRight": "8",
  "bottomRight": "8",
  "bottomLeft": "8"
}
```

For circular elements, use `"50%"` for all corners.

---

## Effects

### Box Shadow
```json
"_boxShadow": [
  {
    "offsetX": "0",
    "offsetY": "4",
    "blur": "16",
    "spread": "0",
    "color": {"hex": "#000000", "opacity": 0.1}
  }
]
```

### Transform
```json
"_transform": {
  "translateX": "10",
  "translateY": "-5",
  "scaleX": "1.1",
  "scaleY": "1.1",
  "rotate": "45",
  "skewX": "0",
  "skewY": "0"
}
```

**IMPORTANT:** Bricks' `_transform` cannot combine rotation with translation (e.g., `rotate(45deg) translateY(-420px)`). For complex transforms, use external CSS with ID selectors.

### Opacity & Transitions
```json
"_opacity": "0.8"
"_cssTransition": "all 0.3s ease"
```

---

## Overflow & Visibility

```json
"_overflow": "hidden"  // visible, hidden, scroll, auto
"_overflowX": "auto"
"_overflowY": "scroll"
"_visibility": "visible"  // visible, hidden
```

---

## Cursor

```json
"_cursor": "pointer"  // auto, pointer, default, not-allowed, grab, etc.
```

---

## Property Coverage

**99.5%+ coverage includes:**
- ✅ All layout properties
- ✅ All flexbox properties
- ✅ All grid properties
- ✅ All typography properties
- ✅ All background properties (solid, image, gradient)
- ✅ All border properties
- ✅ All transform properties (basic - see note below)
- ✅ All effect properties

**Not natively supported (use external CSS):**
- ❌ `_cssCustom` property (doesn't output to frontend)
- ❌ Complex transforms combining multiple operations
- ❌ `::before` and `::after` pseudo-elements
- ❌ Complex selectors (`.parent > .child:hover`)
- ❌ Attribute selectors (`[data-attr]:hover`)
- ❌ `mix-blend-mode`
- ❌ Keyframe animations (`@keyframes`)

---

## Common Pitfalls

### Zero Dimensions Cause Collapse
Elements with `width: 0` and `height: 0` collapse. Absolutely positioned children need a dimensioned parent.

**❌ BAD:**
```json
{
  "_position": "relative",
  "_width": "0",
  "_height": "0"
}
```

**✅ GOOD:**
```json
{
  "_position": "relative",
  "_width": "1000",
  "_height": "1000"
}
```

### Property Name Pattern

Remember: `_[property][Min/Max]` NOT `_[min/max][Property]`

**Quick reference:**
- `_width` / `_widthMin` / `_widthMax`
- `_height` / `_heightMin` / `_heightMax`
- NOT `_minWidth`, `_maxWidth`, `_minHeight`, `_maxHeight`
