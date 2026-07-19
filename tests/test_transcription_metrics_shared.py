from __future__ import annotations

import pytest

from realtime_backend.app.evaluation.transcription_metrics import (
    NormalizationPolicy,
    aggregate_metric_results,
    character_error_rate,
    compare_to_reference,
    edit_distance_with_operations,
    evaluate_domain_terms,
    evaluate_transcription,
    normalize_text,
    word_error_rate,
)


def test_turkish_normalization_preserves_letters_and_handles_dotted_i():
    text = "İSTANBUL IĞDIR, Ankara’da 42 kişi."

    normalized = normalize_text(text)

    assert normalized == "istanbul ığdır ankara da 42 kişi"
    assert all(letter in normalized for letter in ("ı", "ğ", "ş"))


def test_normalization_options_cover_punctuation_apostrophes_and_numbers():
    policy = NormalizationPolicy(remove_punctuation=False, normalize_numbers=True)

    normalized = normalize_text("Proje’nin 42 görevi!", policy)

    assert normalized == "proje'nin kırk iki görevi!"


def test_wer_cer_and_edit_operations_are_reported_from_one_alignment():
    evaluation = evaluate_transcription("merhaba ekip bugün", "merhaba bugün yeni")

    assert evaluation is not None
    assert evaluation.normalized.wer == pytest.approx(2 / 3)
    assert evaluation.normalized.cer is not None
    assert len(evaluation.normalized.substitutions) == 2
    assert evaluation.normalized.reference_word_count == 3
    assert evaluation.normalized.hypothesis_word_count == 3


def test_deletion_and_insertion_counts_are_explicit():
    deletion = evaluate_transcription("bir iki", "bir")
    insertion = evaluate_transcription("bir", "bir iki")

    assert deletion is not None and len(deletion.normalized.deletions) == 1
    assert deletion.normalized.insertions == ()
    assert insertion is not None and len(insertion.normalized.insertions) == 1
    assert insertion.normalized.deletions == ()


def test_metrics_are_not_calculated_without_reference_or_when_excluded():
    assert evaluate_transcription(None, "metin") is None
    assert evaluate_transcription("", "metin") is None
    assert evaluate_transcription("referans", "metin", excluded=True) is None
    assert word_error_rate(None, "metin") is None
    assert character_error_rate("", "metin") is None


def test_raw_and_normalized_comparisons_remain_distinct():
    evaluation = evaluate_transcription("Merhaba, ekip!", "merhaba ekip")

    assert evaluation is not None
    assert evaluation.raw.wer > 0.0
    assert evaluation.normalized.wer == 0.0


def test_domain_term_accuracy_is_occurrence_and_alignment_aware():
    result = evaluate_domain_terms(
        "MindGraph sonra MindGraph ve FastAPI",
        "MindGraph sonra hata ve FastAPI MindGraph",
        ["MindGraph", "FastAPI"],
    )

    assert result is not None
    assert result.total_reference_occurrences == 3
    assert result.correctly_recognized_occurrences == 2
    assert result.substitution_occurrences == 1
    assert result.accuracy == pytest.approx(2 / 3)
    assert result.per_term["MindGraph"]["correct_occurrences"] == 1


def test_domain_term_elsewhere_does_not_credit_missing_reference_position():
    result = evaluate_domain_terms("MindGraph burada", "burada MindGraph", ["MindGraph"])

    assert result is not None
    assert result.correctly_recognized_occurrences == 0
    assert result.accuracy == 0.0


def test_corpus_aggregation_uses_total_reference_denominators():
    first = evaluate_transcription("bir iki", "bir")
    second = evaluate_transcription("üç dört beş", "üç dört beş")

    aggregate = aggregate_metric_results([first.normalized, second.normalized])

    assert aggregate is not None
    assert aggregate["reference_word_count"] == 5
    assert aggregate["word_distance"] == 1
    assert aggregate["wer"] == pytest.approx(0.2)


def test_compatibility_helpers_delegate_to_shared_metric_shape():
    comparison = compare_to_reference("bir iki", "bir üç")
    distance, operations = edit_distance_with_operations(["bir", "iki"], ["bir", "üç"])

    assert comparison is not None
    assert comparison["wer"] == pytest.approx(0.5)
    assert comparison["substitution_count"] == 1
    assert distance == 1
    assert operations["substitutions"] == [{"reference": "iki", "actual": "üç"}]
