"""Docker Compose steps for the main stack and for each branch stack."""

from testbed import naming
from testbed.config import Settings
from testbed.shell import Step, step

RUN_SQL = "/opt/airflow/scripts/run_sql.py"


def main_dir(settings: Settings) -> str:
    return str(settings.repo / "airflow")


def worktree(settings: Settings, branch: str) -> str:
    return str(settings.worktrees / naming.slug(branch))


def branch_dir(settings: Settings, branch: str) -> str:
    return f"{worktree(settings, branch)}/airflow"


def main_compose(settings: Settings, *args) -> Step:
    return step("docker", "compose", *args, cwd=main_dir(settings))


def branch_compose(settings: Settings, branch: str, *args, stdin=None) -> Step:
    return step(
        "docker",
        "compose",
        "-p",
        naming.project(branch),
        "--env-file",
        f"{main_dir(settings)}/.env",
        "--env-file",
        ".env.branch",
        *args,
        cwd=branch_dir(settings, branch),
        stdin=stdin,
    )


def snowflake_sql(settings: Settings, branch: str, sql: str, database: str) -> Step:
    return branch_compose(
        settings,
        branch,
        "run",
        "--rm",
        "--no-deps",
        "-T",
        "airflow-cli",
        "python",
        RUN_SQL,
        "--database",
        database,
        stdin=sql,
    )
