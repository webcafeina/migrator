---
name: lsr-fingerprint
description: "Last Stack Resort" — fingerprinting heurístico por JS globals + DOM patterns cuando builtwith-fingerprint no resuelve. Requiere renderizado real con Playwright. Más caro y lento, solo se invoca como fallback.
---

# Skill — LSR Fingerprint (Last Stack Resort)

## Propósito

Romper empates o resolver casos donde `builtwith-fingerprint` no llegue a confianza suficiente. Inspecciona el runtime real del browser (JS globals, DOM tras hidratación, fingerprints específicos).

## Cuándo aplicar

- `builtwith-fingerprint` devolvió `confidence < 0.5` o múltiples candidatos con `> 0.6`.
- Operador marcó manualmente la URL como "requiere análisis profundo".

## Coste

- Cargar la página entera en Playwright headless: 5–15 s por URL.
- ~ 50× más caro que builtwith por consumo de proxy y CPU.
- Por eso es **fallback**, no default.

## Contrato

```python
class LsrFingerprinter:
    async def fingerprint(self, url: str) -> list[TechMatch]:
        """
        Carga la página con Playwright + stealth, espera hidratación completa,
        ejecuta probes JS para inspeccionar window globals y DOM.
        """
```

## Probes JS

Ejecutados vía `page.evaluate()`:

```javascript
async function probeStack() {
  const probes = {
    // Builder probes
    wix: !!window.wixBiSession,
    wixStudio: !!window.studioBiSession,
    webflow: !!window.Webflow && typeof window.Webflow.require === "function",
    hostingerAi: !!window.HOSTAI || document.querySelector('[data-hostai-loaded]') !== null,
    squarespace: !!window.Static && Static.SQUARESPACE_CONTEXT !== undefined,
    shopify: !!window.Shopify && Shopify.shop !== undefined,
    wordpress: document.querySelector('meta[name="generator"][content*="WordPress"]') !== null,

    // Framework probes
    react: !!window.React || document.querySelector('[data-reactroot]') !== null,
    vue: !!window.Vue || document.querySelector('[data-v-]') !== null,
    angular: !!window.ng || document.querySelector('[ng-version]') !== null,

    // CMS probes
    drupal: !!window.Drupal,
    joomla: document.body?.id === 'system' || !!window.Joomla,
    typo3: !!document.querySelector('meta[name="generator"][content*="TYPO3"]'),

    // E-commerce
    woocommerce: !!window.wc_add_to_cart_params || document.body?.classList.contains('woocommerce'),
    magento: !!window.Magento || !!window.checkout,
    prestashop: !!window.prestashop,

    // Builders nicho
    elementor: !!document.querySelector('.elementor-page'),
    divi: !!document.querySelector('.et_pb_section'),
    bricks: !!document.querySelector('.brxe-section') || document.body?.classList.contains('bricks-is-frontend'),
    breakdance: !!document.querySelector('.bde-section'),
    oxygen: !!document.querySelector('.ct-section'),
  };
  return probes;
}
```

Después aplicar `aggregate()` igual que en builtwith, con pesos altos (cada probe positivo = 0.5–0.7).

## DOM patterns adicionales

- Estructura de scripts cargados (orden, dependencias)
- Headers de respuesta capturados durante navegación (Playwright `page.on("response")`)
- Cookies establecidas (algunas plataformas tienen cookies características: `_wix_browser_sess`, `webflow-uid`)

## Caso especial: detección WP + builder específico

WordPress puede tener varios page builders. LSR comprueba:
- Bricks (`.brxe-*` clases)
- Elementor (`.elementor-*`)
- Divi (`.et_pb_*`)
- Breakdance, Oxygen

Si detecta WP + Bricks: confidence muy alta (origen perfecto para "actualizar" sin migrar).

## Errores tipados

- `LsrError` (raíz)
- `TimeoutError` — Playwright > 30s sin hidratación
- `RenderError` — error genérico de Playwright

## Tests

- Fixtures Playwright con sitios reales conocidos
- Mock de `page.evaluate` para tests unitarios del agregador

## Dependencias

- Playwright (Python)
- `playwright-stealth`
