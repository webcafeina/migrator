# 00 — ÍNDICE MAESTRO DE DOCUMENTACIÓN OPERATIVA

> Esta carpeta contiene toda la documentación operativa que necesitas TÚ (humano) para construir y operar Webcafeína Migrator con Claude Code Opus 4.7 en Antigravity.
>
> Estos documentos son tuyos, NO son para Claude Code. Para Claude Code está el archivo separado `CLAUDE_CODE_PROMPT.md`.

---

## Estructura de la documentación

| Documento | Cuándo lo lees | Para qué |
|---|---|---|
| **00 — Índice** | Ahora | Saber dónde está cada cosa |
| **01 — Guía de operación humana** | Antes de empezar | Saber qué haces tú, en qué orden, con qué |
| **02 — Runbook de prerequisitos por fase** | Al inicio de cada fase | Confirmar que tienes lo necesario antes de abrir la sesión |
| **03 — Checklist de revisión del plan** | Cuando Claude Code te muestre el plan en modo plan | Validar el plan antes de aprobarlo |
| **04 — Troubleshooting** | Cuando algo falle | Resolver problemas comunes rápidamente |
| **05 — Glosario y referencia rápida** | Cuando dudes algo concreto | Buscar IDs, comandos, rutas, convenciones |
| **CLAUDE_CODE_PROMPT.md** | Una sola vez al inicio | Pegar como primer mensaje en Claude Code |

---

## Flujo recomendado

### Día 1 — Preparación

1. Lee **01 — Guía de operación humana** completa
2. Lee **05 — Glosario y referencia rápida** para familiarizarte
3. Empieza a conseguir credenciales/cuentas listadas en sección 0.1 del documento 01
4. Verifica software local (sección 0.2 del documento 01)
5. Prepara la sandbox WordPress (sección 0.4 del documento 01)

### Día 2 — Bootstrap

1. Lee **02 — Runbook**, sección Fase 0
2. Confirma que tienes los prerequisitos de Fase 0
3. Abre Antigravity en carpeta vacía
4. Pega `CLAUDE_CODE_PROMPT.md` en modo plan
5. Espera plan generado
6. Revisa con **03 — Checklist de revisión del plan**
7. Aprueba o pide ajustes
8. Ejecuta Fase 0
9. Revisa output según sección "Qué obtendrás" y "Qué revisas" del documento 02
10. Commit + push

### Día 3 en adelante — Por fase

1. Sesión nueva en Antigravity
2. Lee sección de la fase correspondiente en **02 — Runbook**
3. Confirma prerequisitos humanos
4. Inicia sesión con mensaje "Lee CLAUDE.md y STATE.md. Genera plan SOLO de Fase X"
5. Revisa plan con **03 — Checklist**
6. Aprueba, ejecuta, revisa, commit, push
7. Si algo falla, consulta **04 — Troubleshooting**
8. Si dudas algo concreto, consulta **05 — Glosario**

---

## Documentos que se crearán DENTRO del repo durante la construcción

Estos los genera Claude Code automáticamente, NO los crees tú:

| Archivo en el repo | Cuándo |
|---|---|
| `CLAUDE.md` | Fase 0 |
| `STATE.md` | Fase 0, actualizado en cada fase |
| `README.md` | Fase 0 |
| `docs/decisiones.md` | Fase 0, actualizado durante construcción |
| `docs/arquitectura.md` | Fase 14 |
| `docs/prospeccion.md` | Fase 14 |
| `docs/migracion.md` | Fase 14 |
| `docs/despliegue.md` | Fase 14 |
| `docs/playbook-operativo.md` | Fase 14 |
| `docs/troubleshooting.md` | Fase 14 (versión técnica, distinta del documento 04 que es operativo) |

---

## Mantenimiento de esta documentación

Estos documentos (00-05) son tuyos. Mantenlos actualizados a mano cuando:

- Cambies decisiones de stack
- Añadas nuevos servicios externos
- Identifiques nuevos problemas comunes
- El equipo crezca o cambien responsables
- Cambien IDs de ClickUp, dominios, etc.

Sugerencia: guarda esta carpeta dentro del repo en `docs/operativos-humanos/` o fuera del repo en tu Drive personal del equipo, según prefieras visibilidad pública o privada.
