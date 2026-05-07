"""
Signal Scorer
==============
Aggregates all module scores, applies Regime Multiplier, normalizes to [0, 100].

Formula:
    raw   = OrderFlow(0-35) + SMC(0-30) + VSA+VolProfile(0-30) + Context(0-15) + Bonus(0-15)
    final = min(round(raw * regime_multiplier / 125 * 100), 100)

Classification:
    ALERT  : final >= alert_threshold  (default 75)
    WATCH  : final >= watch_threshold  (default 55)
    IGNORE : final < watch_threshold

PARABOLIC regime: suppress all Short signals (return IGNORE regardless of score).

Satisfies: Requirements 6.1–6.6, 13.5
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Maximum possible raw score (sum of all module maxima)
MAX_RAW_SCORE = 125.0  # 35 + 30 + 30 + 15 + 15

# Default thresholds (configurable via config.yaml)
DEFAULT_ALERT_THRESHOLD = 75
DEFAULT_WATCH_THRESHOLD = 55


@dataclass
class ScoreInput:
    """All module scores fed into the Signal Scorer."""
    order_flow: float = 0.0     # 0–35 pts
    smc: float = 0.0            # 0–30 pts
    vsa: float = 0.0            # 0–30 pts
    context: float = 0.0        # 0–15 pts
    bonus: float = 0.0          # 0–15 pts (confluence bonus)
    regime_multiplier: float = 1.0
    direction: str = "long"     # "long" | "short"
    regime: str = "RANGING"     # for PARABOLIC short suppression


@dataclass
class ScoreOutput:
    """Result of the Signal Scorer."""
    raw_score: float
    final_score: int            # [0, 100]
    classification: str         # "ALERT" | "WATCH" | "IGNORE"
    suppressed: bool = False    # True if short suppressed in PARABOLIC


class SignalScorer:
    """
    Aggregates module scores and produces a normalized final score.

    Satisfies: Requirements 6.1–6.6, 13.5
    """

    def __init__(
        self,
        alert_threshold: int = DEFAULT_ALERT_THRESHOLD,
        watch_threshold: int = DEFAULT_WATCH_THRESHOLD,
    ) -> None:
        if watch_threshold >= alert_threshold:
            raise ValueError(
                f"watch_threshold ({watch_threshold}) must be less than "
                f"alert_threshold ({alert_threshold})"
            )
        self.alert_threshold = alert_threshold
        self.watch_threshold = watch_threshold

    @classmethod
    def from_config(cls, config) -> "SignalScorer":
        """Create from validated AppConfig."""
        t = config.strategy.score_threshold
        return cls(
            alert_threshold=t.alert,
            watch_threshold=t.watch,
        )

    def score(self, inputs: ScoreInput) -> ScoreOutput:
        """
        Compute the final normalized score.

        Args:
            inputs: ScoreInput with all module scores and regime info

        Returns:
            ScoreOutput with final_score in [0, 100] and classification

        Satisfies: Requirements 6.1, 6.2, 6.3, 6.5, 13.5
        """
        # PARABOLIC regime: suppress all Short signals (Req 13.5)
        if inputs.regime == "PARABOLIC" and inputs.direction == "short":
            logger.debug(
                "Short signal suppressed in PARABOLIC regime "
                "(direction=%s, regime=%s)",
                inputs.direction, inputs.regime,
            )
            return ScoreOutput(
                raw_score=0.0,
                final_score=0,
                classification="IGNORE",
                suppressed=True,
            )

        # Clamp each module score to its maximum
        of_score = min(max(inputs.order_flow, 0.0), 35.0)
        smc_score = min(max(inputs.smc, 0.0), 30.0)
        vsa_score = min(max(inputs.vsa, 0.0), 30.0)
        ctx_score = min(max(inputs.context, 0.0), 15.0)
        bonus = min(max(inputs.bonus, 0.0), 15.0)

        raw = of_score + smc_score + vsa_score + ctx_score + bonus

        # Apply regime multiplier and normalize to [0, 100] (Req 6.3)
        multiplier = max(0.0, min(inputs.regime_multiplier, 1.0))
        final = min(round(raw * multiplier / MAX_RAW_SCORE * 100), 100)
        final = max(0, final)  # ensure non-negative

        classification = self.classify(final)

        return ScoreOutput(
            raw_score=raw,
            final_score=final,
            classification=classification,
            suppressed=False,
        )

    def classify(self, final_score: int) -> str:
        """
        Classify a final score into ALERT / WATCH / IGNORE.

        Satisfies: Requirement 6.5
        """
        if final_score >= self.alert_threshold:
            return "ALERT"
        elif final_score >= self.watch_threshold:
            return "WATCH"
        return "IGNORE"
