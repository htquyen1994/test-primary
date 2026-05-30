"""
Threshold Optimization Package
================================
Automated tuning of scoring weights and thresholds based on labeled outcomes.

Modules:
  outcome_loader     — Load signal_log + outcomes, join into DataFrame
  threshold_analyzer — Sweep threshold → precision/recall/EV curves
  weight_analyzer    — Module correlation analysis + coordinate-descent optimization
  regime_analyzer    — Per-regime precision breakdown
  recommender        — Generate JSON recommendation with CI
  config_applier     — Apply recommendation to DB TradingParams (--apply only)
  report_writer      — Write markdown tuning report

Pipeline:
  OutcomeLoader → ThresholdAnalyzer + WeightAnalyzer + RegimeAnalyzer
               → Recommender → (optional) ConfigApplier → ReportWriter
"""
