"""Trips the delivery partner exports as CSV each day, copied from a stage into DELIVERY.TRIPS."""

from datetime import timedelta

import pendulum
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow.sdk import CronDataIntervalTimetable, dag


@dag(
    schedule=CronDataIntervalTimetable("0 6 * * *", timezone="UTC"),
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=10)},
    tags=["delivery", "load"],
)
def delivery_trips():
    clear_landing = SQLExecuteQueryOperator(
        task_id="clear_landing",
        conn_id="snowflake_default",
        sql="TRUNCATE TABLE DELIVERY.TRIPS_LANDING",
    )
    copy_trips = SQLExecuteQueryOperator(
        task_id="copy_trips",
        conn_id="snowflake_default",
        sql="sql/delivery_trips_copy.sql",
    )
    merge_trips = SQLExecuteQueryOperator(
        task_id="merge_trips",
        conn_id="snowflake_default",
        sql="sql/delivery_trips_merge.sql",
    )

    clear_landing >> copy_trips >> merge_trips


delivery_trips()
