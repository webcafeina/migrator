---
name: h2b
description: Converts HTML/CSS/JavaScript to Bricks Builder JSON format using flat structure with ID-based relationships. Use when converting HTML markup, CSS styles, or JavaScript interactions to Bricks Builder paste-ready JSON. Supports 31 Bricks elements, pseudo-selectors (:hover, :focus, :nth-child), gradients, 99.5%+ native property coverage. Always outputs flat element array with parent/children ID references, never nested objects.
---

# h2b - HTML to Bricks Builder Converter

**Version:** 3.2.0  
**Native Coverage:** 99.5%+  
**Output:** Bricks Builder paste-ready JSON

## Version 3.2.0 Changes

**Critical Fixes:**
- Fixed property naming convention: `_heightMin`/`_widthMax` (NOT `_minHeight`/`_maxWidth`)
- Clarified `_cssClasses` is a space-separated STRING, not an array
- Documented that both `_cssClasses` AND `_cssId` should be used
- Removed `_cssCustom` (doesn't work - use external CSS instead)
- Updated Bricks version to 2.1.4
- Added guidance on `text` vs `heading` element for rich HTML content

## Critical: Flat Structure with ID Relationships

Bricks uses FLAT structure with ID-based parent-child relationships, NOT nested children.

### ❌ WRONG (Nested)
```json
{"content": [{"name": "div", "children": [{"name": "heading"}]}]}
```

### ✅ CORRECT (Flat)
```json
{
  "content": [
    {"id": "div1", "name": "div", "parent": 0, "children": ["h1"]},
    {"id": "h1", "name": "heading", "parent": "div1", "children": []}
  ]
}
```

## Critical: Classes and IDs

### Use BOTH _cssClasses AND _cssId

Every element that needs external CSS targeting should have BOTH:

```json
{
  "settings": {
    "_cssClasses": "my-class another-class",  // STRING, space-separated
    "_cssId": "unique-element-id"             // STRING, unique identifier
  }
}
```

**Why both?**
- `_cssClasses` → Reusable class selectors in external CSS (e.g., `.orbit-item`)
- `_cssId` → Unique HTML ID for specific targeting (e.g., `#orbit-item-1`)

### _cssClasses Format

**CRITICAL:** `_cssClasses` is a space-separated STRING, NOT an array.

```json
// ✅ CORRECT
"_cssClasses": "orbit-item rotating-element"

// ❌ WRONG
"_cssClasses": ["orbit-item", "rotating-element"]
```

### Custom Inline Styles Don't Work

**`_cssCustom` property does NOT output to frontend CSS.**

```json
// ❌ DOESN'T WORK
{
  "settings": {
    "_cssCustom": "transform: rotate(45deg);"  // Bricks ignores this!
  }
}
```

**✅ CORRECT - Use external CSS:**
```css
#element-id {
  transform: rotate(45deg);
}
```

**When to use external CSS:**
- Custom transforms
- Keyframe animations (`@keyframes`)
- `mix-blend-mode`
- Complex selectors (`.parent:hover .child`)
- Any CSS that `_cssCustom` would have handled

## Required Fields on EVERY Element

```json
{
  "id": "unique-id",        // Unique ID (e.g., "einrji", "mhkwpa")
  "name": "div",            // Element type (see BRICKS-ELEMENTS.md)
  "parent": 0,              // Parent ID (0 for root)
  "children": ["child1"],   // Array of child IDs (or [])
  "settings": {
    "_cssClasses": "my-class",  // For external CSS targeting
    "_cssId": "unique-id"       // Custom HTML ID
  },
  "label": "My Element"     // Display name (optional but recommended)
}
```

**IMPORTANT:**
- Always add `_cssClasses` for elements needing external CSS
- Always add `_cssId` for stable HTML IDs
- Use semantic value for `_cssId`
- Example: `"id": "einrji"` → `"_cssId": "card-1"` → HTML: `<div id="card-1">`

## Conversion Workflow

1. Parse HTML → Build DOM tree
2. Generate unique IDs → Random 6-char lowercase (e.g., "einrji", "mhkwpa")
3. Map elements → HTML tags to Bricks elements (see BRICKS-ELEMENTS.md)
4. Flatten structure → Convert tree to flat array with parent/children IDs
5. Convert styles → CSS to Bricks native properties (see BRICKS-NATIVE-PROPERTIES.md)
6. Handle pseudo-selectors → :hover/:focus to native variants (see PSEUDO-SELECTORS.md)
7. Extract custom CSS → Anything that needs `_cssCustom` goes to external CSS file
8. Process JavaScript → Convert to interactions (see JAVASCRIPT-HANDLING.md + INTERACTIONS.md)
9. Build JSON → Assemble with required metadata
10. Validate → Check all required fields present

## ID Generation

Pattern: Random 6-char lowercase to match Bricks native generation.

**Examples:**
```
einrji
mhkwpa
asdkfj
vbnmqw
zxcpoi
```

**For _cssId:** Use semantic names for readability in CSS:
```
hero-section
orbit-container
card-wrapper-1
```

Rules: lowercase, hyphens, descriptive, unique.

## Output Structure

```json
{
  "content": [
    // Flat array - all elements are siblings
    {
      "id": "einrji",
      "name": "...",
      "parent": 0 | "parent-id",
      "children": [...],
      "settings": {
        "_cssClasses": "my-class",
        "_cssId": "my-id",
        ...
      },
      "label": "..."
    }
  ],
  "source": "bricksCopiedElements",
  "sourceUrl": "https://github.com/iamfilipp/html2bricks",
  "version": "2.1.4",
  "globalClasses": [],
  "globalElements": []
}
```

**Metadata (all required):**
- `source` → Always `"bricksCopiedElements"`
- `sourceUrl` → Always `"https://github.com/iamfilipp/html2bricks"`
- `version` → `"2.1.4"` (current Bricks version)
- `globalClasses` → `[]` (unless using global classes)
- `globalElements` → `[]` (unless referencing saved elements)

## Image Handling

**External URL:**
```json
{
  "name": "image",
  "settings": {
    "image": {
      "url": "https://images.unsplash.com/photo-xyz",
      "external": true,
      "filename": "photo-xyz.jpg"
    }
  }
}
```

**No URL/local:**
```json
{
  "name": "image",
  "settings": {
    "image": {
      "filename": "placeholder.jpg"
    }
  }
}
```

## Text vs Heading Elements

**Use `heading` element for plain text:**
```json
{
  "name": "heading",
  "settings": {
    "tag": "h1",
    "text": "Plain heading text"
  }
}
```

**Use `text` element for styled/rich HTML:**
```json
{
  "name": "text",
  "settings": {
    "text": "<h1><span class=\"styled\">Rich</span> <span class=\"highlight\">HTML</span></h1>"
  }
}
```

**Why?** The `heading` element only accepts plain text. When HTML contains styled `<span>` elements inside headings, use the `text` element which accepts full HTML markup.

## Quality Checklist

- [ ] Flat structure (not nested)
- [ ] All elements have: id, name, parent, children, settings, label
- [ ] Elements needing CSS have `_cssClasses` as space-separated string
- [ ] Elements needing unique IDs have `_cssId` in settings
- [ ] Random 6-char lowercase IDs for element `id`
- [ ] Semantic IDs for `_cssId` values
- [ ] Parent/children relationships correct
- [ ] Bricks native properties (99.5%+) - CHECK PROPERTY NAMES
- [ ] Pseudo-selectors converted to native OR external CSS
- [ ] Images handled (URL or placeholder.jpg)
- [ ] JavaScript → interactions preferred (but use external CSS for hover effects)
- [ ] NO `_cssCustom` usage - all custom CSS in external file
- [ ] Metadata correct (version 2.1.4, correct sourceUrl)
- [ ] Valid Bricks element names
- [ ] Width/height not set to 0 (causes collapse for positioned children)

## Example: Hero Section

**Input:**
```html
<section><div><h1>Welcome</h1><button>Start</button></div></section>
```

**Output:**
```json
{
  "content": [
    {
      "id": "mhkwpa",
      "name": "section",
      "parent": 0,
      "children": ["qnxrtb"],
      "settings": {
        "_cssClasses": "hero-section",
        "_cssId": "hero"
      },
      "label": "Hero"
    },
    {
      "id": "qnxrtb",
      "name": "div",
      "parent": "mhkwpa",
      "children": ["einrji", "asdkfj"],
      "settings": {
        "_cssClasses": "hero-container",
        "_cssId": "container"
      },
      "label": "Container"
    },
    {
      "id": "einrji",
      "name": "heading",
      "parent": "qnxrtb",
      "children": [],
      "settings": {
        "_cssClasses": "hero-title",
        "_cssId": "title",
        "tag": "h1",
        "text": "Welcome"
      },
      "label": "Title"
    },
    {
      "id": "asdkfj",
      "name": "button",
      "parent": "qnxrtb",
      "children": [],
      "settings": {
        "_cssClasses": "cta-button",
        "_cssId": "btn",
        "text": "Start"
      },
      "label": "CTA"
    }
  ],
  "source": "bricksCopiedElements",
  "sourceUrl": "https://github.com/iamfilipp/html2bricks",
  "version": "2.1.4",
  "globalClasses": [],
  "globalElements": []
}
```

## References

Load these as needed:

- `references/BRICKS-ELEMENTS.md` - Complete list of 31 Bricks elements
- `references/BRICKS-NATIVE-PROPERTIES.md` - All native properties (99.5%+ coverage)
- `references/PSEUDO-SELECTORS.md` - Pseudo-selector conversion guide
- `references/INTERACTIONS.md` - Native interactions system
- `references/JAVASCRIPT-HANDLING.md` - JavaScript processing strategy

## Critical Reminders

- FLAT structure - Never nest children objects
- ID-based relationships - Use parent/children arrays  
- All required fields - id, name, parent, children, settings, label
- **Always add `_cssClasses`** - Space-separated string for CSS targeting
- **Always add `_cssId`** - Every element needs custom HTML ID in settings
- **NO `_cssCustom`** - Use external CSS file instead
- Unique IDs - Random 6-char for `id`, semantic for `_cssId`
- sourceUrl branding - `https://github.com/iamfilipp/html2bricks`
- Bricks version - `2.1.4`
- 99.5%+ native - Minimize external CSS (but use it when needed)
- Use `text` element for rich HTML, `heading` for plain text only
