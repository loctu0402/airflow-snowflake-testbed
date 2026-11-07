"""Run one task or one DAG of a branch stack without the UI, and compare its tables with the nightly baseline."""

from datetime import UTC, datetime, timedelta

from testbed import naming, stack
from testbed.config import Settings
from testbed.shell import Step


def yesterday() -> str:
    return (datetime.now(UTC).date() - timedelta(days=1)).isoformat()


def task(settings: Settings, branch: str, dag_id: str, task_id: str, day: str) -> list[Step]:
    return [
        stack.branch_compose(
            settings,
            branch,
            "exec",
            "-T",
            "airflow-scheduler",
            "airflow",
            "tasks",
            "test",
            naming.airflow_id(dag_id),
            naming.airflow_id(task_id),
            naming.logical_date(day),
        )
    ]


def dag(settings: Settings, branch: str, dag_id: str, day: str) -> list[Step]:
    return [
        stack.branch_compose(
            settings,
            branch,
            "exec",
            "-T",
            "airflow-scheduler",
            "airflow",
            "dags",
            "test",
            naming.airflow_id(dag_id),
            naming.logical_date(day),
        )
    ]


def tables_sql(branch: str, tables: list[str]) -> str:
    names = ", ".join(f"'{naming.table(name)}'" for name in tables)
    selects = [
        f"SELECT '{database}' AS DATABASE_NAME, TABLE_SCHEMA, TABLE_NAME, ROW_COUNT, LAST_ALTERED,\n"
        f"    DATEDIFF('minute', LAST_ALTERED, CURRENT_TIMESTAMP()) AS MINUTES_SINCE_WRITE\n"
        f"FROM {database}.INFORMATION_SCHEMA.TABLES\n"
        f"WHERE TABLE_SCHEMA || '.' || TABLE_NAME IN ({names})"
        for database in (naming.database(branch), naming.TEST_DATABASE)
    ]
    return "\nUNION ALL\n".join(selects) + "\nORDER BY TABLE_SCHEMA, TABLE_NAME, DATABASE_NAME;\n"


def check_tables(settings: Settings, branch: str, tables: list[str]) -> list[Step]:
    return [stack.snowflake_sql(settings, branch, tables_sql(branch, tables), naming.database(branch))]
