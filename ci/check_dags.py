"""Import every DAG the way the dag-processor does and resolve every SQL file a task names."""

import os
import sys
import tempfile
from pathlib import Path


def main(folder: str) -> int:
    dags = Path(folder).resolve()
    home = Path(tempfile.mkdtemp())
    os.environ["AIRFLOW_HOME"] = str(home)
    os.environ["AIRFLOW__CORE__DAGS_FOLDER"] = str(dags)
    os.environ["AIRFLOW__CORE__LOAD_EXAMPLES"] = "False"
    os.environ["AIRFLOW__DATABASE__SQL_ALCHEMY_CONN"] = f"sqlite:///{(home / 'ci.db').as_posix()}"
    sys.path.insert(0, str(dags))

    from airflow.dag_processing.dagbag import DagBag

    bag = DagBag(dag_folder=str(dags), include_examples=False)
    failures = [f"{Path(path).name}: {error.strip().splitlines()[-1]}" for path, error in bag.import_errors.items()]
    for dag_id, dag in sorted(bag.dags.items()):
        dag.resolve_template_files()
        unresolved = [
            f"{task.task_id} -> {task.sql}"
            for task in dag.tasks
            if isinstance(getattr(task, "sql", None), str) and task.sql.endswith(".sql")
        ]
        failures += [f"{dag_id}: SQL file not found for {item}" for item in unresolved]
        print(f"ok  {dag_id}: {', '.join(task.task_id for task in dag.tasks)}")
    for failure in failures:
        print(f"ERR {failure}")
    if not bag.dags:
        failures.append("no DAG found")
    print(f"{len(bag.dags)} DAGs imported, {len(failures)} errors")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "airflow/dags"))
