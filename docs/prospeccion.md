# Prospección — Webcafeína Migrator

> Documento stub. Se completa en **Fase 9 — Prospección**.

---

## Objetivo del módulo

Descubrir empresas españolas cuyas webs estén construidas con Wix, Hostinger AI Builder o Webflow, enriquecerlas con datos de contacto y empresa, y preparar secuencias de outreach personalizadas que un operador humano revisará y enviará.

> **Importante**: la herramienta NUNCA envía outreach automáticamente. Solo prepara.

## Flujo (resumen)

Ver [docs/arquitectura.md §5](./arquitectura.md#5-flujo-de-prospección-detallado).

```
operador → prospector → fingerprinter → enricher → outreach-composer → revisión humana → envío manual
```

## Subagentes implicados

- `prospector` — descubrimiento (Google Maps + directorios)
- `fingerprinter` — clasifica builder
- `enricher` — añade contacto + datos empresa
- `outreach-composer` — prepara secuencias personalizadas

## Skills usados

- `google-maps-scraper`, `directory-scraper`, `builtwith-fingerprint`, `lsr-fingerprint`
- `proxy-rotation`, `captcha-handling`
- `gdpr-compliance`, `resend-notifier`

## Cumplimiento legal

Toda operación debe pasar por [gdpr-compliance skill](../.claude/skills/gdpr-compliance/SKILL.md):

- Base jurídica: interés legítimo art. 6.1.f RGPD para descubrimiento y enrichment.
- LSSI-CE: outreach con identificación, motivo, base jurídica, opt-out funcional, link a privacidad.
- TTL: leads sin consentimiento → purga a 12 meses.

Ver [ISSUES.md WCM-002](../ISSUES.md) (datos legales pendientes de completar).

## Métricas operacionales

(A medir desde dashboard en Fase 9)

- Leads descubiertos / mes
- Tasa de fingerprint correcto (verificación manual sample)
- Coste promedio por lead cualificado (Bright Data + Maps API + 2captcha)
- Tasa de respuesta a outreach (humano reporta tras envío)
- Tasa de conversión lead → proyecto

---

## Por documentar en Fase 9

- Plantillas de secuencia base (`wix-corporate-3steps`, etc.)
- Script de scoring de leads
- Política exacta de retención y purga
- Playbook de revisión de outreach (qué validar antes de aprobar)
- Casos límite legales (autónomos individualizados, asociaciones, etc.)
