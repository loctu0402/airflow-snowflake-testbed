import re
from pathlib import Path

import pytest

from testbed import naming

PROCEDURES_SQL = Path(__file__).resolve().parents[1] / "snowflake" / "08_branch_clones.sql"
BRANCHES = [
    "main",
    "feature/POS-Refunds",
    "fix__double--dash",
    "release/2026.11",
    "dependabot/pip/apache-airflow-providers-snowflake-6.17.0",
    "user/a-very-long-branch-name-that-keeps-going-past-the-limit",
]


@pytest.mark.parametrize(
    ("branch", "expected"),
    [
        ("main", "main"),
        ("feature/POS-Refunds", "feature-pos-refunds"),
        ("fix__double--dash", "fix-double-dash"),
        ("release/2026.11", "release-2026-11"),
    ],
)
def test_slug_sanitises_branch_names(branch, expected):
    assert naming.slug(branch) == expected


def test_long_slugs_are_cut_with_a_stable_hash():
    first = naming.slug("user/a-very-long-branch-name-that-keeps-going-past-the-limit")
    second = naming.slug("user/a-very-long-branch-name-that-keeps-going-past-the-limit-two")
    assert len(first) <= naming.SLUG_MAX
    assert first != second
    assert first == naming.slug("user/a-very-long-branch-name-that-keeps-going-past-the-limit")
    assert re.fullmatch(r"[a-z0-9-]+-[0-9a-f]{6}", first)


@pytest.mark.parametrize(
    "branch", ["", "-rf", "--upload-pack=x", "feature/../main", "a b", "x.lock", "feature/", "a//b", "bad;rm", "a$(id)"]
)
def test_unusable_branch_names_are_refused(branch):
    with pytest.raises(ValueError):
        naming.slug(branch)


def test_derived_names():
    branch = "feature/POS-Refunds"
    assert naming.project(branch) == "testbed-feature-pos-refunds"
    assert naming.database(branch) == "DW_BR_FEATURE_POS_REFUNDS"
    assert naming.hostname(branch, "example.dev") == "airflow-feature-pos-refunds.example.dev"


def test_every_branch_database_passes_the_procedure_guard():
    guard = re.compile(re.search(r're\.compile\(r"([^"]+)"\)', PROCEDURES_SQL.read_text()).group(1))
    for branch in BRANCHES:
        assert guard.fullmatch(naming.database(branch)), naming.database(branch)


def test_ports_are_stable_and_clear_of_the_main_ui():
    for branch in BRANCHES:
        port = naming.port(branch)
        assert naming.PORT_BASE <= port < naming.PORT_BASE + naming.PORT_SPAN
        assert port == naming.port(branch)
        assert port != 8080


def test_hostnames_stay_one_label_under_the_zone():
    for branch in BRANCHES:
        label, zone = naming.hostname(branch, "example.dev").split(".", 1)
        assert zone == "example.dev"
        assert len(label) <= 63


def test_tables_are_upper_cased_and_checked():
    assert naming.table("pos.orders") == "POS.ORDERS"
    for bad in ["orders", "POS.ORDERS;DROP", "a.b.c", "POS.'X'"]:
        with pytest.raises(ValueError):
            naming.table(bad)


def test_airflow_ids_and_dates_are_checked():
    assert naming.airflow_id("pos_orders") == "pos_orders"
    assert naming.logical_date("2026-11-06") == "2026-11-06"
    for bad in ["pos orders", "dag;rm", ""]:
        with pytest.raises(ValueError):
            naming.airflow_id(bad)
    for bad in ["2026-13-01", "yesterday", "06/11/2026"]:
        with pytest.raises(ValueError):
            naming.logical_date(bad)
