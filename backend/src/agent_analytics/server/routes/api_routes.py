import base64
import json
import sys
import traceback
from datetime import datetime
from time import time
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field, validator

from agent_analytics.server.auth import SAMLUser, get_current_user
from agent_analytics.server.db.operations import UsageTracker
from agent_analytics.server.logger import logger
from agent_analytics.server.routes import get_tenant_id, runtime_client
from agent_analytics.server.utils.api_queries import (
    get_spans_for_trace,
    search_traces_with_search_after,
)

# Create router with tenant_id dependency
api_router = APIRouter(
    prefix="/api/v1",
    tags=["API"],
    dependencies=[Depends(get_tenant_id)]
)

# Pydantic models based on the OpenAPI spec
class SpanCountRange(BaseModel):
    min: int | None = Field(None, ge=0)
    max: int | None = Field(None, ge=0)

class TraceSearchFilters(BaseModel):
    start_time: datetime
    end_time: datetime
    service_names: list[str] | None = []
    agent_ids: list[str] | None = []
    agent_names: list[str] | None = []
    user_ids: list[str] | None = []
    session_ids: list[str] | None = []
    span_count_range: SpanCountRange | None = None

class TraceSearchSort(BaseModel):
    field: str = Field("start_time", pattern="^(start_time|end_time)$")
    direction: str = Field("desc", pattern="^(asc|desc)$")

class TraceSearchQuery(BaseModel):
    filters: TraceSearchFilters
    sort: TraceSearchSort | None = None
    page_size: int = Field(50, ge=1, le=1000)
    cursor: dict | list | str | float | None = None
    include_root_spans: bool = False

    @validator('cursor')
    def validate_cursor(cls, v):
        if v is not None:
            # Cursor should be a valid JSON structure
            if isinstance(v, str):
                try:
                    json.loads(v)
                except:
                    # Try base64-decoded JSON
                    decoded = base64.urlsafe_b64decode(v.encode()).decode()
                    json.loads(decoded)
        return v

class SpansResponse(BaseModel):
    traceData: dict[str, Any]
    nextCursor: dict | list | str | float | None
    totalCount: int

class TraceSearchResponse(BaseModel):
    generatedAt: datetime
    originalQuery: TraceSearchQuery
    traceSummaries: list[dict[str, Any]]
    nextCursor: dict | list | str | float | None
    totalCount: int
    error: dict | None = None
    class Config:
        exclude_none = True

@api_router.get("/traces/{trace_id}/spans", response_model=SpansResponse)
async def get_spans_for_trace_endpoint(
    request: Request,
    trace_id: str = Path(..., pattern="^[a-fA-F0-9]{16,32}$"),
    page_size: int = Query(50, ge=1, le=1000),
    cursor: str | None = Query(None),
    current_user: SAMLUser = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Get all spans for a given trace ID with cursor-based pagination"""
    start_time = time()

    try:
        # Parse cursor if provided
        parsed_cursor = None
        if cursor:
            try:
                parsed_cursor = json.loads(cursor)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid cursor format. Must be valid JSON."
                )

        # Get tenant components for database client
        tenant_components, _ = await runtime_client.ensure_initialized(tenant_id)

        # Execute the query
        result = await get_spans_for_trace(
            tenant_components=tenant_components,
            tenant_id=tenant_id,
            trace_id=trace_id,
            page_size=page_size,
            cursor=parsed_cursor
        )

        # Log successful action
        await UsageTracker.log_action(
            username=current_user.username,
            action="get_spans_for_trace",
            element=trace_id,
            response_time_ms=(time() - start_time) * 1000,
            status_code=200,
            success=True,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            payload_size=sys.getsizeof(result),
            metadata={
                "trace_id": trace_id,
                "page_size": page_size,
                "total_count": result.get("total_count", 0),
                "tenant_id": tenant_id
            }
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        await runtime_client.cleanup(tenant_id)

        error_msg = str(e)
        logger.error(f"Error in get_spans_for_trace: {error_msg}")
        traceback.print_exc()

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_spans_for_trace",
            element=trace_id,
            response_time_ms=(time() - start_time) * 1000,
            status_code=500,
            success=False,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            error_message=error_msg,
            metadata={"tenant_id": tenant_id}
        )

        raise HTTPException(status_code=500, detail=error_msg)


good_example = {
    "filters": {
        "start_time": "2025-07-24T10:00:00Z",
        "end_time": "2025-07-24T12:00:00Z",
        "service_names": ["api-gateway", "user-service"],
        "agent_ids": [],
        "agent_names": [],
        "user_ids": ["user-12345"],
        "session_ids": [],
        "span_count_range": {
            "min": 5,
            "max": 100
        }
    },
    "sort": {
        "field": "start_time",
        "direction": "desc"
    },
    "page_size": 50,
    "cursor": None,
    "include_root_spans": False
}
@api_router.post("/traces/search", response_model=TraceSearchResponse)
async def search_traces_endpoint(
    request: Request,
    query: TraceSearchQuery = Body(..., example=good_example),
    current_user: SAMLUser = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Search traces with filters, sorting, and cursor-based pagination"""
    start_time = time()

    try:
        # Validate date range
        if query.filters.start_time >= query.filters.end_time:
            raise HTTPException(
                status_code=400,
                detail="start_time must be before end_time"
            )

        # Validate span count range if provided
        if query.filters.span_count_range:
            if (query.filters.span_count_range.min is not None and
                query.filters.span_count_range.max is not None and
                query.filters.span_count_range.min > query.filters.span_count_range.max):
                raise HTTPException(
                    status_code=400,
                    detail="span_count_range.min must be less than or equal to span_count_range.max"
                )

        # Set default sort if not provided
        if query.sort is None:
            query.sort = TraceSearchSort()

        # Get tenant components for database client
        tenant_components, _ = await runtime_client.ensure_initialized(tenant_id)

        # Execute the search
        result = await search_traces_with_search_after(
            tenant_components=tenant_components,
            tenant_id=tenant_id,
            query=query
        )

        # Add metadata to response
        result["generatedAt"] = datetime.utcnow()
        result["originalQuery"] = query

        # Log successful action
        await UsageTracker.log_action(
            username=current_user.username,
            action="search_traces",
            element="trace_search",
            response_time_ms=(time() - start_time) * 1000,
            status_code=200,
            success=True,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            payload_size=sys.getsizeof(result),
            metadata={
                "service_names": query.filters.service_names,
                "agent_ids": query.filters.agent_ids,
                "page_size": query.page_size,
                "total_count": result.get("total_count", 0),
                "results_count": len(result.get("trace_summaries", [])),
                "tenant_id": tenant_id
            }
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        await runtime_client.cleanup(tenant_id)

        error_msg = str(e)
        logger.error(f"Error in search_traces: {error_msg}")
        traceback.print_exc()

        await UsageTracker.log_action(
            username=current_user.username,
            action="search_traces",
            element="trace_search",
            response_time_ms=(time() - start_time) * 1000,
            status_code=500,
            success=False,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            error_message=error_msg,
            metadata={"tenant_id": tenant_id}
        )

        raise HTTPException(status_code=500, detail=error_msg)
