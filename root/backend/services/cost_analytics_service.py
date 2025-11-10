# ABOUTME: Cost analytics service for multi-blog reporting and analysis
# ABOUTME: Provides aggregated cost insights, weekly/monthly reports, and cost trends

"""
Cost Analytics Service for comprehensive multi-blog cost analysis and reporting.

Provides:
- Multi-blog cost aggregation
- Time-based analytics (daily, weekly, monthly, yearly)
- Cost trend analysis
- Cost by model and agent breakdowns
- Cost forecasting based on historical data
- Report generation and export
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, asdict
import json

from backend.models.database import get_db_manager, CostTracking, Project
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class TimeRange(Enum):
    """Time range for analytics."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CUSTOM = "custom"


@dataclass
class CostDataPoint:
    """Single cost data point for timeseries."""
    timestamp: str
    cost: float
    token_count: int
    call_count: int
    agent_name: Optional[str] = None
    model_name: Optional[str] = None


class CostAnalyticsService:
    """Service for comprehensive cost analytics and reporting."""

    def __init__(self, db_url: str = None):
        """Initialize analytics service with database connection."""
        self.db_manager = get_db_manager(db_url or "sqlite:///data/projects.db")
        self.db_manager.init_database()
        logger.info("CostAnalyticsService initialized")

    @property
    def session(self) -> Session:
        """Get database session."""
        return self.db_manager.get_session()

    async def get_multi_project_cost_summary(
        self,
        project_ids: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated cost summary across multiple projects.

        Args:
            project_ids: List of project IDs to include. If None, includes all.
            start_date: Start date for cost analysis
            end_date: End date for cost analysis

        Returns:
            Aggregated cost summary dictionary
        """
        try:
            session = self.session
            query = session.query(CostTracking)

            if project_ids:
                query = query.filter(CostTracking.project_id.in_(project_ids))

            if start_date:
                query = query.filter(CostTracking.created_at >= start_date)

            if end_date:
                query = query.filter(CostTracking.created_at <= end_date)

            # Get all records
            records = query.all()
            session.close()

            if not records:
                return self._empty_summary()

            # Aggregate data
            total_cost = sum(r.cost for r in records)
            total_input_tokens = sum(r.input_tokens for r in records)
            total_output_tokens = sum(r.output_tokens for r in records)
            total_tokens = total_input_tokens + total_output_tokens
            call_count = len(records)

            # Cost by agent
            cost_by_agent = {}
            for record in records:
                if record.agent_name not in cost_by_agent:
                    cost_by_agent[record.agent_name] = {
                        "cost": 0,
                        "calls": 0,
                        "input_tokens": 0,
                        "output_tokens": 0
                    }
                cost_by_agent[record.agent_name]["cost"] += record.cost
                cost_by_agent[record.agent_name]["calls"] += 1
                cost_by_agent[record.agent_name]["input_tokens"] += record.input_tokens
                cost_by_agent[record.agent_name]["output_tokens"] += record.output_tokens

            # Cost by model
            cost_by_model = {}
            for record in records:
                model = record.model_used or "unknown"
                if model not in cost_by_model:
                    cost_by_model[model] = {
                        "cost": 0,
                        "calls": 0,
                        "input_tokens": 0,
                        "output_tokens": 0
                    }
                cost_by_model[model]["cost"] += record.cost
                cost_by_model[model]["calls"] += 1
                cost_by_model[model]["input_tokens"] += record.input_tokens
                cost_by_model[model]["output_tokens"] += record.output_tokens

            # Average cost per call
            avg_cost_per_call = total_cost / call_count if call_count > 0 else 0

            return {
                "total_cost": round(total_cost, 6),
                "total_tokens": total_tokens,
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "total_calls": call_count,
                "average_cost_per_call": round(avg_cost_per_call, 6),
                "cost_by_agent": cost_by_agent,
                "cost_by_model": cost_by_model,
                "date_range": {
                    "start": start_date.isoformat() if start_date else None,
                    "end": end_date.isoformat() if end_date else None
                }
            }

        except Exception as e:
            logger.error(f"Error getting multi-project cost summary: {e}")
            return self._empty_summary()

    async def get_time_series_costs(
        self,
        time_range: TimeRange,
        project_ids: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[CostDataPoint]:
        """
        Get cost data points over time.

        Args:
            time_range: Granularity (daily, weekly, monthly, yearly)
            project_ids: Project IDs to include
            start_date: Start date
            end_date: End date

        Returns:
            List of cost data points ordered by time
        """
        try:
            session = self.session
            query = session.query(CostTracking)

            if project_ids:
                query = query.filter(CostTracking.project_id.in_(project_ids))

            if start_date:
                query = query.filter(CostTracking.created_at >= start_date)

            if end_date:
                query = query.filter(CostTracking.created_at <= end_date)

            records = query.order_by(CostTracking.created_at).all()
            session.close()

            if not records:
                return []

            # Group by time range
            data_points = self._aggregate_by_time_range(records, time_range)
            return data_points

        except Exception as e:
            logger.error(f"Error getting time series costs: {e}")
            return []

    def _aggregate_by_time_range(
        self,
        records: List[CostTracking],
        time_range: TimeRange
    ) -> List[CostDataPoint]:
        """Aggregate cost records by time range."""
        grouped = {}

        for record in records:
            # Determine grouping key based on time_range
            timestamp = record.created_at
            if time_range == TimeRange.DAILY:
                key = timestamp.date().isoformat()
            elif time_range == TimeRange.WEEKLY:
                week_start = timestamp.date() - timedelta(days=timestamp.weekday())
                key = week_start.isoformat()
            elif time_range == TimeRange.MONTHLY:
                key = timestamp.strftime("%Y-%m")
            elif time_range == TimeRange.YEARLY:
                key = timestamp.strftime("%Y")
            else:
                key = timestamp.isoformat()

            if key not in grouped:
                grouped[key] = {
                    "cost": 0,
                    "token_count": 0,
                    "call_count": 0,
                    "timestamp": key
                }

            grouped[key]["cost"] += record.cost
            grouped[key]["token_count"] += record.input_tokens + record.output_tokens
            grouped[key]["call_count"] += 1

        # Convert to data points
        data_points = [
            CostDataPoint(
                timestamp=key,
                cost=round(data["cost"], 6),
                token_count=data["token_count"],
                call_count=data["call_count"]
            )
            for key, data in sorted(grouped.items())
        ]

        return data_points

    async def get_weekly_report(
        self,
        project_ids: Optional[List[str]] = None,
        weeks_back: int = 1
    ) -> Dict[str, Any]:
        """
        Get weekly cost report.

        Args:
            project_ids: Project IDs to include
            weeks_back: Number of weeks to look back (0 = current week)

        Returns:
            Weekly cost report
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(weeks=weeks_back + 1)

        summary = await self.get_multi_project_cost_summary(
            project_ids=project_ids,
            start_date=start_date,
            end_date=end_date
        )

        time_series = await self.get_time_series_costs(
            TimeRange.DAILY,
            project_ids=project_ids,
            start_date=start_date,
            end_date=end_date
        )

        return {
            "report_type": "weekly",
            "generated_at": datetime.utcnow().isoformat(),
            "summary": summary,
            "daily_breakdown": [asdict(dp) for dp in time_series],
            "week_ending": end_date.isoformat()
        }

    async def get_monthly_report(
        self,
        project_ids: Optional[List[str]] = None,
        months_back: int = 0
    ) -> Dict[str, Any]:
        """
        Get monthly cost report.

        Args:
            project_ids: Project IDs to include
            months_back: Number of months to look back (0 = current month)

        Returns:
            Monthly cost report
        """
        end_date = datetime.utcnow()
        # Calculate start of month
        start_date = end_date.replace(day=1)
        if months_back > 0:
            for _ in range(months_back):
                start_date = (start_date - timedelta(days=1)).replace(day=1)

        summary = await self.get_multi_project_cost_summary(
            project_ids=project_ids,
            start_date=start_date,
            end_date=end_date
        )

        time_series = await self.get_time_series_costs(
            TimeRange.DAILY,
            project_ids=project_ids,
            start_date=start_date,
            end_date=end_date
        )

        return {
            "report_type": "monthly",
            "generated_at": datetime.utcnow().isoformat(),
            "summary": summary,
            "daily_breakdown": [asdict(dp) for dp in time_series],
            "month": start_date.strftime("%Y-%m"),
            "month_end": end_date.isoformat()
        }

    async def get_cost_trends(
        self,
        project_ids: Optional[List[str]] = None,
        num_periods: int = 12,
        time_range: TimeRange = TimeRange.WEEKLY
    ) -> Dict[str, Any]:
        """
        Get cost trends over multiple periods.

        Args:
            project_ids: Project IDs to include
            num_periods: Number of periods to analyze
            time_range: Time range granularity

        Returns:
            Trend analysis with projections
        """
        try:
            end_date = datetime.utcnow()

            # Calculate start date based on time range
            if time_range == TimeRange.DAILY:
                start_date = end_date - timedelta(days=num_periods)
            elif time_range == TimeRange.WEEKLY:
                start_date = end_date - timedelta(weeks=num_periods)
            elif time_range == TimeRange.MONTHLY:
                start_date = end_date - timedelta(days=30 * num_periods)
            else:
                start_date = end_date - timedelta(days=365 * num_periods)

            time_series = await self.get_time_series_costs(
                time_range=time_range,
                project_ids=project_ids,
                start_date=start_date,
                end_date=end_date
            )

            if not time_series:
                return {
                    "status": "no_data",
                    "trend": None,
                    "forecast": None
                }

            # Calculate trend
            costs = [dp.cost for dp in time_series]
            avg_cost = sum(costs) / len(costs) if costs else 0
            trend_direction = "increasing" if costs[-1] > costs[0] else "decreasing"
            trend_percentage = ((costs[-1] - costs[0]) / costs[0] * 100) if costs[0] > 0 else 0

            # Simple linear forecast (next period)
            if len(costs) > 1:
                avg_change = (costs[-1] - costs[0]) / len(costs)
                forecasted_cost = costs[-1] + avg_change
            else:
                forecasted_cost = costs[-1] if costs else 0

            return {
                "status": "success",
                "time_range": time_range.value,
                "num_periods": num_periods,
                "data_points": [asdict(dp) for dp in time_series],
                "average_cost_per_period": round(avg_cost, 6),
                "trend": {
                    "direction": trend_direction,
                    "percentage_change": round(trend_percentage, 2)
                },
                "forecast": {
                    "next_period_estimated": round(forecasted_cost, 6),
                    "method": "linear_extrapolation"
                }
            }

        except Exception as e:
            logger.error(f"Error calculating cost trends: {e}")
            return {"status": "error", "message": str(e)}

    async def compare_projects(
        self,
        project_ids: List[str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Compare costs across multiple projects.

        Args:
            project_ids: Project IDs to compare
            start_date: Start date
            end_date: End date

        Returns:
            Comparison data
        """
        try:
            projects_data = {}

            for project_id in project_ids:
                summary = await self.get_multi_project_cost_summary(
                    project_ids=[project_id],
                    start_date=start_date,
                    end_date=end_date
                )
                projects_data[project_id] = summary

            # Get project names
            session = self.session
            project_names = {p.id: p.name for p in session.query(Project).filter(
                Project.id.in_(project_ids)
            ).all()}
            session.close()

            return {
                "comparison_type": "project",
                "generated_at": datetime.utcnow().isoformat(),
                "projects": [
                    {
                        "id": pid,
                        "name": project_names.get(pid, pid),
                        **projects_data[pid]
                    }
                    for pid in project_ids
                ],
                "cheapest_project": min(
                    projects_data.items(),
                    key=lambda x: x[1]["total_cost"]
                )[0] if projects_data else None,
                "most_expensive_project": max(
                    projects_data.items(),
                    key=lambda x: x[1]["total_cost"]
                )[0] if projects_data else None
            }

        except Exception as e:
            logger.error(f"Error comparing projects: {e}")
            return {"status": "error", "message": str(e)}

    def _empty_summary(self) -> Dict[str, Any]:
        """Return empty summary structure."""
        return {
            "total_cost": 0.0,
            "total_tokens": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_calls": 0,
            "average_cost_per_call": 0.0,
            "cost_by_agent": {},
            "cost_by_model": {},
            "date_range": {"start": None, "end": None}
        }
