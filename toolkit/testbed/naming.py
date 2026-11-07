"""Names derived from a git branch, and the checks on every id the toolkit passes to a command."""

import hashlib
import re
from datetime import date

BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}")
AIRFLOW_ID = re.compile(r"[A-Za-z0-9_.-]{1,250}")
TABLE = re.compile(r"[A-Z_][A-Z0-9_]*\.[A-Z_][A-Z0-9_]*")
SLUG_MAX = 30
PORT_BASE = 8100
PORT_SPAN = 800

TEST_DATABASE = "DW_TEST"
BRANCH_DATABASE_PREFIX = "DW_BR_"
PROCEDURES = "OPS.TESTBED"
TEST_USER = "SVC_AIRFLOW_TEST"
TEST_ROLE = "TESTER"
TEST_WAREHOUSE = "TEST_WH"
TEST_KEY_FILE = "tester.p8"


def branch_name(value: str) -> str:
    if not BRANCH.fullmatch(value) or ".." in value or "//" in value or value.endswith((".lock", "/", ".")):
        raise ValueError(f"not a usable branch name: {value!r}")
    return value


def slug(branch: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", branch_name(branch).lower()).strip("-")
    if len(text) <= SLUG_MAX:
        return text
    digest = hashlib.sha1(branch.encode()).hexdigest()[:6]
    return f"{text[: SLUG_MAX - 7].rstrip('-')}-{digest}"


def project(branch: str) -> str:
    return f"testbed-{slug(branch)}"


def database(branch: str) -> str:
    return BRANCH_DATABASE_PREFIX + slug(branch).upper().replace("-", "_")


def port(branch: str) -> int:
    return PORT_BASE + int(hashlib.sha1(slug(branch).encode()).hexdigest(), 16) % PORT_SPAN


def hostname(branch: str, domain: str) -> str:
    return f"airflow-{slug(branch)}.{domain}"


def airflow_id(value: str) -> str:
    if not AIRFLOW_ID.fullmatch(value):
        raise ValueError(f"not a valid DAG or task id: {value!r}")
    return value


def table(value: str) -> str:
    name = value.upper()
    if not TABLE.fullmatch(name):
        raise ValueError(f"name a table as SCHEMA.TABLE, got {value!r}")
    return name


def logical_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError(f"not a date in YYYY-MM-DD: {value!r}") from None
