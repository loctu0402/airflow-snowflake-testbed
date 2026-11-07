import io
import sys
from pathlib import PurePosixPath

import pytest

from testbed import branch, stack, testing, tunnel
from testbed.config import Settings
from testbed.shell import Runner, step

SETTINGS = Settings(home=PurePosixPath("/opt/testbed"), domain="example.dev", tunnel_id="tunnel-id")


def test_render_is_a_pasteable_shell_line():
    item = step("sudo", "tee", "/etc/x.yml", cwd="/opt/a b", stdin="key: 'v'\n", quiet=True)
    assert item.render() == "cd '/opt/a b' && sudo tee /etc/x.yml > /dev/null <<'EOF'\nkey: 'v'\nEOF"


def test_render_quotes_arguments():
    assert step("echo", "it's", "a b").render() == "echo 'it'\"'\"'s' 'a b'"


def test_branch_compose_uses_its_own_project_and_both_env_files():
    item = stack.branch_compose(SETTINGS, "feature/x", "ps")
    assert item.cwd == "/opt/testbed/worktrees/feature-x/airflow"
    assert item.argv == (
        "docker",
        "compose",
        "-p",
        "testbed-feature-x",
        "--env-file",
        "/opt/testbed/repo/airflow/.env",
        "--env-file",
        ".env.branch",
        "ps",
    )


def test_branch_env_points_the_stack_at_its_clone():
    text = branch.branch_env(SETTINGS, "feature/x", with_tunnel=True)
    assert "SNOWFLAKE_DATABASE=DW_BR_FEATURE_X\n" in text
    assert "SNOWFLAKE_ROLE=TESTER\n" in text
    assert "SNOWFLAKE_KEY_PATH=/opt/testbed/secrets/tester.p8\n" in text
    assert "AIRFLOW_EXECUTOR=LocalExecutor\n" in text
    assert "TUNNEL_HOSTNAME=airflow-feature-x.example.dev\n" in text
    assert "loader" not in text.lower()


def test_branch_up_adds_a_worktree_then_clones_then_starts(tmp_path):
    settings = Settings(home=PurePosixPath(tmp_path.as_posix()), domain="example.dev", tunnel_id=None)
    lines = [item.render() for item in branch.up(settings, "feature/x", with_tunnel=False)]
    assert lines[0] == f"git -C {tmp_path.as_posix()}/repo fetch origin feature/x"
    assert "worktree add --detach" in lines[1]
    assert "CALL OPS.TESTBED.CREATE_BRANCH_CLONE('DW_BR_FEATURE_X');" in lines[3]
    assert "--database DW_TEST" in lines[3]
    assert lines[4].endswith("up -d airflow-scheduler airflow-dag-processor")


def test_branch_up_reuses_an_existing_worktree(tmp_path):
    (tmp_path / "worktrees" / "feature-x").mkdir(parents=True)
    settings = Settings(home=PurePosixPath(tmp_path.as_posix()), domain="example.dev", tunnel_id=None)
    second = branch.up(settings, "feature/x", with_tunnel=False)[1]
    assert second.argv[-3:] == ("checkout", "--detach", "origin/feature/x")


def test_branch_down_drops_the_clone_first_and_the_worktree_last():
    lines = [item.render() for item in branch.down(SETTINGS, "feature/x")]
    assert "DROP_BRANCH_CLONE('DW_BR_FEATURE_X')" in lines[0]
    assert "down --volumes --remove-orphans" in lines[1]
    assert lines[-1] == "git -C /opt/testbed/repo worktree remove --force /opt/testbed/worktrees/feature-x"


def test_tunnel_config_keeps_existing_branches_and_ends_with_a_catch_all(tmp_path):
    other = tmp_path / "worktrees" / "feature-y" / "airflow"
    other.mkdir(parents=True)
    (other / ".env.branch").write_text("AIRFLOW_PORT=8222\nTUNNEL_HOSTNAME=airflow-feature-y.example.dev\n")
    settings = Settings(home=PurePosixPath(tmp_path.as_posix()), domain="example.dev", tunnel_id="abc")
    routes = tunnel.branch_routes(settings, add="feature/x")
    config = tunnel.render(settings, routes)
    assert config.splitlines()[:2] == ["tunnel: abc", "credentials-file: /etc/cloudflared/abc.json"]
    assert "  - hostname: airflow.example.dev\n    service: http://localhost:8080\n" in config
    assert "  - hostname: airflow-feature-y.example.dev\n    service: http://localhost:8222\n" in config
    assert f"service: http://localhost:{branch.naming.port('feature/x')}" in config
    assert config.rstrip().splitlines()[-1] == "  - service: http_status:404"
    assert tunnel.branch_routes(settings, remove="feature/y") == []


def test_tunnel_needs_an_id():
    with pytest.raises(ValueError):
        tunnel.render(Settings(home=PurePosixPath("/opt/testbed"), domain="example.dev", tunnel_id=None), [])


def test_check_tables_compares_branch_with_the_nightly_baseline():
    sql = testing.tables_sql("feature/x", ["pos.orders", "ERP.INVOICES"])
    assert "FROM DW_BR_FEATURE_X.INFORMATION_SCHEMA.TABLES" in sql
    assert "FROM DW_TEST.INFORMATION_SCHEMA.TABLES" in sql
    assert "IN ('POS.ORDERS', 'ERP.INVOICES')" in sql
    with pytest.raises(ValueError):
        testing.tables_sql("feature/x", ["POS.ORDERS') OR 1=1 --"])


def test_runner_stops_at_the_first_failure_and_feeds_stdin():
    out = io.StringIO()
    code = Runner(dry_run=False, out=out).run(
        [
            step(sys.executable, "-c", "import sys; sys.exit(0 if sys.stdin.read() == 'ping' else 9)", stdin="ping"),
            step(sys.executable, "-c", "import sys; sys.exit(3)"),
            step(sys.executable, "-c", "raise SystemExit('never runs')"),
        ]
    )
    assert code == 3
    assert out.getvalue().count("$ ") == 2
    assert "# stopped: exit 3" in out.getvalue()


def test_runner_reports_a_missing_program():
    assert Runner(dry_run=False, out=io.StringIO()).run([step("testbed-no-such-program")]) == 127
