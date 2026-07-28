from __future__ import annotations

from collective_mindgraph.application import PageRequest
from collective_mindgraph.application.knowledge import IndexKnowledge
from collective_mindgraph.application.transcription.contracts import (
    ConversationTranscript,
    TaskItem,
    TranscriptSegment,
)
from collective_mindgraph.infrastructure.ai import DeterministicEmbeddingModel
from collective_mindgraph.infrastructure.persistence import (
    CanonicalTranscriptionResultArchive,
)
from test_engine_product_workflows import _settings


def test_transcription_archive_builds_evidence_graph_and_embedding_index(tmp_path):
    from collective_mindgraph.engine.context import build_engine_context

    context = build_engine_context(_settings(tmp_path))
    archive = CanonicalTranscriptionResultArchive(
        context.meetings,
        context.recordings,
        context.transcripts,
        context.insights,
        context.knowledge,
    )
    result = ConversationTranscript(
        conversation_id="conversation-graph",
        source="test",
        language="en",
        segments=[
            TranscriptSegment(
                segment_id="segment-graph",
                start=1,
                end=4,
                speaker="Aylin",
                raw_text="Aylin will migrate SQLite.",
                corrected_text="Aylin will migrate SQLite.",
                confidence=0.9,
            )
        ],
        action_items=[
            TaskItem(
                title="Migrate SQLite",
                responsible_person="Aylin",
                source_segment_id="segment-graph",
            )
        ],
    )

    meeting_id = archive.save(result)

    nodes = context.knowledge.list_nodes(
        PageRequest(limit=200),
        meeting_id=meeting_id,
    )
    edges = context.knowledge.list_edges(PageRequest(limit=200))
    assert {"meeting", "segment", "task", "person"} <= {node.kind.value for node in nodes.items}
    assert {"contains", "derived_from", "assigned_to"} <= {edge.kind.value for edge in edges.items}
    assert all(edge.evidence_id is not None for edge in edges.items)

    indexed = IndexKnowledge(
        context.knowledge,
        context.embeddings,
        DeterministicEmbeddingModel(dim=context.settings.embedding_dimension),
    )(meeting_id)

    assert indexed == nodes.total
    assert context.embeddings.count() == nodes.total
    assert (
        IndexKnowledge(
            context.knowledge,
            context.embeddings,
            DeterministicEmbeddingModel(dim=context.settings.embedding_dimension),
        )(meeting_id)
        == nodes.total
    )
    assert context.embeddings.count() == nodes.total
