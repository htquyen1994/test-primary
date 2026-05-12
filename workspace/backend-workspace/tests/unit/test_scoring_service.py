"""
Unit tests for ScoringService ATR-based SL/TP computation.

Satisfies: TASK-02 — ATR-based SL/TP replaces hardcoded 2%/3%
Requirements: SL = 1.5×ATR, TP1 net R:R ≥ 1.5 after 0.2% round-trip fees.
"""

from __future__ import annotations

import math
import pytest

from engine.scoring_service import (
    ScoringService,
    SL_ATR_MULT,
    TP1_RR,
    TP2_RR,
    MIN_NET_RR,
    DEFAULT_FEE_RATE,
)


@pytest.fixture
def svc():
    return ScoringService()


class TestComputeSlTp:

    def test_long_stop_loss_below_entry(self, svc):
        stop_loss, tp1, tp2, gross_rr, net_rr = svc._compute_sl_tp(50000.0, 500.0, "long")
        assert stop_loss < 50000.0

    def test_long_tp1_above_entry(self, svc):
        stop_loss, tp1, tp2, gross_rr, net_rr = svc._compute_sl_tp(50000.0, 500.0, "long")
        assert tp1 > 50000.0

    def test_long_tp2_above_tp1(self, svc):
        _, tp1, tp2, _, _ = svc._compute_sl_tp(50000.0, 500.0, "long")
        assert tp2 > tp1

    def test_short_stop_loss_above_entry(self, svc):
        stop_loss, _, _, _, _ = svc._compute_sl_tp(50000.0, 500.0, "short")
        assert stop_loss > 50000.0

    def test_short_tp1_below_entry(self, svc):
        _, tp1, _, _, _ = svc._compute_sl_tp(50000.0, 500.0, "short")
        assert tp1 < 50000.0

    def test_short_tp2_below_tp1(self, svc):
        _, tp1, tp2, _, _ = svc._compute_sl_tp(50000.0, 500.0, "short")
        assert tp2 < tp1

    def test_sl_distance_equals_atr_mult(self, svc):
        entry, atr = 50000.0, 500.0
        stop_loss, _, _, _, _ = svc._compute_sl_tp(entry, atr, "long")
        sl_dist = entry - stop_loss
        assert math.isclose(sl_dist, atr * SL_ATR_MULT, rel_tol=1e-9)

    def test_tp1_distance_equals_rr_times_sl(self, svc):
        entry, atr = 50000.0, 500.0
        stop_loss, tp1, _, _, _ = svc._compute_sl_tp(entry, atr, "long")
        sl_dist = entry - stop_loss
        tp1_dist = tp1 - entry
        assert math.isclose(tp1_dist, sl_dist * TP1_RR, rel_tol=1e-9)

    def test_tp2_distance_equals_rr_times_sl(self, svc):
        entry, atr = 50000.0, 500.0
        stop_loss, _, tp2, _, _ = svc._compute_sl_tp(entry, atr, "long")
        sl_dist = entry - stop_loss
        tp2_dist = tp2 - entry
        assert math.isclose(tp2_dist, sl_dist * TP2_RR, rel_tol=1e-9)

    def test_gross_rr_equals_tp1_rr_constant(self, svc):
        _, _, _, gross_rr, _ = svc._compute_sl_tp(50000.0, 500.0, "long")
        assert math.isclose(gross_rr, TP1_RR, rel_tol=1e-9)

    def test_net_rr_below_gross_rr(self, svc):
        """Fees always reduce net R:R below gross R:R."""
        _, _, _, gross_rr, net_rr = svc._compute_sl_tp(50000.0, 500.0, "long")
        assert net_rr < gross_rr

    def test_net_rr_meets_minimum_typical_atr(self, svc):
        """Typical ATR (1% of price) must yield net R:R >= MIN_NET_RR."""
        entry = 50000.0
        atr = entry * 0.01 / SL_ATR_MULT  # back-calculate ATR so sl_pct = 1%
        _, _, _, _, net_rr = svc._compute_sl_tp(entry, atr, "long")
        assert net_rr >= MIN_NET_RR, f"net_rr={net_rr} < MIN_NET_RR={MIN_NET_RR}"

    def test_net_rr_meets_minimum_for_1_5pct_sl(self, svc):
        """SL = 1.5% of entry (canonical example) must clear MIN_NET_RR."""
        entry = 50000.0
        # sl_pct = 0.015 → sl_dist = 750 → atr = 750 / SL_ATR_MULT = 500
        atr = 750.0 / SL_ATR_MULT
        _, _, _, _, net_rr = svc._compute_sl_tp(entry, atr, "long")
        assert net_rr >= MIN_NET_RR, f"net_rr={net_rr} < MIN_NET_RR={MIN_NET_RR}"

    def test_net_rr_formula_symmetry_long_short(self, svc):
        """Long and short with same ATR produce identical net R:R."""
        entry, atr = 50000.0, 600.0
        _, _, _, _, net_rr_long = svc._compute_sl_tp(entry, atr, "long")
        _, _, _, _, net_rr_short = svc._compute_sl_tp(entry, atr, "short")
        assert math.isclose(net_rr_long, net_rr_short, rel_tol=1e-9)

    def test_output_values_are_positive(self, svc):
        stop_loss, tp1, tp2, gross_rr, net_rr = svc._compute_sl_tp(50000.0, 500.0, "long")
        assert stop_loss > 0
        assert tp1 > 0
        assert tp2 > 0
        assert gross_rr > 0
        assert net_rr > 0

    def test_custom_fee_rate_reduces_net_rr(self, svc):
        """Higher fee rate reduces net R:R."""
        _, _, _, _, net_low_fee = svc._compute_sl_tp(50000.0, 500.0, "long", fee_rate=0.001)
        _, _, _, _, net_high_fee = svc._compute_sl_tp(50000.0, 500.0, "long", fee_rate=0.005)
        assert net_high_fee < net_low_fee


class TestSlTpConstants:
    """Sanity checks on module constants to prevent accidental regression."""

    def test_sl_atr_mult_is_1_5(self):
        assert SL_ATR_MULT == 1.5

    def test_tp1_rr_is_2_0(self):
        assert TP1_RR == 2.0

    def test_tp2_rr_is_3_0(self):
        assert TP2_RR == 3.0

    def test_min_net_rr_is_1_5(self):
        assert MIN_NET_RR == 1.5

    def test_default_fee_rate_is_0_1pct(self):
        assert DEFAULT_FEE_RATE == 0.001

    def test_tp1_rr_gt_min_net_rr(self):
        """TP1_RR must exceed MIN_NET_RR to leave room for fees."""
        assert TP1_RR > MIN_NET_RR

    def test_tp2_rr_gt_tp1_rr(self):
        assert TP2_RR > TP1_RR
