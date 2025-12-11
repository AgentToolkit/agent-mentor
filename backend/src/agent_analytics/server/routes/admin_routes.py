import html
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from agent_analytics.server.auth import SAMLUser, get_current_user, validate_admin_api_key
from agent_analytics.server.db.operations import LoginTracker, UsageTracker, UserActionRecord
from agent_analytics.server.logger import logger
from agent_analytics.server.utils.admin_queries import get_tenant_statistics
from agent_analytics.runtime.api.initialization import ensure_tenant_initialized
from agent_analytics.server.routes import get_tenant_id, runtime_client

# Pydantic models for tenant stats response
class StatsPeriod(BaseModel):
    start: str
    end: str


class TraceStats(BaseModel):
    total: int
    daily: dict[str, int]


class IssueStats(BaseModel):
    total: int
    daily: dict[str, int]
    by_plugin_metadata_id: dict[str, int]
    by_level: dict[str, int]


class TraceSuccessMetrics(BaseModel):
    total_traces: int
    traces_with_issues: int
    traces_without_issues: int
    success_rate: float


class SpanStats(BaseModel):
    total: int
    daily: dict[str, int]
    unique_traces: int
    avg_spans_per_trace: float
    daily_avg_spans_per_trace: dict[str, float]


class TaskStats(BaseModel):
    total: int
    daily: dict[str, int]


class TenantStats(BaseModel):
    """Stats for a single tenant"""
    traces: TraceStats
    issues: IssueStats
    trace_success_metrics: TraceSuccessMetrics
    spans: SpanStats
    tasks: TaskStats


class AggregatedTotals(BaseModel):
    """Aggregated totals across all tenants"""
    traces: TraceStats
    issues: IssueStats
    trace_success_metrics: TraceSuccessMetrics
    spans: SpanStats
    tasks: TaskStats


class TenantStatsResponse(BaseModel):
    period: StatsPeriod
    tenants: dict[str, TenantStats]
    totals: AggregatedTotals


# Create router with admin API key validation at router level
admin_router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin"],
    dependencies=[Depends(validate_admin_api_key)]
)

# Admin Routes
@admin_router.get("/login-history")
async def get_login_history(
    days: int = 7,
    current_user: SAMLUser = Depends(get_current_user)
):
    return await LoginTracker.get_login_history(days)

@admin_router.get("/user-logins/{username}")
async def get_user_logins(
    username: str,
    current_user: SAMLUser = Depends(get_current_user)
):
    return await LoginTracker.get_user_logins(username)

@admin_router.get("/usage-stats")
async def get_usage_stats(
    days: int = 30,
    current_user: SAMLUser = Depends(get_current_user)
):
    return await UsageTracker.get_action_stats(days)

@admin_router.get("/user-usage/{username}")
async def get_user_usage(
    username: str,
    days: int = 30,
    current_user: SAMLUser = Depends(get_current_user)
):
    return await UsageTracker.get_user_usage(username, days)

@admin_router.get("/actions-dump", response_model=list[UserActionRecord])
async def get_actions_dump(
    days: int = 7,
    current_user: SAMLUser = Depends(get_current_user)
):
    return await UsageTracker.dump_recent_actions(days)


@admin_router.get("/tenant-stats", response_model=TenantStatsResponse)
async def get_tenant_stats(
    tenant_id: str | None = Query(
        default=None,
        description="Tenant ID to filter statistics. If not provided, queries all tenants."
    ),
    start_date: datetime | None = Query(
        default=None,
        description="Start date for statistics (ISO format). Defaults to 7 days ago."
    ),
    end_date: datetime | None = Query(
        default=None,
        description="End date for statistics (ISO format). Defaults to now."
    ),
    current_user: SAMLUser = Depends(get_current_user)
):
    """
    Get tenant-level statistics with daily breakdown.

    Returns counts for:
    - Traces (total and daily)
    - Issues (total, daily, by plugin_metadata_id, by severity level)
    - Spans (total, daily, unique traces, average spans per trace)
    - Tasks (total and daily)

    Time span is capped at 30 days maximum. If not specified, defaults to last 7 days.
    """
    # Set defaults
    if end_date is None:
        end_date = datetime.now(UTC)
    if start_date is None:
        start_date = end_date - timedelta(days=7)

    # Validate time span (max 30 days)
    time_span = end_date - start_date
    max_days = 30
    if time_span.days > max_days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Time span cannot exceed {max_days} days. Requested: {time_span.days} days."
        )

    if start_date >= end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before end_date"
        )

    try:
        # Initialize tenant components (use default tenant for DB access)
        # The tenant_id parameter filters the data, not the connection
        tenant_components, _, _ = await ensure_tenant_initialized(None)

        logger.info(
            f"Fetching tenant stats for tenant_id={tenant_id}, "
            f"period={start_date.isoformat()} to {end_date.isoformat()}"
        )

        stats = await get_tenant_statistics(
            tenant_components=tenant_components,
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date
        )

        return stats

    except TypeError as e:
        # Handle case where DB client is not ES/OS
        logger.error(f"Database type error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tenant statistics require Elasticsearch or OpenSearch backend"
        ) from e
    except ValueError as e:
        logger.error(f"Value error in tenant stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) from e
    except Exception as e:
        logger.error(f"Error fetching tenant statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tenant statistics: {str(e)}"
        ) from e


@admin_router.get("/config/log-level/{logger_name}/{level}")
async def change_log_level(logger_name: str, level: str):
    safe_logger_name = html.escape(logger_name)
    safe_level = html.escape(level.upper())

    if hasattr(logging, safe_level):
        logger.setLevel(getattr(logging, safe_level))
        return {"message": f"Log level for {safe_logger_name} changed to {safe_level}"}
    else:
        return {"error": f"Invalid log level: {safe_level}"}

@admin_router.post("/config/tenant")
async def set_tenant(request: Request,
                    tenant_id: str = Depends(get_tenant_id),
                    config: dict = Body(...),
        ):
    try:
        runtime_client.set_tenant_config(tenant_id, config)

        await runtime_client.ensure_initialized(tenant_id)
        await runtime_client.register_analytics(tenant_id)

        return {"message": "Tenant registered"}

    except Exception as e:
        await runtime_client.cleanup(tenant_id)

        error_msg = str(e)
        logger.error(f"Error set_tenant: {error_msg}")
        import traceback
        traceback.print_exc()

        raise HTTPException(status_code=500, detail=error_msg)