---
name: gdpr-compliance
description: Plantillas y funciones de cumplimiento legal — RGPD + LSSI-CE — para prospección, enriquecimiento y outreach. Define bases jurídicas, registros de tratamiento, opt-out funcional, retención de datos y plantillas de mensaje legal obligatorio en outreach.
---

# Skill — GDPR Compliance

## Propósito

Toda función que toque datos personales o envío de comunicaciones comerciales debe pasar por aquí. Sin excepción.

## Marco normativo aplicable

- **RGPD** (UE 2016/679): tratamiento de datos personales
- **LOPDGDD** (España, LO 3/2018): desarrollo nacional de RGPD
- **LSSI-CE** (Ley 34/2002): comunicaciones comerciales electrónicas
- **ePrivacy** (cookies, comunicaciones)

## Bases jurídicas aplicadas

| Operación | Base | Artículo |
|---|---|---|
| Descubrimiento de lead (URL pública) | Interés legítimo del responsable | 6.1.f RGPD |
| Enriquecimiento con datos públicos profesionales | Interés legítimo | 6.1.f RGPD |
| Outreach comercial B2B inicial | Interés legítimo | 6.1.f RGPD + art. 21 LSSI-CE (relación profesional) |
| Continuación de comunicación tras respuesta | Consentimiento | 6.1.a RGPD |
| Tratamiento durante migración de web cliente | Contrato | 6.1.b RGPD |

> Para outreach a personas físicas (autónomos individualizados), el régimen es más estricto: **consentimiento explícito previo** (no interés legítimo).

## Contrato

```python
class GdprCompliance:
    def record_treatment(
        self,
        lead_id: int,
        legal_ground: LegalGround,
        data_categories: list[str],
        purpose: str,
        evidence: str,
    ) -> None:
        """Insert en audit_log + lead_enrichments.legal_grounds."""

    def record_consent(self, lead_id: int, channel: str, evidence: str) -> None:
        """Lead consintió explícitamente. Upgrade base jurídica → 6.1.a."""

    def process_opt_out(self, email: str | None = None, lead_id: int | None = None) -> None:
        """Elimina lead + enrichments + sequences. Persiste opt-out con timestamp en opt_out_log."""

    def is_opted_out(self, email: str) -> bool: ...

    def build_legal_footer(self, language: str = "es") -> str:
        """Devuelve bloque legal a inyectar al final de outreach."""

    def validate_outreach_email(self, body: str, lead: Lead) -> ValidationResult:
        """Asegura que el cuerpo incluye todos los elementos obligatorios."""
```

## Elementos obligatorios en outreach LSSI-CE

Cada email saliente debe incluir:

1. **Identificación del remitente**: nombre legal Webcafeína S.L., CIF, dirección postal, email de contacto.
2. **Motivo del contacto**: explícito, sin ambigüedad.
3. **Base jurídica**: mención al interés legítimo y oportunidad de objeción.
4. **Mecanismo de baja**: link `opt-out` funcional, en cada mensaje, en posición visible (no escondido en footer minúsculo).
5. **Política de privacidad**: link a URL estable.

`build_legal_footer("es")` devuelve:

```
---
Le escribe Webcafeína S.L. (CIF: {COMPANY_CIF}, {COMPANY_ADDRESS}).
Le contactamos al amparo del art. 6.1.f RGPD (interés legítimo) y art. 21
LSSI-CE tras identificar públicamente que su empresa opera en {sector} en
{región}, contexto en el que nuestros servicios pueden resultarle de
interés profesional. Si no desea recibir más comunicaciones, puede darse
de baja con un clic: {OPT_OUT_URL}. Tratamiento de datos: política
disponible en {PRIVACY_URL}. Datos de contacto del responsable:
{CONTACT_EMAIL}.
```

## Opt-out funcional

- URL: `{OPT_OUT_URL_BASE}?token={signed_token}` (token firmado JWT con `email` + `lead_id` + `iat`).
- Endpoint API `GET /opt-out` valida el token, elimina lead, registra en `opt_out_log(email, timestamp, evidence)`.
- Página de confirmación: "Has sido eliminado de nuestra base de contactos. No volverás a recibir comunicaciones de Webcafeína." (Sin formulario, sin tracking, sin re-suscripción inmediata.)

## Retención de datos

| Tipo de dato | TTL |
|---|---|
| Lead descubierto sin acción | 12 meses tras última actividad |
| Lead con outreach iniciado, sin respuesta | 12 meses tras último envío |
| Lead con respuesta positiva → convertido a proyecto | sin límite (relación contractual) |
| Opt-out log | indefinido (legitimación para no recontactar) |

Job Celery `purge_expired_leads` semanal: aplica TTL.

## Documentos generados en `apps/api/legal/`

(Se generan en Fase 9, no en bootstrap):

- `tratamiento_datos_prospeccion.md` — Registro RGPD art. 30
- `plantilla_aviso_legal_outreach.md` — Texto base outreach
- `politica_retencion.md` — TTLs y procesos de purga
- `procedimiento_brecha.md` — Plan en caso de brecha (notificación AEPD en 72 h)

## Bandera de cumplimiento

Cada `outreach_sequences.steps_json[step]` que pasa por aquí lleva:
```json
{
  "legal_validation": {
    "passed": true,
    "validator_version": "v1.0",
    "validated_at": "2026-..."
  }
}
```

Si `passed=false`, la secuencia NO se persiste como `status="ready"`.

## Tests

- Validación de plantillas con variables faltantes → error
- Opt-out: token firmado debe verificar correctamente, expiración no aplicable (los opt-out no caducan)
- Purga: integration test creando leads con `created_at` simulado del pasado

## Dependencias

- `pyjwt` para tokens firmados
- `python-dateutil` para cálculos TTL
