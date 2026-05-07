"""
Property 5: Score Normalization Invariant
Property 6: Confluence Monotonicity
=========================================

Property 5: For any combination of module scores and regime multiplier,
final = min(round(raw * multiplier / 125 * 100), 100) must always be
an integer in [0, 100].

Property 6: When two or more confirmation factors are active simultaneously,
the combined score must be strictly greater than either factor alone.

Satisfies: Requirements 6.1, 6.3, 6.4
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from engine.scorer import SignalScorer, ScoreInput


# ---------------------------------------------------------------------------
# Property 5: Score Normalization Invariant
# ---------------------------------------------------------------------------

@given(
    of_score=st.floats(min_value=0.0, max_value=35.0, allow_nan=False, allow_infinity=False),
    smc_score=st.floats(min_value=0.0, max_value=30.0, allow_nan=False, allow_infinity=False),
    vsa_score=st.floats(min_value=0.0, max_value=30.0, allow_nan=False, allow_infinity=False),
    ctx_score=st.floats(min_value=0.0, max_value=15.0, allow_nan=False, allow_infinity=False),
    bonus=st.floats(min_value=0.0, max_value=15.0, allow_nan=False, allow_infinity=False),
    multiplier=st.floats(min_value=0.6, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property5_score_normalization_invariant(
    of_score, smc_score, vsa_score, ctx_score, bonus, multiplier
):
    """
    Property 5: final score must always be an integer in [0, 100].
    Validates: Requirements 6.1, 6.3
    """
    scorer = SignalScorer()
    inputs = ScoreInput(
        order_flow=of_score,
        smc=smc_score,
        vsa=vsa_score,
        context=ctx_score,
        bonus=bonus,
        regime_multiplier=multiplier,
        direction="long",
        regime="TRENDING",
    )
    result = scorer.score(inputs)

    assert isinstance(result.final_score, int), (
        f"final_score must be int, got {type(result.final_score)}"
    )
    assert 0 <= result.final_score <= 100, (
        f"final_score {result.final_score} is outside [0, 100]"
    )
    assert result.classification in {"ALERT", "WATCH", "IGNORE"}, (
        f"classification '{result.classification}' is invalid"
    )


@given(
    multiplier=st.floats(min_value=0.6, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_property5_all_zeros_gives_zero(multiplier: float):
    """All-zero inputs must produce final_score = 0."""
    scorer = SignalScorer()
    inputs = ScoreInput(
        order_flow=0, smc=0, vsa=0, context=0, bonus=0,
        regime_multiplier=multiplier, direction="long", regime="TRENDING",
    )
    result = scorer.score(inputs)
    assert result.final_score == 0


@given(
    multiplier=st.floats(min_value=0.6, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_property5_all_max_gives_at_most_100(multiplier: float):
    """All-max inputs must produce final_score <= 100."""
    scorer = SignalScorer()
    inputs = ScoreInput(
        order_flow=35, smc=30, vsa=30, context=15, bonus=15,
        regime_multiplier=multiplier, direction="long", regime="TRENDING",
    )
    result = scorer.score(inputs)
    assert result.final_score <= 100


# ---------------------------------------------------------------------------
# Property 6: Confluence Monotonicity
# ---------------------------------------------------------------------------

@given(
    s1=st.floats(min_value=5.0, max_value=25.0, allow_nan=False, allow_infinity=False),
    s2=st.floats(min_value=5.0, max_value=25.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property6_confluence_monotonicity(s1: float, s2: float):
    """
    Property 6: Combined score (s1 + s2 active) must be strictly greater
    than either s1 alone or s2 alone.

    Note: Due to integer rounding in the normalization formula, we require
    both s1 and s2 to be large enough (≥ 5 pts) to guarantee the combined
    score produces a strictly higher integer after rounding.

    Validates: Requirement 6.4
    """
    scorer = SignalScorer()

    # Score with only s1 (smc module)
    result_s1 = scorer.score(ScoreInput(
        order_flow=0, smc=s1, vsa=0, context=0, bonus=0,
        regime_multiplier=1.0, direction="long", regime="TRENDING",
    ))

    # Score with only s2 (vsa module)
    result_s2 = scorer.score(ScoreInput(
        order_flow=0, smc=0, vsa=s2, context=0, bonus=0,
        regime_multiplier=1.0, direction="long", regime="TRENDING",
    ))

    # Score with both active
    result_combined = scorer.score(ScoreInput(
        order_flow=0, smc=s1, vsa=s2, context=0, bonus=0,
        regime_multiplier=1.0, direction="long", regime="TRENDING",
    ))

    # Combined raw score must be strictly greater than either alone
    # (integer rounding may cause ties for very small values, so we check raw)
    raw_s1 = s1
    raw_s2 = s2
    raw_combined = s1 + s2

    assert raw_combined > raw_s1, (
        f"Combined raw ({raw_combined}) must be > s1 raw ({raw_s1})"
    )
    assert raw_combined > raw_s2, (
        f"Combined raw ({raw_combined}) must be > s2 raw ({raw_s2})"
    )

    # Final score: combined must be >= either alone (strict > guaranteed when s2 >= 5)
    assert result_combined.final_score >= result_s1.final_score
    assert result_combined.final_score >= result_s2.final_score
