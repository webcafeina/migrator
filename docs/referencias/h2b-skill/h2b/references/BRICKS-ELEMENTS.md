# Bricks Builder Elements Reference

Complete list of all 31 Bricks elements with required settings and usage notes.

## Structure Elements (4)

### 1. `section`
**Purpose:** Top-level section wrapper  
**Required settings:** None  
**Common use:** Page sections, major layout blocks  
**HTML mapping:** `<section>`, `<header>`, `<main>`, `<footer>`

### 2. `container`
**Purpose:** Bricks container (max-width, responsive)  
**Required settings:** None  
**Common use:** Content wrapper within sections  
**HTML mapping:** `<div class="container">`

### 3. `block`
**Purpose:** Generic block element  
**Required settings:** None  
**Common use:** Layout blocks, flex/grid containers  
**HTML mapping:** `<div>` (for layout purposes)

### 4. `div`
**Purpose:** Generic div container  
**Required settings:** None  
**Common use:** Generic wrappers  
**HTML mapping:** `<div>`

---

## Typography Elements (4)

### 5. `heading`
**Purpose:** Headings (h1-h6)  
**Required settings:**
```json
{
  "text": "Heading text",
  "tag": "h2"  // Optional: h1, h2, h3, h4, h5, h6 (defaults to h2)
}
```
**HTML mapping:** `<h1>`, `<h2>`, `<h3>`, `<h4>`, `<h5>`, `<h6>`

### 6. `text-basic`
**Purpose:** Simple text paragraphs  
**Required settings:**
```json
{
  "text": "Text content"
}
```
**HTML mapping:** `<p>`

### 7. `text`
**Purpose:** Rich text with HTML  
**Required settings:**
```json
{
  "text": "<p>HTML content here</p>"
}
```
**HTML mapping:** `<div>` with HTML content

### 8. `text-link`
**Purpose:** Text link  
**Required settings:**
```json
{
  "text": "Link text",
  "link": {
    "type": "external",
    "url": "#"
  }
}
```
**HTML mapping:** `<a>`

---

## Interactive Elements (2)

### 9. `button`
**Purpose:** Button element  
**Required settings:**
```json
{
  "text": "Button text",
  "style": "primary"  // Optional: primary, secondary, light, etc.
}
```
**HTML mapping:** `<button>`, `<a class="btn">`

### 10. `icon`
**Purpose:** Icon element  
**Required settings:**
```json
{
  "icon": {
    "library": "ionicons",
    "icon": "ion-ios-arrow-forward"
  }
}
```
**HTML mapping:** `<i>`, `<svg>`, icon fonts

---

## Media Elements (5)

### 11. `image`
**Purpose:** Image element  
**Required settings:**
```json
{
  "image": {
    "url": "https://...",
    "external": true,
    "filename": "photo.jpg"
  }
}
```
**HTML mapping:** `<img>`

### 12. `video`
**Purpose:** Video player  
**Required settings:** Varies by type (YouTube/Vimeo/file)  
**HTML mapping:** `<video>`, `<iframe>` (YouTube/Vimeo)

### 13. `audio`
**Purpose:** Audio player  
**Required settings:** None (minimal)  
**HTML mapping:** `<audio>`

### 14. `svg`
**Purpose:** SVG element  
**Required settings:** None  
**HTML mapping:** `<svg>`

### 15. `ba-lottie`
**Purpose:** Lottie animation  
**Required settings:**
```json
{
  "source_type": "url",
  "trigger": "viewport"
}
```
**HTML mapping:** Lottie animation files

---

## Layout/Display Elements (6)

### 16. `divider`
**Purpose:** Horizontal divider  
**Required settings:** None  
**HTML mapping:** `<hr>`

### 17. `dropdown`
**Purpose:** Dropdown menu  
**Required settings:** Nested structure with content div  
**HTML mapping:** `<div class="dropdown">`

### 18. `accordion`
**Purpose:** Simple accordion  
**Required settings:**
```json
{
  "accordions": [
    {"title": "Item", "content": "Content"}
  ]
}
```
**HTML mapping:** Accordion pattern

### 19. `accordion-nested`
**Purpose:** Nested accordion structure  
**Required settings:** Nested structure with title/content blocks  
**HTML mapping:** Complex accordion pattern

### 20. `image-gallery`
**Purpose:** Image gallery  
**Required settings:**
```json
{
  "items": {
    "images": [...]
  }
}
```
**HTML mapping:** Gallery pattern

### 21. `map`
**Purpose:** Map with addresses  
**Required settings:**
```json
{
  "addresses": [
    {"latitude": "...", "longitude": "..."}
  ]
}
```
**HTML mapping:** Google Maps embed

---

## Carousel/Slider Elements (3)

### 22. `carousel`
**Purpose:** Content carousel  
**Required settings:**
```json
{
  "fields": [...]
}
```
**HTML mapping:** Carousel pattern

### 23. `slider`
**Purpose:** Image slider  
**Required settings:**
```json
{
  "items": [
    {"title": "Slide", "content": "..."}
  ]
}
```
**HTML mapping:** Slider pattern

### 24. `slider-nested`
**Purpose:** Nested slider structure  
**Required settings:** Nested block structure  
**HTML mapping:** Complex slider pattern

---

## Special Elements (7)

### 25. `counter`
**Purpose:** Animated counter  
**Required settings:**
```json
{
  "countTo": 1000
}
```
**HTML mapping:** Number counter animations

### 26. `pricing-tables`
**Purpose:** Pricing table  
**Required settings:**
```json
{
  "pricingTables": [...]
}
```
**HTML mapping:** Pricing table pattern

### 27. `countdown`
**Purpose:** Countdown timer  
**Required settings:**
```json
{
  "date": "2026-01-01 12:00"
}
```
**HTML mapping:** Countdown timers

### 28. `pie-chart`
**Purpose:** Pie chart  
**Required settings:**
```json
{
  "percent": 60
}
```
**HTML mapping:** Chart/graph elements

### 29. `testimonials`
**Purpose:** Testimonials slider  
**Required settings:**
```json
{
  "items": [
    {"content": "...", "name": "..."}
  ]
}
```
**HTML mapping:** Testimonial carousels

### 30. `breadcrumbs`
**Purpose:** Breadcrumb navigation  
**Required settings:** None (auto-generated)  
**HTML mapping:** Breadcrumb pattern

### 31. `back-to-top`
**Purpose:** Back to top button  
**Required settings:** Nested structure with icon + text  
**HTML mapping:** Scroll-to-top buttons

---

## HTML to Bricks Element Mapping Guide

```
HTML Tag              → Bricks Element
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
<section>             → section
<header>              → section
<main>                → section
<footer>              → section
<div>                 → div (or block/container based on context)
<h1> through <h6>     → heading (with tag: "h1" etc.)
<p>                   → text-basic
<a>                   → text-link
<button>              → button
<img>                 → image
<video>               → video
<audio>               → audio
<svg>                 → svg
<hr>                  → divider
```

## Context-Based Element Selection

**When to use `div` vs `block` vs `container`:**
- `section` → Top-level page sections
- `container` → Content wrappers with max-width
- `block` → Flex/grid layout containers
- `div` → Generic wrappers

**When to use `heading` vs `text-basic` vs `text`:**
- `heading` → h1-h6 semantic headings
- `text-basic` → Simple paragraphs
- `text` → Rich HTML content
