# Tratamiento de datos para prospección comercial

**Responsable**: Webcafeína S.L. (CIF B10463990), Santa Cristina, s/n – Edificio Embarcadero, 10195 Cáceres. Email: info@webcafeina.com.

**Última actualización**: 2026-05-13.

## 1. Datos tratados

- **Dato profesional**: razón social, nombre comercial, URL de la web pública del negocio, dirección postal pública, teléfono profesional publicado, email profesional publicado (`info@`, `hola@`, etc.), redes sociales profesionales públicas.
- **Datos técnicos derivados**: tecnología detectada en la web (builder, framework, plugins visibles), estimaciones públicas de tráfico/empleados/sector.
- **NO se tratan**: datos personales de empleados individuales (nombres + apellidos sin función pública), datos de salud, ideología, opiniones políticas, ni ninguna categoría especial del art. 9 RGPD.

## 2. Origen de los datos

- Google Maps Places API legacy (operador: Google Ireland Limited).
- HTML público de la web del propio negocio.
- Directorios públicos (Páginas Amarillas, etc.) — pendiente activación, Fase 9+.

Toda fuente debe ser pública. No se compran bases de datos.

## 3. Finalidad

Contactar al negocio para ofrecerle un servicio de migración técnica de su web actual (Wix/Hostinger AI/Webflow → WordPress + Bricks). El contacto se realiza por canal email profesional B2B.

## 4. Base jurídica

**Art. 6.1.f RGPD — interés legítimo del responsable**. En la ponderación:

- **Interés legítimo de Webcafeína**: prospección comercial B2B, actividad económica habitual y necesaria del responsable como agencia digital.
- **Derechos del titular**: el dato tratado es exclusivamente profesional y publicado por el propio negocio para fines de contacto comercial. No invade ámbito personal/privado.
- **Salvaguardas**: oposición funcional con un solo clic; sin perfilado automatizado con efectos jurídicos; retención limitada (ver §6); sin envío masivo automatizado (cada outreach requiere revisión humana antes de enviar).

Concordancia con **art. 21.2 LSSI-CE**: la comunicación se considera comercial dirigida a un profesional sobre productos o servicios relacionados con su actividad, lo que habilita el contacto incluso por correo electrónico sin consentimiento previo.

## 5. Destinatarios

- Operadores internos de Webcafeína (equipo comercial y técnico).
- Encargados del tratamiento bajo contrato (Cloudflare R2 — almacenamiento de assets; Resend Inc. — envío email transaccional; Sentry — observabilidad). Todos con DPA firmado.
- No se ceden datos a terceros para fines comerciales propios de esos terceros.

## 6. Plazo de conservación

- **Lead activo (no contactado)**: 12 meses desde su descubrimiento. Si no se ha generado outreach pasados 12 meses, se borra del CRM interno (estado `DISCARDED`).
- **Lead contactado sin respuesta**: 24 meses desde el último intento de contacto.
- **Lead opt-out**: el lead se elimina, pero el email queda en `opt_out_log` **indefinidamente** como base jurídica para no recontactar. La conservación de este log se ampara también en el interés legítimo: evitar recontactos no deseados.
- **Lead convertido a cliente**: pasa a la relación contractual; aplican los plazos del contrato firmado, no este documento.

## 7. Derechos del titular

El titular puede ejercer ante info@webcafeina.com los siguientes derechos:

- **Acceso, rectificación, supresión, oposición, limitación, portabilidad** (arts. 15–22 RGPD).
- En cada email de outreach se incluye un **enlace de oposición funcional con un solo clic**. Al pulsarlo, el lead se elimina automáticamente del CRM y el email queda registrado en `opt_out_log` para evitar recontactos.
- Reclamación ante la **Agencia Española de Protección de Datos** (www.aepd.es).

## 8. Decisiones automatizadas

No se toman decisiones automatizadas con efectos jurídicos sobre los titulares. El sistema **clasifica** y **prioriza** leads (fingerprint, score, embedding semántico), pero todo envío de outreach pasa por revisión humana explícita (estado `DRAFT_PENDING_REVIEW` → operador → `READY`).

## 9. Transferencias internacionales

- Google Places API: tratamiento en EEUU bajo cláusulas tipo de la CE / Data Privacy Framework.
- Resend: tratamiento en EEUU bajo cláusulas tipo de la CE / DPF.
- Cloudflare R2: tratamiento en EEUU/EEE bajo cláusulas tipo CE / DPF.

## 10. Política revisada por

Pendiente de revisión por asesor legal externo antes de paso a producción (WCM-LEGAL-001 en `ISSUES.md`).
