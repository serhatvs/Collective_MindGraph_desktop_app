import pytest
from fastapi.testclient import TestClient
from realtime_backend.app.main import app

client = TestClient(app)

def test_memory_ask_endpoint_smoke():
    response = client.get("/memory/ask?q=FastAPI görevler")
    assert response.status_code == 200
    data = response.json()
    assert "query" in data
    assert "short_answer" in data
    assert "evidence_chains" in data

def test_memory_ask_llm_assisted_fallback_smoke():
    # Since LLM might not be available in all test envs, check fallback behavior
    response = client.get("/memory/ask?q=Test&mode=llm_assisted")
    assert response.status_code == 200
    data = response.json()
    # If no evidence found, it won't even try LLM, returns evidence_only
    if not data["evidence_chains"]:
        assert data["answer_type"] == "evidence_only"
    else:
        # If evidence found but LLM fails/unavailable, it should be fallback_to_evidence_only
        assert data["answer_type"] in ["llm_assisted", "fallback_to_evidence_only", "evidence_only"]
