"""testbed: run Airflow branches against a zero-copy clone of production, with or without the UI."""

import argparse

from testbed import branch, prereqs, testing
from testbed.config import Settings
from testbed.deploy import deploy
from testbed.shell import Runner


def build_parser() -> argparse.ArgumentParser:
    dry_run_help = "print the commands, run nothing"
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS, help=dry_run_help)
    parser = argparse.ArgumentParser(prog="testbed", description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help=dry_run_help)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("setup", parents=[common], help="check and install VM prerequisites, publish the main UI")

    branches = commands.add_parser("branch", help="branch stacks").add_subparsers(dest="action", required=True)
    up = branches.add_parser("up", parents=[common], help="worktree, compose project, Snowflake clone")
    up.add_argument("--tunnel", action="store_true", help="publish the branch UI on its own hostname")
    ui = branches.add_parser("ui", parents=[common], help="start the branch UI and print where to open it")
    down = branches.add_parser("down", parents=[common], help="drop the clone, stop the stack, remove the worktree")
    for sub in (up, ui, down):
        sub.add_argument("branch")

    tests = commands.add_parser("test", help="run without the UI").add_subparsers(dest="action", required=True)
    task = tests.add_parser("task", parents=[common], help="airflow tasks test in the branch stack")
    task.add_argument("dag_id")
    task.add_argument("task_id")
    dag = tests.add_parser("dag", parents=[common], help="airflow dags test in the branch stack")
    dag.add_argument("dag_id")
    for sub in (task, dag):
        sub.add_argument("--branch", required=True)
        sub.add_argument("--date", default=None, help="logical date, YYYY-MM-DD, yesterday by default")

    checks = commands.add_parser("check", help="read-only checks").add_subparsers(dest="action", required=True)
    tables = checks.add_parser("tables", parents=[common], help="row count and freshness, branch against DW_TEST")
    tables.add_argument("tables", nargs="+", metavar="SCHEMA.TABLE")
    tables.add_argument("--branch", required=True)

    commands.add_parser("deploy", parents=[common], help="fast-forward main on the VM, reserialize, list import errors")
    return parser


def dispatch(args: argparse.Namespace, settings: Settings, runner: Runner) -> int:
    match args.command, getattr(args, "action", None):
        case "setup", _:
            return prereqs.setup(settings, runner)
        case "branch", "up":
            return runner.run(branch.up(settings, args.branch, args.tunnel))
        case "branch", "ui":
            steps, notes = branch.ui(settings, args.branch)
            code = runner.run(steps)
            for note in notes:
                runner.say(note)
            return code
        case "branch", "down":
            return runner.run(branch.down(settings, args.branch))
        case "test", "task":
            return runner.run(
                testing.task(settings, args.branch, args.dag_id, args.task_id, args.date or testing.yesterday())
            )
        case "test", "dag":
            return runner.run(testing.dag(settings, args.branch, args.dag_id, args.date or testing.yesterday()))
        case "check", "tables":
            return runner.run(testing.check_tables(settings, args.branch, args.tables))
        case "deploy", _:
            return deploy(settings, runner)
    raise ValueError(f"unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return dispatch(args, Settings.from_env(), Runner(dry_run=args.dry_run))
    except ValueError as error:
        parser.error(str(error))
