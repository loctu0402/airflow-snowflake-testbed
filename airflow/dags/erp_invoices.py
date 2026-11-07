"""Invoices changed each day, from the ERP API into ERP.INVOICES."""

from datetime import timedelta

import pendulum
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow.sdk import CronDataIntervalTimetable, dag, task

from loaders.api import load_window

COLUMNS = ["INVOICE_ID", "SUPPLIER_ID", "INVOICE_DATE", "AMOUNT", "CURRENCY", "UPDATED_AT"]


@dag(
    schedule=CronDataIntervalTimetable("30 1 * * *", timezone="UTC"),
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=10)},
    tags=["erp", "load"],
)
def erp_invoices():
    clear_landing = SQLExecuteQueryOperator(
        task_id="clear_landing",
        conn_id="snowflake_default",
        sql="TRUNCATE TABLE ERP.INVOICES_LANDING",
    )

    @task
    def fetch_invoices(data_interval_start=None, data_interval_end=None) -> int:
        return load_window(
            "erp_api", "/v1/invoices", "ERP.INVOICES_LANDING", COLUMNS, data_interval_start, data_interval_end
        )

    merge_invoices = SQLExecuteQueryOperator(
        task_id="merge_invoices",
        conn_id="snowflake_default",
        sql="sql/erp_invoices_merge.sql",
    )

    clear_landing >> fetch_invoices() >> merge_invoices


erp_invoices()
