"""Fast-forward the VM's checkout to main, reserialize the DAGs, and fail on any import error."""

from testbed import stack
from testbed.config import Settings
from testbed.shell import Runner, step


def deploy(settings: Settings, runner: Runner) -> int:
    repo = settings.repo
    code, branch = runner.capture(step("git", "-C", repo, "branch", "--show-current"))
    if code:
        return code
    if not runner.dry_run and branch.strip() != "main":
        runner.say(f"# refused: the VM checkout is on {branch.strip() or 'a detached HEAD'}, not main")
        return 1
    code, changes = runner.capture(step("git", "-C", repo, "status", "--porcelain"))
    if code:
        return code
    if changes.strip():
        runner.say("# refused: the VM checkout has local changes, move them into a pull request")
        runner.say(changes.rstrip())
        return 1
    code = runner.run(
        [
            step("git", "-C", repo, "fetch", "origin", "main"),
            step("git", "-C", repo, "merge", "--ff-only", "origin/main"),
            stack.main_compose(settings, "exec", "-T", "airflow-scheduler", "airflow", "dags", "reserialize"),
            stack.main_compose(settings, "exec", "-T", "airflow-scheduler", "airflow", "dags", "list-import-errors"),
        ]
    )
    if code:
        return code
    code, head = runner.capture(step("git", "-C", repo, "rev-parse", "--short", "HEAD"))
    if not runner.dry_run:
        runner.say(f"# deployed {head.strip()}, no import errors")
    return code
