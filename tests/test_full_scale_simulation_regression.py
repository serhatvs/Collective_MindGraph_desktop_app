import pytest
import os
import asyncio
from pathlib import Path
from realtime_backend.scripts.run_full_scale_simulation import run_simulation

@pytest.mark.asyncio
async def test_full_scale_simulation_regression():
    # This will run the simulation and we can assert on the output report
    # The simulation exports into the dated report archive.
    export_path = Path("docs/reports/2026-06-30/simulation/export_simulation.json")
    if export_path.exists():
        export_path.unlink()
        
    await run_simulation()
    
    assert export_path.exists()
    import json
    with open(export_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    v2_graph = data.get("v2_production_graph", {})
    nodes = v2_graph.get("nodes", [])
    node_types = [n.get("type") for n in nodes]
    
    assert "ENTITY" in node_types
    assert "RISK" in node_types
    assert "OPEN_QUESTION" in node_types
    assert "FOLLOW_UP" in node_types
    assert "SESSION" in node_types
    
    # Check edges
    edges = v2_graph.get("edges", [])
    edge_types = [e.get("edge_type") for e in edges]
    
    assert "SEGMENT_RAISES_RISK" in edge_types
    assert "SEGMENT_RAISES_OPEN_QUESTION" in edge_types
    assert "SEGMENT_CREATES_FOLLOW_UP" in edge_types
    assert "SEGMENT_MENTIONS_ENTITY" in edge_types
