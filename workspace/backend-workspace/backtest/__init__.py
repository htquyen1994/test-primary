"""Backtesting Engine — trade simulation, metrics, walk-forward, AI feedback."""

from backtest.models import TradeResult
from backtest.engine import BacktestingEngine
from backtest.metrics import compute_metrics, write_result_record
from backtest.walk_forward import WalkForwardAnalysis
from backtest.ai_feedback import find_underperformance_clusters, write_optimization_suggestions
from backtest.benchmark import generate_benchmark_table

__all__ = [
    "TradeResult", "BacktestingEngine",
    "compute_metrics", "write_result_record",
    "WalkForwardAnalysis",
    "find_underperformance_clusters", "write_optimization_suggestions",
    "generate_benchmark_table",
]
