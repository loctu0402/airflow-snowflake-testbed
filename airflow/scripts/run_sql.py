"""Run the SQL read from stdin with this stack's Snowflake connection and print every result set."""

import argparse
import sys
from contextlib import closing

from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, help="database the session starts in")
    args = parser.parse_args()
    hook = SnowflakeHook(snowflake_conn_id="snowflake_default", database=args.database)
    with closing(hook.get_conn()) as connection:
        for cursor in connection.execute_string(sys.stdin.read()):
            print("\t".join(column[0] for column in cursor.description))
            for row in cursor:
                print("\t".join("" if value is None else str(value) for value in row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
