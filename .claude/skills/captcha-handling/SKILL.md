---
name: captcha-handling
description: Detección de captcha (reCAPTCHA v2, v3, hCaptcha, Cloudflare Turnstile, generic) y fallback a 2captcha API solo cuando proxy-rotation no basta. Solo en prospección. Mantiene presupuesto controlado por proyecto/campaña.
---

# Skill — Captcha Handling

## Propósito

Resolver captchas que bloquean el scraping prospectivo, **como último recurso** después de que `proxy-rotation` haya fallado.

## Cuándo aplicar

- Solo en operaciones de prospección (descubrimiento, fingerprinting, enrichment).
- Solo si la fuente es valiosa (directorio sectorial relevante, no un blog cualquiera).
- Nunca en migración cliente (no debería haber captcha contra una web del cliente; si lo hay, es problema del cliente).

## Detección de captcha

```python
class CaptchaDetector:
    def detect(self, html: str, url: str, response_status: int) -> CaptchaDetection | None:
        """Devuelve tipo de captcha y data necesaria para resolverlo, o None."""
```

Heurísticas:

| Tipo | Señales |
|---|---|
| reCAPTCHA v2 | `<div class="g-recaptcha" data-sitekey="...">`; iframe `recaptcha/api2/anchor` |
| reCAPTCHA v3 | Script `https://www.google.com/recaptcha/api.js?render=...`; sin checkbox |
| hCaptcha | `<div class="h-captcha" data-sitekey="...">`; iframe `hcaptcha.com` |
| Cloudflare Turnstile | `<div class="cf-turnstile" data-sitekey="...">` |
| Cloudflare challenge page | HTTP 503 + `cf-mitigated: challenge` header + texto "Just a moment..." |
| Captcha custom imagen | imágenes con CAPTCHA en alt, input asociado |

## Resolución vía 2captcha

```python
class TwoCaptchaSolver:
    def solve_recaptcha_v2(self, site_key: str, page_url: str) -> str: ...
    def solve_recaptcha_v3(self, site_key: str, page_url: str, action: str, min_score: float = 0.7) -> str: ...
    def solve_hcaptcha(self, site_key: str, page_url: str) -> str: ...
    def solve_turnstile(self, site_key: str, page_url: str) -> str: ...
    def solve_image_captcha(self, image_bytes: bytes) -> str: ...
```

Coste medio (orientativo):
- reCAPTCHA v2: ~ $0.002 / resolución
- reCAPTCHA v3: ~ $0.003
- hCaptcha: ~ $0.003
- Turnstile: ~ $0.002

## Política de presupuesto

- Cada campaña define `max_captcha_spend_eur` (default 5 €).
- Si se supera, parar el proceso, marcar campaña `status="budget_exceeded"`, notificar al operador.
- Métricas en dashboard: resoluciones por campaña, coste acumulado, ratio éxito.

## Integración con Playwright

```python
# 1. Detectar captcha
detection = detector.detect(await page.content(), page.url, response.status)

if detection:
    # 2. Resolver via 2captcha
    token = solver.solve(detection)

    # 3. Inyectar token y submit
    if detection.type == "recaptcha_v2":
        await page.evaluate(f"document.getElementById('g-recaptcha-response').innerHTML = '{token}';")
        # disparar el callback si existe
        await page.evaluate(f"___grecaptcha_cfg.clients[0].L.L.callback('{token}')")
    # similar para los demás tipos
```

## Caso especial: Cloudflare challenge

- 2captcha tiene servicio específico "Cloudflare Turnstile" (sitekey).
- Si la página es challenge interstitial (no Turnstile), no resolver — buscar IP residencial alternativa (más probable que pase sin desafío).

## Errores tipados

- `CaptchaError` (raíz)
- `CaptchaServiceUnavailableError` — 2captcha API caído
- `BudgetExceededError` — campaña sin presupuesto
- `UnsupportedCaptchaTypeError` — captcha custom no resolvible

## Tests

- Mock de 2captcha API
- Detector contra fixtures HTML de cada tipo
- Test budget: simular 10 resoluciones con coste mayor que budget → debe parar

## Dependencias

- `2captcha-python` SDK
- Credenciales en `.env`: `TWOCAPTCHA_API_KEY`
