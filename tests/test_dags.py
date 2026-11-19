from pathlib import Path

from airflow.models import DagBag


PROJECT = Path(__file__).resolve().parents[1]


def test_no_import_errors():
    dagbag = DagBag(dag_folder=str(PROJECT / "dags"), include_examples=False)
    assert dagbag.import_errors == {}


def test_all_project_dags_disable_catchup():
    dagbag = DagBag(dag_folder=str(PROJECT / "dags"), include_examples=False)
    assert dagbag.dags
    assert all(not dag.catchup for dag in dagbag.dags.values())


def test_orders_dag_contains_idempotent_transform():
    dagbag = DagBag(dag_folder=str(PROJECT / "dags"), include_examples=False)
    dag = dagbag.dags.get("marketplace_orders_ingest_daily")
    assert dag is not None
    assert {"refresh_dimensions", "archive_orders", "load_staging", "transform_idempotently"} <= set(dag.task_ids)
    source = (PROJECT / "dags" / "marketplace_orders_ingest.py").read_text(encoding="utf-8")
    assert "DELETE FROM dwh.fact_orders WHERE dt=%s" in source


def test_api_requires_bearer_and_is_deterministic():
    import importlib.util
    spec = importlib.util.spec_from_file_location("marketplace_api", PROJECT / "api" / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    client = module.app.test_client()
    assert client.get("/orders?date=2026-04-07").status_code == 401
    headers = {"Authorization": "Bearer formation-token-2026"}
    first = client.get("/orders?date=2026-04-07", headers=headers).json
    second = client.get("/orders?date=2026-04-07", headers=headers).json
    assert first == second and first
