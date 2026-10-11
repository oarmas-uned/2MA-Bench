"""
Tests for 2MA-Bench FastAPI web endpoints and SSE streaming.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from twoma_bench.web.app import app


@pytest.mark.asyncio
async def test_web_index_and_dimensions():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Index
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "2M AI Bench" in resp.text

        # Dimensions
        dim_resp = await client.get("/api/dimensions")
        assert dim_resp.status_code == 200
        dims = dim_resp.json()
        assert len(dims) == 5
        dim_ids = [d["id"] for d in dims]
        assert "smt_logic" in dim_ids
        assert "vm_emulation" in dim_ids


@pytest.mark.asyncio
async def test_web_test_connection():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/test-connection",
            json={"provider": "mock", "base_url": "http://localhost", "api_key": "test", "model": "test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


@pytest.mark.asyncio
async def test_web_run_and_results():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Launch run with mock provider
        run_req = {
            "provider": "mock",
            "base_url": "http://localhost",
            "api_key": "test",
            "model": "test",
            "seed": 42,
            "difficulty": 1,
            "dimensions": ["smt_logic", "vm_emulation"],
        }
        res = await client.post("/api/run", json=run_req)
        assert res.status_code == 200
        run_id = res.json()["run_id"]
        assert run_id.startswith("2ma_")

        # Stream events
        event_count = 0
        async with client.stream("GET", f"/api/stream/{run_id}") as stream_resp:
            assert stream_resp.status_code == 200
            async for line in stream_resp.aiter_lines():
                if line.startswith("data:"):
                    event_count += 1
                    if "run_completed" in line:
                        break

        assert event_count > 0

        # Check results
        results_resp = await client.get(f"/api/results/{run_id}")
        assert results_resp.status_code == 200
        summary = results_resp.json()
        assert summary["run_id"] == run_id
        assert summary["total_problems"] == 2

        # Check markdown export
        md_resp = await client.get(f"/api/export/{run_id}/markdown")
        assert md_resp.status_code == 200
        assert "# 2M AI Bench (2MA-Bench) Evaluation Report" in md_resp.text
