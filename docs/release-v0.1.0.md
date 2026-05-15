# Release v0.1.0 — instrucciones de publicación

> Documento dirigido al **equipo Webcafeína** (quien tenga permisos en `github.com/webcafeina`). Pasos para llevar el repo local a GitHub y publicar el tag `v0.1.0`.

---

## 0. Pre-flight check (ya hecho automáticamente)

```bash
cd /Users/alvaro/Desktop/webcafeina-migrator

# Tests verdes
venv/bin/python -m pytest -q --tb=no
# → 387 passed + 10 skipped

# Coverage
venv/bin/python -m pytest -q --cov --cov-fail-under=70 --tb=no
# → > 70% threshold cumplido

# Dashboard
cd apps/dashboard && pnpm type-check && pnpm test && cd ../..
# → tsc clean + 15/15 vitest

# Audit
venv/bin/pip-audit --skip-editable    # → No vulnerabilities
pnpm audit --prod                       # → No vulnerabilities (tras postcss override)

# Sin secretos en git
grep -rE "(JWT_SECRET|SECRET_KEY|API_KEY)\s*=\s*['\"][A-Za-z0-9]{8,}" \
    --include="*.py" --include="*.ts" .   # → 0 hits
```

Estado del repo local:

```bash
git log --oneline | head -3
# d1b2b86 docs: arquitectura + flows + playbook operativo
# f0b1ea0 chore(state): record Fase 12 commit SHA
# ...
```

---

## 1. Decidir nombre y visibilidad del repo

Necesito tu decisión sobre:

- **Org / cuenta**: `@webcafeina` (org) o tu cuenta personal `@alvaro-...`. Recomendado: org.
- **Nombre**: `migrator` (corto) vs `webcafeina-migrator` (descriptivo).
- **Visibilidad**: `private` (recomendado — herramienta interna) vs `internal` (org Enterprise) vs `public`.

Por defecto a continuación asumo: `webcafeina/migrator` **privado**.

---

## 2. Crear el repo en GitHub

### Opción A — vía web

1. Login en GitHub con la cuenta admin de la org.
2. https://github.com/organizations/webcafeina/repositories/new
3. Nombre: `migrator`. Description: "Webcafeína Migrator — herramienta interna de prospección + migración WP".
4. **Private**. NO inicializar con README / .gitignore / license (ya están localmente).
5. Click **Create repository**.

### Opción B — vía `gh` CLI

```bash
gh repo create webcafeina/migrator --private \
    --description "Webcafeína Migrator — herramienta interna de prospección + migración WP"
```

---

## 3. Conectar el repo local al remote

```bash
cd /Users/alvaro/Desktop/webcafeina-migrator
git remote add origin git@github.com:webcafeina/migrator.git
git branch -M main   # asegurar que la rama principal se llama main
```

---

## 4. Primer push

```bash
# Sanity check del remote
git remote -v
# origin  git@github.com:webcafeina/migrator.git (fetch)
# origin  git@github.com:webcafeina/migrator.git (push)

# Push de main + tags
git push -u origin main
git push origin --tags    # incluye v0.1.0 cuando esté creado (paso 5)
```

Si el push falla por tamaño (>100 MB en algún fichero):

```bash
# Detectar ficheros grandes
git ls-files | xargs -I {} ls -la {} 2>/dev/null | sort -k5 -n -r | head -10
```

(No debería haber problema — `node_modules`, `venv`, `.next` están todos gitignored.)

---

## 5. Crear el tag v0.1.0

**Después** del primer push (los tags incluyen el SHA del commit, y queremos que ese commit ya esté en GitHub):

```bash
git tag -a v0.1.0 -m "$(cat <<'EOF'
Webcafeína Migrator v0.1.0 — primer release MVP

Cubre las 16 fases de construcción (0–15):
- Prospección comercial RGPD/LSSI-CE compliant
- Migración Wix/Hostinger AI/Webflow → WP+Bricks (15 fases pipeline)
- Dashboard Next.js 15 + CLI Typer + API FastAPI + Celery worker
- Observabilidad Sentry/structlog/Logtail/Prometheus
- Infra systemd nativo + Nginx + scripts WHM idempotentes
- 387 tests Python + 15 TS + 8 Playwright (coverage 74.8%)
- 33 ADRs documentando todas las decisiones

Ver CHANGELOG.md para detalle completo.
EOF
)"

git push origin v0.1.0
```

---

## 6. Activar branch protection en `main`

Una vez en GitHub:

1. **Settings → Branches → Add rule** para `main`.
2. Marcar:
   - [x] Require a pull request before merging.
   - [x] Require approvals: 1.
   - [x] Require status checks to pass: `python (3.14)`, `typescript (22)`, `infra`, `e2e`.
   - [x] Require branches to be up to date before merging.
   - [x] Require linear history (sin merge commits).
   - [x] Do not allow bypassing.

---

## 7. Configurar secrets de GitHub para CI/CD

**Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Valor | Usado por |
|---|---|---|
| `DEPLOY_HOST` | IP / FQDN del servidor WHM | `deploy-production.yml` |
| `DEPLOY_USER` | `webcafeina` (o usuario sistema) | `deploy-production.yml` |
| `DEPLOY_SSH_KEY` | clave privada SSH del runner | `deploy-production.yml` |

Para tests opcionales en CI:
| Secret | Valor | Usado por |
|---|---|---|
| `CODECOV_TOKEN` | token de codecov.io | upload de `coverage.xml` (futuro) |

---

## 8. Crear el release en GitHub

```bash
gh release create v0.1.0 \
    --title "v0.1.0 — primer MVP" \
    --notes-file CHANGELOG.md \
    --verify-tag
```

O vía web: **Releases → Create a new release → tag v0.1.0**.

---

## 9. Verificar que CI corre verde

Tras el push:

1. https://github.com/webcafeina/migrator/actions → debería haber arrancado `CI`.
2. Esperar a que terminen los 4 jobs (python × 2, typescript × 2, infra, e2e).
3. Tiempo estimado total: ~10 min.

Si algún job falla:
- `python (3.13)` puede fallar si alguna dep no soporta 3.13 — investigar y decidir si quitar 3.13 de la matrix.
- `e2e` puede fallar la primera vez porque Playwright no tiene snapshots x64. Re-ejecutar con `--update-snapshots` desde una run manual.

---

## 10. Equipo

Añadir al equipo Webcafeína en **Settings → Collaborators and teams**. Convención: **sin roles individuales** — todo el equipo se gestiona como una unidad con los permisos que corresponda al uso del repo (admin para los que necesiten publicar releases / mergear, write para el resto). Cualquier cambio puede hacerlo cualquier miembro del equipo; no hay assignees personales en el código.

---

## 11. Post-release

Una vez todo verde:

1. Actualizar `STATE.md` con el SHA del tag.
2. Notificar al equipo Webcafeína por el canal habitual.
3. Empezar a planificar la roadmap post-v0.1.0 (ver `ISSUES.md` WCM-011 a WCM-020).

---

**Tiempo total estimado de los pasos 1-9: 30-60 minutos**, dependiendo de problemas de SSH/auth en GitHub.
