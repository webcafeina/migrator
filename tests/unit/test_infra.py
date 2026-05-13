"""Validación de los artefactos de infra (Fase 12):
- bash -n para todos los scripts
- systemd units mínimamente válidos (configparser)
- nginx vhosts: presencia de secciones críticas
- workflows YAML parseables
"""

from __future__ import annotations

import configparser
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INFRA = REPO_ROOT / "infra"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"


# ---------- Bash syntax ----------

@pytest.mark.parametrize("script", sorted(INFRA.glob("**/*.sh")), ids=lambda p: p.name)
def test_bash_syntax_valid(script: Path) -> None:
    """`bash -n` debe pasar para cada script."""
    result = subprocess.run(
        ["bash", "-n", str(script)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"bash -n falló en {script}:\n{result.stderr}"


# ---------- systemd units ----------

@pytest.mark.parametrize(
    "unit",
    sorted(INFRA.glob("systemd/wcm-*.service")) + [INFRA / "systemd/wcm.target"],
    ids=lambda p: p.name,
)
def test_systemd_unit_has_required_sections(unit: Path) -> None:
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.read(unit)
    assert "Unit" in parser, f"{unit.name} falta [Unit]"
    assert "Install" in parser, f"{unit.name} falta [Install]"


@pytest.mark.parametrize(
    "service",
    sorted(INFRA.glob("systemd/wcm-*.service")),
    ids=lambda p: p.name,
)
def test_systemd_services_have_hardening(service: Path) -> None:
    """Cada .service debe declarar mínimo:
    NoNewPrivileges, ProtectSystem, PrivateTmp.
    """
    content = service.read_text()
    for directive in ("NoNewPrivileges=true", "ProtectSystem=", "PrivateTmp=true"):
        assert directive in content, f"{service.name} falta {directive}"


def test_systemd_services_reference_existing_env_file_path() -> None:
    """EnvironmentFile debe apuntar a `${WCM_APP_DIR}/.env` (no a /etc/...)."""
    for service in INFRA.glob("systemd/wcm-*.service"):
        content = service.read_text()
        if "EnvironmentFile=" in content:
            assert "${WCM_APP_DIR}/.env" in content, f"{service.name} EnvironmentFile mal"


# ---------- nginx ----------

def test_nginx_common_snippet_has_security_headers() -> None:
    snippet = (INFRA / "nginx/wcm-common.conf").read_text()
    for header in (
        "Strict-Transport-Security",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Content-Security-Policy",
    ):
        assert header in snippet, f"snippet falta {header}"


@pytest.mark.parametrize(
    "vhost",
    sorted(INFRA.glob("nginx/*.conf")) and [
        p for p in INFRA.glob("nginx/*.conf") if "common" not in p.name
    ],
    ids=lambda p: p.name,
)
def test_nginx_vhost_has_https_redirect_and_upstream(vhost: Path) -> None:
    content = vhost.read_text()
    assert "listen 80" in content, f"{vhost.name} no escucha HTTP (no hay redirect)"
    assert "return 301 https" in content, f"{vhost.name} no redirige a HTTPS"
    assert "ssl_certificate" in content, f"{vhost.name} no declara cert SSL"
    assert "include snippets/wcm-common.conf" in content, (
        f"{vhost.name} no incluye el snippet común de headers"
    )


def test_api_vhost_restricts_metrics() -> None:
    """`/metrics` no debe ser público — debe tener ACL `deny all`."""
    api_vhost = INFRA / "nginx/api.migrator.webcafeina.com.conf"
    content = api_vhost.read_text()
    # Buscamos el bloque /metrics y verificamos que tiene deny all.
    assert "location = /metrics" in content
    metrics_block_start = content.index("location = /metrics")
    metrics_block_end = content.index("}", metrics_block_start)
    block = content[metrics_block_start:metrics_block_end]
    assert "deny all" in block, "/metrics debe denegar acceso público"
    assert "allow 127.0.0.1" in block


def test_api_vhost_restricts_health_deep() -> None:
    api_vhost = INFRA / "nginx/api.migrator.webcafeina.com.conf"
    content = api_vhost.read_text()
    assert "location = /health/deep" in content
    health_idx = content.index("location = /health/deep")
    block = content[health_idx : content.index("}", health_idx)]
    assert "deny all" in block
    assert "allow 127.0.0.1" in block


# ---------- GitHub workflows ----------

def test_workflows_are_valid_yaml() -> None:
    yaml = pytest.importorskip("yaml")
    for wf in WORKFLOWS.glob("*.yml"):
        with wf.open() as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict), f"{wf.name} no parsea a dict"
        # GitHub Actions YAML serializa `on` como True (boolean) en pyyaml
        # por defecto. Aceptamos cualquiera de los dos.
        assert "on" in data or True in data, f"{wf.name} falta `on:`"
        assert "jobs" in data, f"{wf.name} falta `jobs:`"


def test_ci_workflow_runs_python_and_ts_jobs() -> None:
    yaml = pytest.importorskip("yaml")
    ci = WORKFLOWS / "ci.yml"
    data = yaml.safe_load(ci.read_text())
    jobs = set(data["jobs"].keys())
    assert {"python", "typescript", "infra"}.issubset(jobs), (
        f"ci.yml debe definir python/typescript/infra. Tiene: {jobs}"
    )


# ---------- Deploy scripts coherentes ----------

def test_deploy_scripts_are_executable() -> None:
    """Los .sh de infra deben tener bit ejecutable (operacional, no test)."""
    for script in INFRA.glob("**/*.sh"):
        mode = script.stat().st_mode
        assert mode & 0o111, f"{script} no es ejecutable"


def test_deploy_script_uses_set_euo_pipefail() -> None:
    """Los scripts críticos deben fallar rápido (set -euo pipefail)."""
    critical = [
        INFRA / "deploy/deploy.sh",
        INFRA / "deploy/rollback.sh",
        INFRA / "deploy/migrate.sh",
        INFRA / "deploy/health-check.sh",
        INFRA / "whm-setup/01-system-prereqs.sh",
        INFRA / "whm-setup/02-database.sh",
        INFRA / "whm-setup/03-install-units.sh",
        INFRA / "whm-setup/04-install-nginx.sh",
        INFRA / "whm-setup/05-init-env.sh",
    ]
    for script in critical:
        content = script.read_text()
        assert "set -euo pipefail" in content, (
            f"{script.name} debe declarar set -euo pipefail"
        )
