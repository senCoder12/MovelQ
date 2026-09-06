from __future__ import annotations

import structlog
from datetime import date
from typing import Optional

from app.domain.entities import HistoricalBaseline
from app.domain.interfaces import BaselineRepository

logger = structlog.get_logger(__name__)


class BaselineService:
    def __init__(self, baseline_repository: BaselineRepository):
        self.baseline_repository = baseline_repository

    async def get_shift_baseline(
        self,
        business_unit: str,
        office: str,
        shift: str,
        direction: str,
        reference_date: date,
        lookback_days: int = 30
    ) -> HistoricalBaseline:
        logger.info(
            "Fetching shift baseline",
            business_unit=business_unit,
            office=office,
            shift=shift,
            direction=direction,
            lookback_days=lookback_days
        )

        data = await self.baseline_repository.get_shift_baseline(
            business_unit=business_unit,
            office=office,
            shift=shift,
            direction=direction,
            lookback_days=lookback_days,
            reference_date=reference_date
        )

        if not data:
            data = {}

        return HistoricalBaseline(
            scope=f"office:{office}|shift:{shift}|direction:{direction}",
            metric_name="shift_baseline",
            period_label=f"{lookback_days}d",
            mean=data.get("mean"),
            median=data.get("median"),
            p90=data.get("p90"),
            p95=data.get("p95"),
            sample_size=data.get("sample_size", 0)
        )
