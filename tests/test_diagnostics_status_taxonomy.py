import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from collective_mindgraph_desktop.ui.pages.diagnostics_page import DiagnosticsPage


def test_diagnostics_uses_truthful_status_taxonomy(qtbot):
    page = DiagnosticsPage()
    qtbot.addWidget(page)

    assert page.labels["diarization_status"].text() == "NOT IMPLEMENTED / ROADMAP"
    assert page.labels["llm_status"].text() == "OPTIONAL / DISABLED"
    assert page.labels["ask_memory_evidence"].text().startswith("ACTIVE")
    assert page.labels["graph_status"].text().startswith("ACTIVE")

    page.set_app_summary(vector_count=0, embedding_dim=384, provider_name="Mock")
    assert page.labels["embedding_status"].text().startswith("DISABLED")
    assert "vector" not in page.labels["hybrid_status"].text().lower()

    page.set_app_summary(
        vector_count=3,
        embedding_dim=384,
        provider_name="SentenceTransformer",
        model_path="local-model",
    )
    assert page.labels["embedding_status"].text().startswith("ACTIVE")
    assert "vector" in page.labels["hybrid_status"].text().lower()
