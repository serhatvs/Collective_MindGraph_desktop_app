import pytest

from app.models import ConversationTranscript, TranscriptSegment
from app.services.conversation_store import ConversationStore


def test_conversation_store_round_trips_transcript(tmp_path):
    store = ConversationStore(tmp_path)
    transcript = ConversationTranscript(
        conversation_id="conv_123",
        source="test",
        segments=[
            TranscriptSegment(
                segment_id="seg_1",
                start=0.0,
                end=1.0,
                speaker="Speaker_1",
                raw_text="hello",
                corrected_text="Hello.",
            )
        ],
    )

    store.save(transcript)
    loaded = store.get("conv_123")

    assert loaded is not None
    assert loaded.conversation_id == "conv_123"
    assert loaded.segments[0].corrected_text == "Hello."


def test_conversation_store_loads_old_format_gracefully(tmp_path):
    import json
    store = ConversationStore(tmp_path)
    conversation_id = "old_conv"
    path = store.path_for(conversation_id)

    # Minimal old format without diagnostics, quality_mode, or corrected_text in segments
    old_payload = {
        "conversation_id": conversation_id,
        "source": "test",
        "segments": [
            {
                "segment_id": "s1",
                "start": 0.0,
                "end": 1.0,
                "speaker": "Speaker_1",
                "raw_text": "hello old"
                # corrected_text is missing
            }
        ]
    }
    path.write_text(json.dumps(old_payload), encoding="utf-8")

    loaded = store.get(conversation_id)
    assert loaded is not None
    assert loaded.conversation_id == conversation_id
    assert loaded.diagnostics is None
    assert loaded.segments[0].raw_text == "hello old"
    assert loaded.segments[0].corrected_text == ""


@pytest.mark.parametrize(
    "conversation_id",
    [
        "../escape",
        r"..\escape",
        r"C:\Temp\escape",
        "nested/escape",
        ".",
        "x" * 129,
        "𐐀" * 126,
    ],
)
def test_conversation_store_rejects_unsafe_paths(tmp_path, conversation_id):
    store = ConversationStore(tmp_path / "transcripts")

    with pytest.raises(ValueError, match="conversation_id"):
        store.path_for(conversation_id)

    assert list((tmp_path / "transcripts").iterdir()) == []


def test_conversation_store_accepts_unicode_id_with_safe_utf16_length(tmp_path):
    store = ConversationStore(tmp_path / "transcripts")
    conversation_id = "𐐀" * 125

    assert store.path_for(conversation_id).name == f"{conversation_id}.json"
