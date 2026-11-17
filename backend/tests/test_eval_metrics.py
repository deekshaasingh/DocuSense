"""The evaluation metrics themselves need tests: a wrong metric is worse than none."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "eval")))

from metrics import (  # noqa: E402
    auroc, error_capture, expected_calibration_error, match_line_items, prf,
    reliability_table,
)


def test_perfect_calibration_has_near_zero_ece():
    # every prediction in the 0.9-1.0 bin, 95% of them correct, midpoint 0.95
    scores = [0.95] * 100
    correct = [True] * 95 + [False] * 5
    assert expected_calibration_error(scores, correct) == pytest.approx(0.0, abs=1e-9)


def test_inverted_confidence_has_large_ece():
    scores = [0.95] * 50
    correct = [False] * 50
    assert expected_calibration_error(scores, correct) > 0.9


def test_reliability_table_bins_and_counts():
    rows = reliability_table([0.05, 0.15, 0.95, 0.99], [False, True, True, True])
    assert sum(r["n"] for r in rows) == 4
    assert rows[-1]["n"] == 2


def test_auroc_perfect_separation_is_one():
    assert auroc([0.9, 0.8, 0.2, 0.1], [True, True, False, False]) == pytest.approx(1.0)


def test_auroc_undefined_with_one_class():
    assert auroc([0.9, 0.8], [True, True]) is None


def test_error_capture_rewards_confidence_guided_review():
    # the two lowest-confidence documents hold every error
    doc_scores = [0.1, 0.2, 0.9, 0.95, 0.99]
    doc_errors = [3, 2, 0, 0, 0]
    out = error_capture(doc_scores, doc_errors, 0.4)
    assert out["documents_reviewed"] == 2
    assert out["errors_caught_guided"] == 5
    assert out["ecarb"] > 2.0
    assert out["recall_of_errors"] == pytest.approx(1.0)


def test_error_capture_is_one_when_confidence_is_uninformative():
    doc_scores = [0.5] * 10
    doc_errors = [1] * 10
    out = error_capture(doc_scores, doc_errors, 0.3)
    assert out["ecarb"] == pytest.approx(1.0, abs=0.01)


def test_line_item_matching_aligns_rows_out_of_order():
    pred = [
        {"description": "Stapler", "quantity": 1, "unit_price": 50.0, "amount": 50.0},
        {"description": "A4 paper ream", "quantity": 2, "unit_price": 100.0, "amount": 200.0},
    ]
    truth = [
        {"description": "A4 paper ream", "quantity": 2, "unit_price": 100.0, "amount": 200.0},
        {"description": "Stapler", "quantity": 1, "unit_price": 50.0, "amount": 50.0},
    ]
    m = match_line_items(pred, truth)
    assert m == {"matched": 2, "predicted": 2, "expected": 2}


def test_line_item_matching_rejects_wrong_numbers():
    pred = [{"description": "Stapler", "quantity": 1, "unit_price": 50.0, "amount": 50.0}]
    truth = [{"description": "Stapler", "quantity": 9, "unit_price": 999.0, "amount": 8991.0}]
    assert match_line_items(pred, truth)["matched"] == 0


def test_line_item_matching_handles_empty_sides():
    assert match_line_items([], [])["matched"] == 0
    assert match_line_items([], [{"description": "x"}])["expected"] == 1


def test_prf():
    p, r, f = prf(matched=3, predicted=4, expected=6)
    assert p == pytest.approx(0.75)
    assert r == pytest.approx(0.5)
    assert f == pytest.approx(0.6)
