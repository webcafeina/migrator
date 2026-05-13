# Plantilla de aviso legal para emails de outreach

Este es el texto **mínimo** que debe aparecer al pie de cualquier email comercial enviado desde Webcafeína Migrator. Si una plantilla nueva no incluye este bloque íntegro, el `OutreachComposerAgent` la rechaza (validador legal `v1.0`).

## Bloque legal mínimo

```
{{ company_legal_name }} · CIF {{ company_cif }} · {{ company_address }} · {{ company_contact_email }}.
Tratamiento de datos al amparo del art. 6.1.f RGPD (interés legítimo,
contacto B2B). Más info en {{ company_privacy_policy_url }}.

Si prefieres no recibir más mensajes nuestros, ejerce tu derecho de
oposición aquí (un clic, sin trámites): {{ opt_out_url }}
```

## Requisitos LSSI-CE / RGPD aplicados

1. **Identificación del remitente**: razón social completa + CIF + dirección postal completa + email de contacto.
2. **Base jurídica explícita**: mención al art. 6.1.f RGPD (interés legítimo).
3. **Enlace a política de privacidad**: el receptor debe poder consultar el tratamiento completo.
4. **Oposición funcional con un solo clic**: el enlace de opt-out debe procesar la oposición sin pedir login, sin formularios adicionales, y sin preguntar "¿estás seguro?". Un clic → opt-out registrado.
5. **Asunto no engañoso**: la `subject` no debe simular conversación previa con quien nunca la tuvo (no `Re:` sin trato anterior, no `Fwd:`, no `Tu pedido`, etc.).
6. **Una sola CTA primaria** por email. Sin manipulación emocional, sin urgencia falsa.

## Casos de uso

- Email inicial frío: bloque completo arriba.
- Followup tras 5+ días sin respuesta: bloque completo arriba (no se asume que el primero llegó).
- Reactivación de leads inactivos >6 meses: bloque completo + recordatorio explícito de que ya nos comunicamos hace tiempo.

## Variables disponibles en plantillas

| Variable | Origen | Obligatoria |
|---|---|---|
| `business_name` | `lead.business_name` | no |
| `website_url` | `lead.url` | sí |
| `builder_label` | `lead.builder_detected` mapeado | sí |
| `sender_name` | config del agente | sí |
| `company_name` | env `COMPANY_LEGAL_NAME` | sí |
| `company_city` | derivado de `COMPANY_ADDRESS` | sí |
| `company_contact_email` | env `COMPANY_CONTACT_EMAIL` | sí |
| `legal_block` | composición de empresa | sí |
| `opt_out_url` | URL base + token JWT firmado | sí |
| `previous_subject` | solo en followups | no |

Cualquier variable sin valor disparará `StrictUndefined` de Jinja2 — un fallo aquí es un bug, no un email enviado a medias.

## Versionado

Cualquier cambio a esta plantilla incrementa `LEGAL_VALIDATOR_VERSION` en `apps/worker/src/wcm_worker/agents/outreach_composer.py`. Los emails ya enviados quedan trazables a su versión vía `outreach_sequences.legal_validator_version`.
