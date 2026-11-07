"""The cloudflared ingress: the main UI plus one hostname for every branch that asked for one."""

from pathlib import Path
from string import Template

from testbed import naming
from testbed.config import Settings
from testbed.shell import Step, step

TEMPLATE = Path(__file__).resolve().parents[2] / "cloudflare" / "config.yml.template"
CONFIG = "/etc/cloudflared/config.yml"
MAIN_PORT = 8080


def read_env(path: Path) -> dict[str, str]:
    pairs = (line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)
    return {key.strip(): value.strip() for key, value in pairs}


def branch_routes(settings: Settings, add: str | None = None, remove: str | None = None) -> list[tuple[str, int]]:
    routes = {}
    for env_file in sorted(Path(str(settings.worktrees)).glob("*/airflow/.env.branch")):
        values = read_env(env_file)
        if values.get("TUNNEL_HOSTNAME") and values.get("AIRFLOW_PORT"):
            routes[env_file.parent.parent.name] = (values["TUNNEL_HOSTNAME"], int(values["AIRFLOW_PORT"]))
    if remove:
        routes.pop(naming.slug(remove), None)
    if add:
        routes[naming.slug(add)] = (naming.hostname(add, settings.domain), naming.port(add))
    return [routes[key] for key in sorted(routes)]


def render(settings: Settings, routes: list[tuple[str, int]]) -> str:
    if not settings.tunnel_id:
        raise ValueError("set TESTBED_TUNNEL_ID to the id printed by cloudflared tunnel create")
    rules = "".join(f"  - hostname: {host}\n    service: http://localhost:{port}\n" for host, port in routes)
    return Template(TEMPLATE.read_text()).substitute(
        tunnel_id=settings.tunnel_id, domain=settings.domain, main_port=MAIN_PORT, branch_rules=rules
    )


def write_config(settings: Settings, routes: list[tuple[str, int]]) -> Step:
    return step("sudo", "tee", CONFIG, stdin=render(settings, routes), quiet=True)


def route_dns(settings: Settings, host: str) -> Step:
    return step("cloudflared", "tunnel", "route", "dns", "--overwrite-dns", settings.tunnel_id, host)


def restart() -> Step:
    return step("sudo", "systemctl", "restart", "cloudflared")
