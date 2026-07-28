from __future__ import annotations

from datetime import UTC, datetime

import pytest

from collective_mindgraph.application.memory import AnswerMemory
from collective_mindgraph.application.memory.memory_results import MemorySearchResult
from collective_mindgraph.domain import (
    EvidenceId,
    EvidenceReference,
    KnowledgeNode,
    KnowledgeNodeId,
    KnowledgeNodeKind,
    MeetingId,
    SegmentId,
)
from collective_mindgraph.infrastructure.ai import LocalEndpointLanguageModel


class _Search:
    def __init__(self, results):
        self._results = results

    def __call__(self, *_args, **_kwargs):
        return self._results


class _LanguageModel:
    def __init__(self, payload=None, error: Exception | None = None):
        self.payload = payload
        self.error = error

    def is_available(self) -> bool:
        return True

    def generate_structured_json(self, _prompt, _schema):
        if self.error is not None:
            raise self.error
        return self.payload


def _results() -> tuple[MemorySearchResult, ...]:
    now = datetime.now(tz=UTC)
    evidence = EvidenceReference(
        id=EvidenceId("evidence-1"),
        meeting_id=MeetingId(1),
        segment_id=SegmentId("segment-1"),
        text_preview="SQLite migration accepted",
        start_seconds=1,
        end_seconds=3,
        created_at=now,
    )
    node = KnowledgeNode(
        id=KnowledgeNodeId("node-1"),
        meeting_id=MeetingId(1),
        kind=KnowledgeNodeKind.DECISION,
        title="SQLite migration accepted",
        body="SQLite migration accepted",
        evidence_id=evidence.id,
        attributes={"review": "accepted", "needs_review": False},
        created_at=now,
        updated_at=now,
    )
    return (
        MemorySearchResult(
            node=node,
            score=1,
            matched_by=frozenset({"keyword"}),
            evidence=evidence,
        ),
    )


def test_grounded_local_answer_accepts_only_cited_supported_sentences():
    model = _LanguageModel(
        {
            "sentences": [
                {
                    "text": "SQLite migration accepted.",
                    "citations": ["evidence-1"],
                }
            ]
        }
    )
    answer = AnswerMemory(_Search(_results()), model)(
        "What was accepted?",
        mode="llm_assisted",
    )

    assert answer.mode_used == "llm_assisted"
    assert answer.validation_status == "accepted"
    assert answer.sentence_validations[0].supported is True
    assert answer.sentence_validations[0].sources == ("evidence-1",)


@pytest.mark.parametrize(
    ("payload", "warning_fragment"),
    [
        (
            {"sentences": [{"text": "SQLite migration accepted.", "citations": ["unknown"]}]},
            "unknown evidence",
        ),
        (
            {"sentences": [{"text": "SQLite migration accepted.", "citations": []}]},
            "must have evidence",
        ),
        (
            {"sentences": [{"text": "Mars launch approved.", "citations": ["evidence-1"]}]},
            "unsupported",
        ),
        ({"answer": "SQLite migration accepted."}, "no cited sentences"),
    ],
)
def test_unsafe_local_answers_fall_back_to_evidence(
    payload,
    warning_fragment,
):
    answer = AnswerMemory(_Search(_results()), _LanguageModel(payload))(
        "What was accepted?",
        mode="llm_assisted",
    )

    assert answer.mode_used == "evidence_only_fallback"
    assert answer.validation_status == "rejected_fallback"
    assert warning_fragment in answer.warnings[0]
    assert answer.short_answer == "SQLite migration accepted"


def test_malformed_language_model_json_falls_back_without_provider_exception():
    answer = AnswerMemory(
        _Search(_results()),
        _LanguageModel(error=ValueError("bad json")),
    )("What was accepted?", mode="llm_assisted")

    assert answer.mode_used == "evidence_only_fallback"
    assert "malformed" in answer.warnings[0]


def test_evidence_only_answer_refuses_nodes_without_evidence():
    result = _results()[0]
    answer = AnswerMemory(
        _Search(
            (
                MemorySearchResult(
                    node=result.node,
                    score=result.score,
                    matched_by=result.matched_by,
                    evidence=None,
                ),
            )
        )
    )("What was accepted?")

    assert answer.confidence_level == "insufficient"
    assert answer.used_sources == ()
    assert answer.chains == ()


def test_partially_supported_generated_claim_falls_back_to_evidence():
    answer = AnswerMemory(
        _Search(_results()),
        _LanguageModel(
            {
                "sentences": [
                    {
                        "text": "SQLite migration accepted in Paris.",
                        "citations": ["evidence-1"],
                    }
                ]
            }
        ),
    )("What was accepted?", mode="llm_assisted")

    assert answer.mode_used == "evidence_only_fallback"
    assert "unsupported" in answer.warnings[0]


def test_local_endpoint_malformed_top_level_json_never_raises_unbound_local(
    monkeypatch,
):
    class _Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b"not-json"

    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: _Response())
    model = LocalEndpointLanguageModel(
        "http://127.0.0.1:1234/v1",
        model_name="test-model",
    )

    with pytest.raises(ValueError, match="valid structured JSON"):
        model.generate_structured_json("prompt", {"type": "object"})
