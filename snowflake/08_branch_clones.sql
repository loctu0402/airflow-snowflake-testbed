USE ROLE SYSADMIN;

CREATE OR REPLACE PROCEDURE OPS.TESTBED.CREATE_BRANCH_CLONE(BRANCH_DATABASE VARCHAR)
RETURNS VARCHAR
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'run'
EXECUTE AS OWNER
AS
$$
import re

BRANCH_DATABASE = re.compile(r"DW_BR_[A-Z0-9_]{1,40}")


def run(session, branch_database):
    name = branch_database.upper()
    if not BRANCH_DATABASE.fullmatch(name):
        raise ValueError(f"{name} is not a branch database name")
    for statement in (
        f"CREATE OR REPLACE DATABASE {name} CLONE DW_TEST",
        f"GRANT USAGE ON DATABASE {name} TO ROLE TESTER",
        f"GRANT ALL ON ALL SCHEMAS IN DATABASE {name} TO ROLE TESTER",
        f"GRANT ALL ON ALL TABLES IN DATABASE {name} TO ROLE TESTER",
        f"GRANT USAGE ON ALL STAGES IN DATABASE {name} TO ROLE TESTER",
        f"GRANT USAGE ON ALL FILE FORMATS IN DATABASE {name} TO ROLE TESTER",
    ):
        session.sql(statement).collect()
    return f"{name} cloned from DW_TEST"
$$;

CREATE OR REPLACE PROCEDURE OPS.TESTBED.DROP_BRANCH_CLONE(BRANCH_DATABASE VARCHAR)
RETURNS VARCHAR
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'run'
EXECUTE AS OWNER
AS
$$
import re

BRANCH_DATABASE = re.compile(r"DW_BR_[A-Z0-9_]{1,40}")


def run(session, branch_database):
    name = branch_database.upper()
    if not BRANCH_DATABASE.fullmatch(name):
        raise ValueError(f"{name} is not a branch database name")
    session.sql(f"DROP DATABASE IF EXISTS {name}").collect()
    return f"{name} dropped"
$$;

GRANT USAGE ON PROCEDURE OPS.TESTBED.CREATE_BRANCH_CLONE(VARCHAR) TO ROLE TESTER;
GRANT USAGE ON PROCEDURE OPS.TESTBED.DROP_BRANCH_CLONE(VARCHAR) TO ROLE TESTER;
