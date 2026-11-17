"""Step 7: the scoring formula, its aggregators, and the routing policy."""
import math

import pytest

from schemas import Invoice, LineItem
from pipeline.confidence import (
    aggregate_logprobs, field_confidence, score_document, route,
    MODEL_WEIGHT, AGREEMENT_WEIGHT, RULES_WEIGHT,
)
from datetime import date


def test_weights_match_the_manual():
    assert (MODEL_WEIGHT, AGREEMENT_WEIGHT, RULES_WEIGHT) == (0.5, 0.3, 0.2)


def test_field_confidence_all_signals_agree_is_high():
    # logprob 0.0 means probability 1.0, i.e. complete certainty
    assert field_confidence([0.0, 0.0], agrees=True, rules_ok=True) == pytest.approx(1.0)


def test_field_confidence_no_evidence_is_zero_model_term():
    # no tokens -> no model evidence, only agreement and rules contribute
    assert field_confidence([], agrees=True, rules_ok=True) == pytest.approx(0.5)


def test_disagreement_and_rule_failure_reduce_score():
    high = field_confidence([0.0], agrees=True, rules_ok=True)
    low = field_confidence([0.0], agrees=False, rules_ok=False)
    assert low < high


def test_aggregators_differ_and_are_bounded():
    lps = [math.log(0.9), math.log(0.5), math.log(0.99)]
    first = aggregate_logprobs(lps, "first")
    mean = aggregate_logprobs(lps, "mean")
    weakest = aggregate_logprobs(lps, "min")
    assert weakest == pytest.approx(0.5)
    assert first == pytest.approx(0.9)
    assert weakest <= mean <= 1.0
    for v in (first, mean, weakest):
        assert 0.0 <= v <= 1.0


def test_empty_logprobs_is_zero_for_every_mode():
    for mode in ("mean", "first", "min", "margin"):
        assert aggregate_logprobs([], mode) == 0.0


def _invoice() -> Invoice:
    return Invoice(
        invoice_number="INV-1", invoice_date=date(2025, 5, 1), vendor_name="Acme",
        vendor_gstin="07ABCDE1234F1Z5", subtotal=200.0, tax_amount=36.0,
        total_amount=236.0,
        line_items=[LineItem(description="Paper", quantity=2, unit_price=100.0, amount=200.0)],
    )


def test_score_document_covers_every_field():
    scores = score_document(_invoice(), [0.0], None)
    assert set(scores) == set(Invoice.model_fields)
    assert all(0.0 <= v <= 1.0 for v in scores.values())


def test_rule_failure_only_docks_the_fields_it_concerns():
    inv = _invoice()
    inv.total_amount = 999.0  # breaks subtotal + tax == total
    scores = score_document(inv, [0.0], None)
    assert scores["total_amount"] < scores["invoice_number"]
    assert scores["vendor_name"] == pytest.approx(1.0)


def test_routing_thresholds():
    assert route({"a": 0.95, "b": 0.93}, 0.90, 0.70) == ("approved", [])
    status, flagged = route({"a": 0.95, "b": 0.80}, 0.90, 0.70)
    assert status == "approved" and flagged == ["b"]
    status, flagged = route({"a": 0.95, "b": 0.40}, 0.90, 0.70)
    assert status == "needs_review" and "b" in flagged


def test_per_field_thresholds_override_the_global_bar():
    scores = {"vendor_gstin": 0.60, "total_amount": 0.95}
    # global policy sends this to review
    assert route(scores, 0.90, 0.70)[0] == "needs_review"
    # a field-specific bar that tolerates a weak GSTIN approves it instead
    relaxed = {"vendor_gstin": {"auto": 0.55, "flag": 0.35}}
    assert route(scores, 0.90, 0.70, relaxed) == ("approved", [])
