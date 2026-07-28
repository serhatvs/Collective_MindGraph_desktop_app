from __future__ import annotations

from scripts.quality.check_mypy_baseline import find_regressions, parse_error_budget


def test_mypy_baseline_parser_normalizes_paths_and_groups_error_codes():
    errors = parse_error_budget(
        [
            "src\\collective_mindgraph\\engine\\main.py:12: error: Missing return [no-untyped-def]",
            "src/collective_mindgraph/engine/main.py:20:4: error: Bad argument [arg-type]",
            "a note that is not an error",
        ]
    )

    assert errors == {
        "src/collective_mindgraph/engine/main.py|no-untyped-def": 1,
        "src/collective_mindgraph/engine/main.py|arg-type": 1,
    }


def test_mypy_baseline_rejects_new_categories_and_count_increases():
    baseline = {"module.py|arg-type": 2, "module.py|assignment": 1}
    actual = {
        "module.py|arg-type": 3,
        "module.py|assignment": 0,
        "other.py|attr-defined": 2,
    }

    assert find_regressions(actual, baseline) == {
        "module.py|arg-type": 1,
        "other.py|attr-defined": 2,
    }


def test_mypy_baseline_allows_only_debt_reduction():
    baseline = {"module.py|arg-type": 2}

    assert find_regressions({"module.py|arg-type": 1}, baseline) == {}
