"""Page through a JSON API for one time window and insert the records into a landing table."""

from airflow.providers.http.hooks.http import HttpHook
from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook

PAGE_SIZE = 500


def load_window(http_conn_id, endpoint, table, columns, start, end) -> int:
    http = HttpHook(method="GET", http_conn_id=http_conn_id)
    snowflake = SnowflakeHook(snowflake_conn_id="snowflake_default")
    loaded, page = 0, 1
    while True:
        params = {
            "updated_from": start.isoformat(),
            "updated_to": end.isoformat(),
            "page": page,
            "page_size": PAGE_SIZE,
        }
        records = http.run(endpoint, data=params).json()["data"]
        if records:
            rows = [[record[column.lower()] for column in columns] for record in records]
            snowflake.insert_rows(table, rows, target_fields=columns)
            loaded += len(records)
        if len(records) < PAGE_SIZE:
            return loaded
        page += 1
