# JavaScript Handling Strategy

4-tier system for processing JavaScript when converting to Bricks.

## Tier 1: Convert to `_interactions` (Best - 90%+ cases)

**Use when:** Simple interactions, animations, show/hide, click events

**Benefits:**
- 100% native Bricks
- No external files
- Visual editing in Bricks
- Best performance

**See:** `references/INTERACTIONS.md` for complete interactions reference

### Examples:
- Click to show/hide element → `_interactions`
- Hover animations → `_interactions`
- Form submit actions → `_interactions`
- Scroll-triggered animations → `_interactions`
- Toggle classes → `_interactions`

---

## Tier 2: Extract to .js Files (Complex Logic)

**Use when:** Complex calculations, API calls, advanced logic

**Process:**
1. Extract JavaScript to separate `.js` file
2. Document dependencies
3. Provide instructions for including in Bricks

**Example:**
```javascript
// cart-calculator.js
function calculateTotal(items) {
  // Complex calculation logic
  return items.reduce((sum, item) => sum + (item.price * item.quantity), 0);
}
```

**In Bricks:** User includes via Code element or theme functions

---

## Tier 3: Reference External Libraries (CDN)

**Use when:** jQuery, GSAP, Chart.js, etc.

**Process:**
1. Identify library and version
2. Provide CDN link
3. Document in output

**Example:**
```html
<!-- Required: GSAP from CDN -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.0/gsap.min.js"></script>
```

---

## Tier 4: Document Instructions (Setup)

**Use when:** Requires WordPress hooks, custom post types, etc.

**Process:**
1. Document what's needed
2. Provide setup instructions
3. Include code snippets

**Example:**
```
Setup Required:
1. Install Contact Form 7 plugin
2. Create form with ID: contact-form-1
3. Add this code to functions.php: [code]
```

---

## Decision Tree

```
JavaScript Code
│
├─ Simple interaction? (click, hover, show/hide)
│  └─ YES → Tier 1: Convert to _interactions ✅
│
├─ Complex logic? (calculations, conditionals)
│  └─ YES → Tier 2: Extract to .js file
│
├─ Uses library? (jQuery, GSAP, etc.)
│  └─ YES → Tier 3: Reference CDN
│
└─ Requires WordPress integration?
   └─ YES → Tier 4: Document instructions
```

---

## Common JavaScript to _interactions Conversions

### Click to Toggle Class
**JavaScript:**
```javascript
element.addEventListener('click', function() {
  this.classList.toggle('active');
});
```

**Bricks:**
```json
{
  "_interactions": [
    {
      "id": "toggle-active",
      "trigger": "click",
      "action": "toggleClass",
      "className": "active"
    }
  ]
}
```

### Show Element on Click
**JavaScript:**
```javascript
button.addEventListener('click', function() {
  modal.style.display = 'block';
});
```

**Bricks:**
```json
{
  "_interactions": [
    {
      "id": "show-modal",
      "trigger": "click",
      "action": "showElement",
      "target": ".modal"
    }
  ]
}
```

### Scroll Animation
**JavaScript:**
```javascript
window.addEventListener('scroll', function() {
  if (isInViewport(element)) {
    element.classList.add('fadeIn');
  }
});
```

**Bricks:**
```json
{
  "_interactions": [
    {
      "id": "scroll-fade",
      "trigger": "onShow",
      "action": "playAnimation",
      "animation": "fadeIn",
      "duration": "1s"
    }
  ]
}
```

---

## Output Format

### When using Tier 1 (_interactions):
Include `_interactions` in element settings (see INTERACTIONS.md)

### When using Tier 2-4:
Create companion files and document:

```
OUTPUT FILES:
- hero-section.json (Bricks JSON)
- scripts/modal-logic.js (Extracted JavaScript)
- README.md (Setup instructions)

SETUP INSTRUCTIONS:
1. Include modal-logic.js in theme
2. Enqueue script in functions.php
3. [Additional steps...]
```

---

## Priority Guidelines

**Always prefer Tier 1** when possible:
- Simpler maintenance
- Better performance
- Visual editing
- No external dependencies

**Use Tier 2-4** only when:
- Logic too complex for interactions
- Requires external APIs
- Needs WordPress integration
- Uses specialized libraries
