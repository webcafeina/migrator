# Pseudo-Selectors in Bricks Builder

**v3.1 Breakthrough:** ALL Bricks properties support pseudo-selector variants!

## Syntax

Append pseudo-selector to any property name:

```json
"_propertyName:pseudoSelector": { ... }
```

## Supported Pseudo-Selectors

### State-Based
- `:hover` - Mouse hover
- `:focus` - Keyboard/click focus
- `:active` - Click/tap active state
- `:visited` - Visited links

### Structural
- `:first-child` - First child element
- `:last-child` - Last child element
- `:nth-child(n)` - Nth child (e.g., `:nth-child(2n)` for even)
- `:nth-of-type(n)` - Nth of type

### Form States
- `:checked` - Checked checkbox/radio
- `:disabled` - Disabled form element
- `:enabled` - Enabled form element
- `:valid` - Valid form input
- `:invalid` - Invalid form input

---

## Examples

### Hover Effects
```json
{
  "_background": {"color": {"hex": "#0066cc"}},
  "_background:hover": {"color": {"hex": "#0052a3"}},
  "_transform:hover": {"translateY": "-2"},
  "_boxShadow:hover": [{"offsetY": "8", "blur": "24", ...}]
}
```

### Button States
```json
{
  "_background": {"color": {"hex": "#0066cc"}},
  "_background:hover": {"color": {"hex": "#0052a3"}},
  "_background:active": {"color": {"hex": "#003d7a"}},
  "_background:disabled": {"color": {"hex": "#cccccc"}}
}
```

### Structural Selectors
```json
{
  "_padding:first-child": {"top": "0"},
  "_padding:last-child": {"bottom": "0"},
  "_background:nth-child(2n)": {"color": {"hex": "#f5f5f5"}}
}
```

### Form States
```json
{
  "_border:focus": {"color": {"hex": "#0066cc"}},
  "_border:invalid": {"color": {"hex": "#ff0000"}},
  "_opacity:disabled": "0.5"
}
```

---

## All Properties Support Pseudo-Selectors

Any property can have pseudo-selector variant:

```json
{
  "_padding:hover": {...},
  "_margin:hover": {...},
  "_width:hover": {...},
  "_typography:hover": {...},
  "_background:hover": {...},
  "_border:hover": {...},
  "_boxShadow:hover": {...},
  "_transform:hover": {...},
  "_opacity:hover": "...",
  // ... literally any property
}
```

---

## Transitions

Always add `_cssTransition` for smooth effects:

```json
{
  "_cssTransition": "all 0.3s ease",
  "_background": {"color": {"hex": "#000"}},
  "_background:hover": {"color": {"hex": "#fff"}}
}
```

---

## Multiple Pseudo-Selectors

Can stack multiple variants on same element:

```json
{
  "_background": {"color": {"hex": "#000"}},
  "_background:hover": {"color": {"hex": "#333"}},
  "_background:active": {"color": {"hex": "#666"}},
  "_background:first-child": {"color": {"hex": "#f00"}},
  "_transform:hover": {"scale": "1.1"},
  "_opacity:hover": "0.9"
}
```

---

## CSS to Bricks Conversion

### ❌ CSS (Old Way)
```css
.button {
  background: #0066cc;
}
.button:hover {
  background: #0052a3;
  transform: translateY(-2px);
}
```

### ✅ Bricks Native (New Way)
```json
{
  "_background": {"color": {"hex": "#0066cc"}},
  "_background:hover": {"color": {"hex": "#0052a3"}},
  "_transform:hover": {"translateY": "-2"},
  "_cssTransition": "all 0.3s ease"
}
```

---

## Impact

**Before v3.1:** ~60% native, 40% external CSS for pseudo-selectors  
**After v3.1:** 99.5%+ native, <0.5% external CSS

**External CSS only needed for:**
- `::before` and `::after` (pseudo-elements, not pseudo-selectors)
- Complex selectors (`.parent > .child:hover`)
- Attribute selectors (`[data-attr]:hover`)
