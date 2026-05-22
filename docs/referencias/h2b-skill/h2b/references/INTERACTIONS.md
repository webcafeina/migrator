# Bricks Native Interactions System

Complete reference for Bricks `_interactions` property.

## Structure

```json
{
  "_interactions": [
    {
      "id": "unique-id",
      "trigger": "click",
      "action": "showElement",
      "target": ".modal",
      "delay": "0s",
      // ... action-specific properties
    }
  ]
}
```

## Required Fields

- `id` - Unique identifier for the interaction
- `trigger` - When the interaction fires
- `action` - What the interaction does

## Triggers

### User Actions
- `click` - Mouse click
- `mouseenter` - Mouse enters element (hover)
- `mouseleave` - Mouse leaves element
- `mouseover` - Mouse over element
- `mouseout` - Mouse out of element

### Lifecycle Events
- `onLoad` - Page/element loads
- `onShow` - Element becomes visible
- `onHide` - Element becomes hidden

### Form Events
- `submit` - Form submission
- `change` - Form field changes
- `focus` - Field receives focus
- `blur` - Field loses focus

### Scroll Events
- `scroll` - Window/element scrolls
- `scrollIntoView` - Element scrolls into view

---

## Actions

### Element Visibility
- `showElement` - Show element
- `hideElement` - Hide element
- `toggleElement` - Toggle element visibility

### Class Management
- `addClass` - Add class to element
- `removeClass` - Remove class from element
- `toggleClass` - Toggle class on element

### Animations
- `playAnimation` - Play animation
- `stopAnimation` - Stop animation
- `pauseAnimation` - Pause animation

### Navigation
- `scrollTo` - Scroll to element
- `navigateToUrl` - Navigate to URL

---

## Common Patterns

### Modal/Popup
```json
{
  "_interactions": [
    {
      "id": "open-modal",
      "trigger": "click",
      "action": "showElement",
      "target": ".modal-overlay"
    }
  ]
}
```

### Close Button
```json
{
  "_interactions": [
    {
      "id": "close-modal",
      "trigger": "click",
      "action": "hideElement",
      "target": ".modal-overlay"
    }
  ]
}
```

### Toggle Menu
```json
{
  "_interactions": [
    {
      "id": "toggle-menu",
      "trigger": "click",
      "action": "toggleClass",
      "className": "menu-open",
      "target": "body"
    }
  ]
}
```

### Scroll Animation
```json
{
  "_interactions": [
    {
      "id": "fade-in-on-scroll",
      "trigger": "scrollIntoView",
      "action": "playAnimation",
      "animation": "fadeIn",
      "duration": "1s",
      "delay": "0s"
    }
  ]
}
```

### Hover Animation
```json
{
  "_interactions": [
    {
      "id": "pulse-on-hover",
      "trigger": "mouseenter",
      "action": "playAnimation",
      "animation": "pulse",
      "duration": "0.5s"
    }
  ]
}
```

---

## Animation Types

Common animation presets:
- `fadeIn` / `fadeOut`
- `slideInUp` / `slideInDown` / `slideInLeft` / `slideInRight`
- `zoomIn` / `zoomOut`
- `bounce`
- `pulse`
- `shake`
- `rotateIn` / `rotateOut`
- `flipInX` / `flipInY`

---

## Multiple Interactions

Single element can have multiple interactions:

```json
{
  "_interactions": [
    {
      "id": "show-on-click",
      "trigger": "click",
      "action": "showElement",
      "target": ".content"
    },
    {
      "id": "pulse-on-hover",
      "trigger": "mouseenter",
      "action": "playAnimation",
      "animation": "pulse",
      "duration": "0.5s"
    },
    {
      "id": "hide-on-leave",
      "trigger": "mouseleave",
      "action": "hideElement",
      "target": ".tooltip"
    }
  ]
}
```

---

## Complete Example: Interactive Card

```json
{
  "id": "card",
  "name": "div",
  "parent": 0,
  "children": ["card-image", "card-content"],
  "settings": {
    "_cssTransition": "all 0.3s ease",
    "_interactions": [
      {
        "id": "lift-on-hover",
        "trigger": "mouseenter",
        "action": "addClass",
        "className": "lifted"
      },
      {
        "id": "unlift-on-leave",
        "trigger": "mouseleave",
        "action": "removeClass",
        "className": "lifted"
      },
      {
        "id": "show-details-on-click",
        "trigger": "click",
        "action": "showElement",
        "target": ".card-details"
      }
    ]
  },
  "label": "Interactive Card"
}
```

---

## Delay & Duration

Control timing:

```json
{
  "id": "delayed-fade",
  "trigger": "onLoad",
  "action": "playAnimation",
  "animation": "fadeIn",
  "duration": "1s",
  "delay": "0.5s"
}
```

---

## Target Options

Bricks interactions support three target types via the Bricks Builder UI:

### 1. Self
Action applies to the element itself (the element with the interaction).
- No `target` field needed in JSON
- Example: Clicking a button to hide itself

```json
{
  "id": "hide-self",
  "trigger": "click",
  "action": "hideElement"
  // No target - applies to self
}
```

### 2. CSS Selector
Action applies to elements matching a CSS selector.
- Supports class selectors (`.classname`)
- Supports ID selectors (`#id`)
- Supports element selectors (`body`, `div`, etc.)

```json
{
  "action": "showElement",
  "target": ".modal"        // Class selector
}

{
  "action": "hideElement",
  "target": "#sidebar"      // ID selector
}

{
  "action": "toggleClass",
  "target": "body"          // Element selector
}
```

### 3. Popup
Action applies to a Bricks popup element.
- Used specifically for popup interactions
- Target must be a valid popup ID

```json
{
  "action": "showElement",
  "target": "popup-id"
}
```

**If no `target` specified:** Action applies to the element itself (same as "Self").

---

## Best Practices

1. **Unique IDs:** Always use unique `id` for each interaction
2. **Descriptive names:** Use clear, action-based names (e.g., "open-modal", "close-sidebar")
3. **Combine with transitions:** Add `_cssTransition` for smooth effects
4. **Test interactions:** Verify all triggers and actions work as expected
5. **Group logically:** Related interactions on same element (open/close, hover/leave)
6. **Use delays sparingly:** Only when timing is critical
7. **Prefer interactions over JavaScript:** Always use interactions when possible

---

## Limitations

**Not supported via interactions:**
- Complex conditionals (if/else logic)
- Calculations
- API calls
- Data manipulation
- Advanced timing sequences

**Use JavaScript (extracted to files) for these cases.**
