"""
Analytics API routes — performance report and tuning recommendations.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_analysis_engine
from api.schemas import PerformanceReportResponse, TuningReportResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/audit/analytics", tags=["analytics"])


@router.get("/performance")
def get_performance(
    analysis_engine=Depends(get_analysis_engine),
):
    if analysis_engine is None:
        raise HTTPException(status_code=503, detail="Analysis engine not initialized")
    try:
        report = analysis_engine.get_performance_report()
        return report
    except Exception as exc:
        logger.error("get_performance failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/tuning")
def get_tuning(
    analysis_engine=Depends(get_analysis_engine),
):
    if analysis_engine is None:
        raise HTTPException(status_code=503, detail="Analysis engine not initialized")
    try:
        report = analysis_engine.get_tuning_recommendations()
        return report
    except Exception as exc:
        logger.error("get_tuning failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
