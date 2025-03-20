import json
import logging
import os
from collections import deque

import sqlglot

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


def load_dbt_dag():
    """Load and parse the dbt manifest file to extract the DAG structure."""
    manifest_path = "target/manifest.json"

    if not os.path.exists(manifest_path):
        raise FileNotFoundError(
            f"Manifest file not found at {manifest_path}. Run 'dbt compile' first."
        )

    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    # Extract models and dependencies
    dag = {}
    for _, details in manifest["nodes"].items():
        if details["resource_type"] == "model":
            model_name = details["name"]
            dependencies = details.get("depends_on", {}).get("nodes", [])
            dag[model_name] = dependencies

    return dag


def topological_sort(dag):
    """Perform topological sorting to determine execution order."""
    in_degree = {node: 0 for node in dag}
    for dependencies in dag.values():
        for dep in dependencies:
            if dep in in_degree:
                in_degree[dep] += 1

    queue = deque([node for node in dag if in_degree[node] == 0])
    execution_order = []

    while queue:
        model = queue.popleft()
        execution_order.append(model)

        for dependent in dag:
            if model in dag[dependent]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

    return execution_order


def transpile_sql(sql_code):
    """Convert T-SQL to DuckDB-compatible SQL."""
    return sqlglot.transpile(sql_code, read="tsql", write="duckdb", pretty=True)[0]


def model(dbt, session):
    dbt.config(materialized="table")

    # Load DAG from dbt
    dag = load_dbt_dag()
    execution_order = topological_sort(dag)

    logger = logging.getLogger(__name__)
    logger.info(f"📌 Execution Order: {execution_order}")

    compiled_dir = "target/compiled/transpile_sql/models/example"

    for model_name in execution_order:
        logger.info(f"🔍 Processing {model_name}...")
        sql_file = os.path.join(compiled_dir, f"{model_name}.sql")

        if not os.path.exists(sql_file):
            logger.warning(f"Skipping {model_name}: Compiled SQL not found.")
            continue

        with open(sql_file, "r") as f:
            compiled_sql = f.read()

        transpiled_sql = transpile_sql(compiled_sql)
        logger.info(f"🔧 Transpiled SQL: \n{transpiled_sql}")

        # Execute transpiled SQL in DuckDB
        # logger.info(f"🚀 Executing {model_name} in DuckDB...")
        # session.sql(transpiled_sql)
        # logger.info(f"✅ Execution successful for {model_name}.")

    return session.sql("SELECT 1 AS success_flag")
