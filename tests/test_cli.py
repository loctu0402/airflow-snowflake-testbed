import platform
import subprocess

import pytest

from testbed.cli import main


@pytest.fixture(autouse=True)
def vm(monkeypatch):
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")
    monkeypatch.setenv("TESTBED_HOME", "/opt/testbed")
    monkeypatch.setenv("TESTBED_DOMAIN", "example.dev")
    monkeypatch.setenv("TESTBED_TUNNEL_ID", "6f1c2c1e-0000-4000-8000-000000000000")

    def refuse(*args, **kwargs):
        raise AssertionError(f"dry run executed {args}")

    monkeypatch.setattr(subprocess, "run", refuse)


def dry(capsys, *argv):
    assert main(["--dry-run", *argv]) == 0
    lines = capsys.readouterr().out.splitlines()
    commands = [line for line in lines if line.startswith(("$ ", "# "))]
    assert commands
    return "\n".join(lines)


def test_setup(capsys):
    out = dry(capsys, "setup")
    assert "$ docker info" in out
    assert "$ sudo apt-get install -y docker.io docker-compose-v2" in out
    assert "$ sudo tee /etc/cloudflared/config.yml > /dev/null <<'EOF'" in out
    assert (
        "cloudflared tunnel route dns --overwrite-dns 6f1c2c1e-0000-4000-8000-000000000000 airflow.example.dev" in out
    )
    assert "$ sudo systemctl restart cloudflared" in out


def test_branch_up_with_tunnel(capsys):
    out = dry(capsys, "branch", "up", "feature/pos-refunds", "--tunnel")
    assert "$ git -C /opt/testbed/repo fetch origin feature/pos-refunds" in out
    assert "worktree add --detach /opt/testbed/worktrees/feature-pos-refunds origin/feature/pos-refunds" in out
    assert "CALL OPS.TESTBED.CREATE_BRANCH_CLONE('DW_BR_FEATURE_POS_REFUNDS');" in out
    assert "  - hostname: airflow-feature-pos-refunds.example.dev" in out
    assert (
        "route dns --overwrite-dns 6f1c2c1e-0000-4000-8000-000000000000 airflow-feature-pos-refunds.example.dev" in out
    )


def test_branch_ui(capsys):
    out = dry(capsys, "branch", "ui", "feature/pos-refunds")
    assert "up -d airflow-api-server" in out
    assert "# UI on the VM: http://127.0.0.1:" in out


def test_test_task_and_dag(capsys):
    out = dry(
        capsys, "test", "task", "pos_orders", "fetch_orders", "--branch", "feature/pos-refunds", "--date", "2026-11-06"
    )
    assert out.endswith(
        "--env-file .env.branch exec -T airflow-scheduler airflow tasks test pos_orders fetch_orders 2026-11-06"
    )
    out = dry(capsys, "test", "dag", "pos_orders", "--branch", "feature/pos-refunds", "--date", "2026-11-06")
    assert out.endswith("exec -T airflow-scheduler airflow dags test pos_orders 2026-11-06")


def test_check_tables(capsys):
    out = dry(capsys, "check", "tables", "pos.orders", "--branch", "feature/pos-refunds")
    assert "run --rm --no-deps -T airflow-cli python /opt/airflow/scripts/run_sql.py --database" in out
    assert "FROM DW_BR_FEATURE_POS_REFUNDS.INFORMATION_SCHEMA.TABLES" in out


def test_branch_down(capsys):
    out = dry(capsys, "branch", "down", "feature/pos-refunds")
    assert "DROP_BRANCH_CLONE('DW_BR_FEATURE_POS_REFUNDS')" in out
    assert out.endswith("worktree remove --force /opt/testbed/worktrees/feature-pos-refunds")


def test_deploy(capsys):
    out = dry(capsys, "deploy")
    order = [
        "git -C /opt/testbed/repo branch --show-current",
        "git -C /opt/testbed/repo status --porcelain",
        "git -C /opt/testbed/repo fetch origin main",
        "git -C /opt/testbed/repo merge --ff-only origin/main",
        "airflow dags reserialize",
        "airflow dags list-import-errors",
    ]
    positions = [out.index(text) for text in order]
    assert positions == sorted(positions)


def test_dry_run_flag_works_after_the_command(capsys):
    assert main(["deploy", "--dry-run"]) == 0
    assert "merge --ff-only origin/main" in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv",
    [
        ["branch", "up", "-rf"],
        ["branch", "up", "feature/../main"],
        ["test", "task", "pos_orders", "fetch_orders"],
        ["test", "task", "pos orders", "x", "--branch", "b"],
        ["test", "dag", "pos_orders", "--branch", "b", "--date", "tomorrow"],
        ["check", "tables", "orders", "--branch", "b"],
    ],
)
def test_bad_input_is_refused_before_anything_runs(argv):
    with pytest.raises(SystemExit) as exit_info:
        main(["--dry-run", *argv])
    assert exit_info.value.code == 2


def test_branch_tunnel_without_an_id_is_refused(monkeypatch):
    monkeypatch.delenv("TESTBED_TUNNEL_ID")
    with pytest.raises(SystemExit):
        main(["--dry-run", "branch", "up", "feature/x", "--tunnel"])
