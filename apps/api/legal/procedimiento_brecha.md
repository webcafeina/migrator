# Procedimiento ante brecha de seguridad

**Responsable**: Webcafeína S.L.  
**Última actualización**: 2026-05-13.

## 1. Definición de brecha

Toda destrucción, pérdida, alteración, divulgación o acceso no autorizados a datos personales tratados por Webcafeína Migrator. Incluye:

- Acceso a la BD por terceros no autorizados.
- Filtración de credenciales (`.env`, claves Google, JWT secret).
- Pérdida de un backup que contenga `leads`/`opt_out_log`.
- Envío masivo accidental por error en una secuencia.
- Cualquier acceso a la API con un token de operador comprometido.

## 2. Detección

Fuentes que pueden disparar el procedimiento:

- Alerta de Sentry con severidad `ERROR` afectando a `apps.api` o `apps.worker` en endpoints de leads/outreach.
- Alerta manual de un miembro del equipo.
- Notificación de un tercero (cliente afectado, AEPD, partner técnico).
- Anomalía detectada en logs (volúmenes anormales de exports, accesos fuera de horario, etc.).

## 3. Procedimiento (T+0 → T+72h)

### T+0 — Contención (primeros 30 min)

1. **Quien detecta** notifica inmediatamente al **operador de guardia** (canal #seguridad-interno).
2. Operador de guardia eleva al **DPO interno** (Álvaro hasta nombramiento formal).
3. DPO designa el **responsable del incidente** (puede ser él mismo).
4. Responsable del incidente:
   - Revoca tokens potencialmente comprometidos (`UPDATE users SET token_version = token_version + 1`).
   - Rota secrets afectados (JWT_SECRET, GOOGLE_MAPS_API_KEY si aplica).
   - Pausa el worker Celery si el vector de ataque incluye prospección activa: `systemctl stop wcm-worker`.

### T+1h → T+24h — Evaluación

1. Inventariar **qué datos** se vieron afectados (entidades, columnas, número de registros).
2. Identificar **a quién afecta** (lista de leads/emails/usuarios).
3. Documentar el **vector de entrada** (commit, log, IP, momento de inicio).
4. Decidir **gravedad** según escala:
   - **A — alta**: filtración masiva o exposición pública de datos. Notificar AEPD obligatorio.
   - **B — media**: acceso interno indebido sin exfiltración. Notificar AEPD si afecta a >100 titulares.
   - **C — baja**: incidente contenido sin acceso real a datos. No notificable, registrar.

### T+24h → T+72h — Notificación

- Si gravedad A o B con >100 titulares: **notificar a AEPD** vía formulario electrónico antes de 72h desde T+0 (art. 33 RGPD).
- Si gravedad A: **notificar a los titulares afectados** sin dilación indebida (art. 34 RGPD), salvo que existan medidas técnicas que vuelvan los datos ininteligibles.
- Notificar al cliente afectado si la brecha implica un proyecto de migración activo.

## 4. Post-mortem (T+7 días)

- Reunión post-mortem con todos los involucrados.
- Documento blameless: causa raíz, timeline, qué falló en detección, qué falló en respuesta, qué arreglar.
- Tareas correctivas con due date a 30 días en ClickUp.
- Si la causa raíz es código: tests de regresión obligatorios antes de cerrar.

## 5. Registro

Todo incidente queda registrado en `apps/api/legal/registro_incidentes.md` (no versionado en git si contiene datos sensibles — vive en almacenamiento cifrado interno).

## 6. Contactos

- DPO interno: Álvaro · info@webcafeina.com.
- Asesor legal externo: pendiente designación (WCM-LEGAL-001).
- Punto de contacto AEPD: www.aepd.es/derechos-y-deberes/canal-prioritario.
