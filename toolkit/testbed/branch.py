"""Bring a branch stack up, open its UI, and take it down."""

from pathlib import Path

from testbed import naming, stack, tunnel
from testbed.config import Settings
from testbed.shell import Step, step


def branch_env(settings: Settings, branch: str, with_tunnel: bool) -> str:
    values = {
        "TESTBED_BRANCH": branch,
        "AIRFLOW_PORT": naming.port(branch),
        "AIRFLOW_EXECUTOR": "LocalExecutor",
        "SNOWFLAKE_USER": naming.TEST_USER,
        "SNOWFLAKE_ROLE": naming.TEST_ROLE,
        "SNOWFLAKE_WAREHOUSE": naming.TEST_WAREHOUSE,
        "SNOWFLAKE_DATABASE": naming.database(branch),
        "SNOWFLAKE_KEY_PATH": settings.secrets / naming.TEST_KEY_FILE,
    }
    if with_tunnel:
        values["TUNNEL_HOSTNAME"] = naming.hostname(branch, settings.domain)
    return "".join(f"{key}={value}\n" for key, value in values.items())


def tunnel_host(settings: Settings, branch: str) -> str | None:
    env_file = Path(stack.branch_dir(settings, branch)) / ".env.branch"
    return tunnel.read_env(env_file).get("TUNNEL_HOSTNAME") if env_file.exists() else None


def up(settings: Settings, branch: str, with_tunnel: bool) -> list[Step]:
    worktree = stack.worktree(settings, branch)
    database = naming.database(branch)
    remote = f"origin/{branch}"
    checkout = (
        step("git", "-C", worktree, "checkout", "--detach", remote)
        if Path(worktree).exists()
        else step("git", "-C", settings.repo, "worktree", "add", "--detach", worktree, remote)
    )
    steps = [
        step("git", "-C", settings.repo, "fetch", "origin", branch),
        checkout,
        step(
            "tee",
            ".env.branch",
            cwd=stack.branch_dir(settings, branch),
            stdin=branch_env(settings, branch, with_tunnel),
            quiet=True,
        ),
        stack.snowflake_sql(
            settings, branch, f"CALL {naming.PROCEDURES}.CREATE_BRANCH_CLONE('{database}');", naming.TEST_DATABASE
        ),
        stack.branch_compose(settings, branch, "up", "-d", "airflow-scheduler", "airflow-dag-processor"),
    ]
    if with_tunnel:
        steps += [
            tunnel.write_config(settings, tunnel.branch_routes(settings, add=branch)),
            tunnel.route_dns(settings, naming.hostname(branch, settings.domain)),
            tunnel.restart(),
        ]
    return steps


def ui(settings: Settings, branch: str) -> tuple[list[Step], list[str]]:
    port = naming.port(branch)
    notes = [
        f"# UI on the VM: http://127.0.0.1:{port}",
        f"# from a laptop: ssh -N -L {port}:127.0.0.1:{port} <vm>, then open http://localhost:{port}",
    ]
    if host := tunnel_host(settings, branch):
        notes.append(f"# through Cloudflare Access: https://{host}")
    return [stack.branch_compose(settings, branch, "up", "-d", "airflow-api-server")], notes


def down(settings: Settings, branch: str) -> list[Step]:
    database = naming.database(branch)
    steps = [
        stack.snowflake_sql(
            settings, branch, f"CALL {naming.PROCEDURES}.DROP_BRANCH_CLONE('{database}');", naming.TEST_DATABASE
        ),
        stack.branch_compose(settings, branch, "down", "--volumes", "--remove-orphans"),
    ]
    if tunnel_host(settings, branch) and settings.tunnel_id:
        steps += [tunnel.write_config(settings, tunnel.branch_routes(settings, remove=branch)), tunnel.restart()]
    steps.append(step("git", "-C", settings.repo, "worktree", "remove", "--force", stack.worktree(settings, branch)))
    return steps
