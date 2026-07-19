"""Shared, reference-based transcription evaluation utilities."""

from .transcription_metrics import (
    DomainTermEvaluation,
    MetricResult,
    NormalizationPolicy,
    TextEvaluation,
    aggregate_metric_results,
    character_error_rate,
    compare_to_reference,
    edit_distance_with_operations,
    evaluate_domain_terms,
    evaluate_transcription,
    normalize_text,
    word_error_rate,
)

__all__ = [
    "DomainTermEvaluation",
    "MetricResult",
    "NormalizationPolicy",
    "TextEvaluation",
    "aggregate_metric_results",
    "character_error_rate",
    "compare_to_reference",
    "edit_distance_with_operations",
    "evaluate_domain_terms",
    "evaluate_transcription",
    "normalize_text",
    "word_error_rate",
]
