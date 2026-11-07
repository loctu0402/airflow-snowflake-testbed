"""Orders changed in each hour, from the POS API into POS.ORDERS."""

from datetime import timedelta

import pendulum
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow.sdk import CronDataIntervalTimetable, dag, task

from loaders.api import load_window

COLUMNS = ["ORDER_ID", "STORE_ID", "ORDERED_AT", "STATUS", "TOTAL_AMOUNT", "UPDATED_AT"]


@dag(
    schedule=CronDataIntervalTimetable("0 * * * *", timezone="UTC"),
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["pos", "load"],
)
def pos_orders():
    clear_landing = SQLExecuteQueryOperator(
        task_id="clear_landing",
        conn_id="snowflake_default",
        sql="TRUNCATE TABLE POS.ORDERS_LANDING",
    )

    @task
    def fetch_orders(data_interval_start=None, data_interval_end=None) -> int:
        return load_window(
            "pos_api", "/v1/orders", "POS.ORDERS_LANDING", COLUMNS, data_interval_start, data_interval_end
        )

    merge_orders = SQLExecuteQueryOperator(
        task_id="merge_orders",
        conn_id="snowflake_default",
        sql="sql/pos_orders_merge.sql",
    )

    clear_landing >> fetch_orders() >> merge_orders


pos_orders()
