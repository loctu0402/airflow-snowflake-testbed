"""Check the VM for what the toolkit needs, install what is missing, and publish the main UI."""

import getpass
import platform

from testbed import tunnel
from testbed.config import Settings
from testbed.shell import Runner, Step, step

ARCH = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}
CLOUDFLARED = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{arch}.deb"


def checks(settings: Settings, user: str, arch: str) -> list[tuple[str, Step, list[Step]]]:
    apt = ("sudo", "apt-get", "install", "-y")
    return [
        ("git", step("git", "--version"), [step(*apt, "git")]),
        (
            "docker",
            step("docker", "info"),
            [
                step("sudo", "apt-get", "update"),
                step(*apt, "docker.io", "docker-compose-v2"),
                step("sudo", "usermod", "-aG", "docker", user),
            ],
        ),
        ("docker compose", step("docker", "compose", "version"), [step(*apt, "docker-compose-v2")]),
        (
            "cloudflared",
            step("cloudflared", "--version"),
            [
                step("curl", "-fsSL", "-o", "/tmp/cloudflared.deb", CLOUDFLARED.format(arch=arch)),
                step("sudo", "dpkg", "-i", "/tmp/cloudflared.deb"),
            ],
        ),
        (
            "folders",
            step("test", "-d", settings.worktrees),
            [
                step("sudo", "mkdir", "-p", settings.worktrees, settings.secrets),
                step("sudo", "chown", f"{user}:{user}", settings.home, settings.worktrees, settings.secrets),
                step("chmod", "700", settings.secrets),
            ],
        ),
    ]


def ensure(runner: Runner, name: str, check: Step, install: list[Step]) -> int:
    if runner.dry_run:
        runner.say(f"# {name}: check, then install when missing")
        runner.say("$ " + check.render())
        return runner.run(install)
    if runner.succeeds(check):
        runner.say(f"# {name}: ok")
        return 0
    runner.say(f"# {name}: missing, installing")
    return runner.run(install)


def setup(settings: Settings, runner: Runner, user: str | None = None, arch: str | None = None) -> int:
    user = user or getpass.getuser()
    arch = arch or ARCH.get(platform.machine().lower(), "amd64")
    for name, check, install in checks(settings, user, arch):
        if code := ensure(runner, name, check, install):
            return code
    if not settings.tunnel_id:
        runner.say("# tunnel: skipped, set TESTBED_TUNNEL_ID to publish the UI through Cloudflare")
        return 0
    code = runner.run(
        [
            tunnel.write_config(settings, tunnel.branch_routes(settings)),
            tunnel.route_dns(settings, f"airflow.{settings.domain}"),
        ]
    )
    if code:
        return code
    service = step("systemctl", "is-enabled", "--quiet", "cloudflared")
    code = ensure(runner, "cloudflared service", service, [step("sudo", "cloudflared", "service", "install")])
    return code or runner.run([tunnel.restart()])
