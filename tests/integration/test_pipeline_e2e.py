"""Integration and End-to-End Tests for RE-PLAN-V System."""

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from app.services.pipeline import PipelineOrchestrator
from interpretation.vision.scene_generator import SyntheticSceneGenerator


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture
def orchestrator():
    return PipelineOrchestrator()


class TestPipelineOrchestratorE2E:
    """Tests the complete end-to-end Python pipeline."""

    def test_pipeline_valid_instruction(self, orchestrator: PipelineOrchestrator):
        prompt = "Move the red box next to the blue box. Do not move the glass."
        result = orchestrator.run(prompt=prompt, algorithm="A*", force_invalid_first_candidate=False)

        assert result.validation.is_valid is True
        assert len(result.candidate_plan.actions) > 0
        assert result.initial_verification.is_valid is True
        assert result.final_verification.is_valid is True
        assert result.final_plan is not None
        assert result.total_execution_time_ms > 0.0

    def test_pipeline_forced_fault_and_repair(self, orchestrator: PipelineOrchestrator):
        prompt = "Move the red box next to the blue box. Do not move the glass."
        result = orchestrator.run(prompt=prompt, algorithm="A*", force_invalid_first_candidate=True)

        assert result.validation.is_valid is True
        # Initial candidate was forced invalid
        assert result.initial_verification.is_valid is False
        assert result.counterexample is not None
        assert result.fault_attribution is not None
        assert result.replanning_result is not None
        assert result.replanning_result.success is True
        assert result.final_verification.is_valid is True
        assert result.final_plan is not None

    def test_pipeline_with_multimodal_vision(self, orchestrator: PipelineOrchestrator):
        gen = SyntheticSceneGenerator()
        blocks = [
            {"name": "red_box", "color": "red", "shape": "box"},
            {"name": "green_box", "color": "green", "shape": "box"},
        ]
        scene = gen.generate_tabletop_scene(blocks)

        prompt = "Stack the red box on the green box."
        result = orchestrator.run(prompt=prompt, image=scene.image, algorithm="A*")

        assert result.has_image is True
        assert result.validation.is_valid is True
        assert result.final_plan is not None


class TestFastAPIRoutesE2E:
    """Tests API routes and server integration."""

    def test_health_check(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["app"] == "RE-PLAN-V"

    def test_system_info(self, client: TestClient):
        resp = client.get("/api/system/info")
        assert resp.status_code == 200
        data = resp.json()
        assert "research_question" in data
        assert "available_algorithms" in data

    def test_static_index_html(self, client: TestClient):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        assert "RE-PLAN-V" in resp.text

    def test_pipeline_run_endpoint_valid(self, client: TestClient):
        resp = client.post(
            "/api/pipeline/run",
            json={
                "prompt": "Move the red box next to the blue box.",
                "algorithm": "A*",
                "force_invalid_first_candidate": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["validation"]["is_valid"] is True
        assert data["initial_verification"]["is_valid"] is True
        assert data["final_plan"] is not None

    def test_pipeline_run_endpoint_with_fault_repair(self, client: TestClient):
        resp = client.post(
            "/api/pipeline/run",
            json={
                "prompt": "Move the red box next to the blue box.",
                "algorithm": "BFS",
                "force_invalid_first_candidate": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["initial_verification"]["is_valid"] is False
        assert data["counterexample"] is not None
        assert data["replanning_result"]["success"] is True
        assert data["final_verification"]["is_valid"] is True

    def test_benchmark_run_endpoint(self, client: TestClient):
        resp = client.post(
            "/api/benchmark/run",
            json={"num_instances": 2, "seed": 99},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "OURS_CounterexampleRepair" in data["summary"]
        assert "B3_GenericRegeneration" in data["summary"]


class TestCLIExecution:
    """Tests CLI entry points and benchmark invocation."""

    def test_run_cli_interactive(self, monkeypatch, capsys):
        from app.main import run_cli_interactive
        run_cli_interactive(algorithm="A*")
        captured = capsys.readouterr()
        assert "RE-PLAN-V CLI Pipeline Demonstration" in captured.out
        assert "Final Verified Plan" in captured.out

    def test_run_cli_benchmark(self, capsys):
        from app.main import run_cli_benchmark
        run_cli_benchmark(num_instances=2, seed=42)
        captured = capsys.readouterr()
        assert "RE-PLAN-V Empirical Evaluation Benchmark" in captured.out
        assert "OURS_CounterexampleRepair" in captured.out

    def test_main_cli_dispatch(self, monkeypatch):
        import sys
        from app.main import main

        monkeypatch.setattr(sys, "argv", ["app.main", "--mode", "cli", "--algorithm", "BFS"])
        ret = main()
        assert ret == 0

