"""Unit and contract tests for all REST API endpoints in app/api/routes.py."""

import pytest
from fastapi.testclient import TestClient
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_get_system_info(client: TestClient):
    res = client.get("/api/system/info")
    assert res.status_code == 200
    data = res.json()
    assert data["app"] == "RE-PLAN-V"
    assert "symbolic_core" in data
    assert len(data["domains"]) == 6
    assert data["graph_mode"] == "Model B: Complete Reachable-State Graph"


def test_get_domains_list(client: TestClient):
    res = client.get("/api/domains")
    assert res.status_code == 200
    domains = res.json()
    assert len(domains) == 6
    domain_ids = {d["domain_id"] for d in domains}
    assert domain_ids == {
        "blocks_world",
        "grid_world",
        "household_robotics",
        "warehouse",
        "scheduling",
        "software_workflow",
    }


@pytest.mark.parametrize("d_id", [
    "blocks_world",
    "grid_world",
    "household_robotics",
    "warehouse",
    "scheduling",
    "software_workflow",
])
def test_get_domain_details(client: TestClient, d_id: str):
    res = client.get(f"/api/domains/{d_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["domain_id"] == d_id
    assert len(data["actions"]) > 0
    assert len(data["predicates"]) > 0
    assert "entity_types" in data


def test_get_domain_details_not_found(client: TestClient):
    res = client.get("/api/domains/quantum_teleportation")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_post_graph_enumerate_success(client: TestClient):
    res = client.post("/api/graph/enumerate", json={
        "domain_id": "blocks_world",
        "prompt": "Stack the red box on the blue box.",
        "max_nodes": 50,
        "max_edges": 150,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["format"] == "cytoscape"
    assert "elements" in data
    nodes = [el for el in data["elements"] if "source" not in el["data"]]
    edges = [el for el in data["elements"] if "source" in el["data"]]
    assert len(nodes) > 0
    assert len(edges) > 0
    assert "stats" in data
    assert data["stats"]["total_nodes"] == len(nodes)


def test_post_graph_enumerate_multi_domain(client: TestClient):
    res = client.post("/api/graph/enumerate", json={
        "domain_id": "warehouse",
        "prompt": "Move SKU_A from shelf_1 to dispatch dock.",
        "max_nodes": 30,
        "max_edges": 100,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["format"] == "cytoscape"
    nodes = [el for el in data["elements"] if "source" not in el["data"]]
    assert len(nodes) > 0


def test_post_graph_enumerate_clarification(client: TestClient):
    res = client.post("/api/graph/enumerate", json={
        "domain_id": "auto",
        "prompt": "Deliver the package.",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "NEEDS_CLARIFICATION"
    assert "clarification_question" in data
    assert data["clarification_question"] is not None


def test_post_graph_enumerate_unsupported(client: TestClient):
    res = client.post("/api/graph/enumerate", json={
        "domain_id": "auto",
        "prompt": "Book a flight from Tokyo to Paris.",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "UNSUPPORTED"


def test_post_pipeline_run_valid(client: TestClient):
    res = client.post("/api/pipeline/run", json={
        "prompt": "Move the red box next to the blue box. Do not move the glass.",
        "algorithm": "A*",
        "provider_type": "mock",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["symbolic_problem_name"] is not None
    assert data["final_plan"] is not None
    assert len(data["final_plan"]["actions"]) > 0
    assert data["final_verification"]["is_valid"] is True


def test_post_pipeline_run_multi_domain(client: TestClient):
    res = client.post("/api/pipeline/run", json={
        "prompt": "Move SKU_A from shelf_1 to dispatch dock.",
        "domain_id": "warehouse",
        "algorithm": "A*",
        "provider_type": "mock",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["final_plan"] is not None
    assert len(data["final_plan"]["actions"]) > 0
    assert data["final_verification"]["is_valid"] is True


def test_post_llm_formalize_mock(client: TestClient):
    res = client.post("/api/llm/formalize", json={
        "prompt": "Stack the red box on the blue box.",
        "domain_id": "blocks_world",
        "provider": "mock",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "red_box" in data["entities"]
    assert len(data["goal_facts"]) > 0


def test_post_dynamic_simulate(client: TestClient):
    res = client.post("/api/dynamic/simulate", json={
        "initial_prompt": "Stack the red box on the green box, then put the blue box on the red box.",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["root_cause"] == "ENVIRONMENT_CHANGE"
    assert data["final_verification"] == "VERIFIED"
