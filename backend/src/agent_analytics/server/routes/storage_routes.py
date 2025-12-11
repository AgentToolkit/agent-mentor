import sys
import traceback
from datetime import UTC, datetime, timedelta
from time import time

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from agent_analytics.server.auth import SAMLUser, get_current_user
from agent_analytics.server.db.operations import UsageTracker
from agent_analytics.server.logger import logger
from agent_analytics.server.routes import get_tenant_id, runtime_client

# Create router with tenant_id dependency
storage_router = APIRouter(
    prefix="/storage",
    tags=["Storage"],
    dependencies=[Depends(get_tenant_id)]
)

# Create a new group
@storage_router.post("/{service_name}/groups")
async def create_group(
    request: Request,
    service_name: str,
    group_data: dict = Body(...),
    current_user: SAMLUser = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    start_time = time()
    try:
        group_name = group_data.get("name")
        trace_ids = group_data.get("traceIds", [])

        if not group_name:
            raise HTTPException(status_code=400, detail="Group name is required")

        if not trace_ids:
            raise HTTPException(status_code=400, detail="At least one trace ID is required")

        # Call the platform client method to create the group with tenant_id
        result = await runtime_client.create_group(
            service_name=service_name,
            group_name=group_name,
            traces_ids=trace_ids,
            tenant_id=tenant_id
        )

        await UsageTracker.log_action(
            username=current_user.username,
            action="create_group",
            element=service_name,
            response_time_ms=(time() - start_time) * 1000,
            status_code=200,
            success=True,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            payload_size=sys.getsizeof(result),
            metadata={
                "group_name": group_name,
                "trace_count": len(trace_ids),
                "service_name": service_name,
                "tenant_id": tenant_id
            }
        )

        return result
    except Exception as e:
        await runtime_client.cleanup(tenant_id)

        error_msg = str(e)
        logger.error(f"Error create_group: {error_msg}")
        traceback.print_exc()

        await UsageTracker.log_action(
            username=current_user.username,
            action="create_group",
            element=service_name,
            response_time_ms=(time() - start_time) * 1000,
            status_code=500,
            success=False,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            error_message=error_msg,
            metadata={"tenant_id": tenant_id}
        )

        raise HTTPException(status_code=500, detail=error_msg)

@storage_router.get("/{service_name}/groups/{group_id}/traces") # return all traces for service_name
async def get_group_traces(
    request: Request,
    service_name: str,
    group_id: str,
    current_user: SAMLUser = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    start_time = time()
    try:
        result = await runtime_client.get_group_traces(service_name, group_id, tenant_id=tenant_id)

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_group_traces",
            element=group_id,
            response_time_ms=(time() - start_time) * 1000,
            status_code=200,
            success=True,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            payload_size=sys.getsizeof(result),
            metadata={
                "trace_count": len(result["traces"]),
                "service_name": service_name,
                "group_id": group_id,
                "tenant_id": tenant_id
            }
        )

        return result
    except Exception as e:
        await runtime_client.cleanup(tenant_id)

        error_msg = str(e)
        logger.error(f"Error get_group_traces: {error_msg}")
        traceback.print_exc()

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_group_traces",
            element=group_id,
            response_time_ms=(time() - start_time) * 1000,
            status_code=500,
            success=False,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            error_message=error_msg,
            metadata={"tenant_id": tenant_id}
        )

        raise HTTPException(status_code=500, detail=error_msg)





# Get only traces for service_name (no trace details yet)
@storage_router.get("/{service_name}")
async def get_storage_traces(
    request: Request,
    service_name: str,
    startDate: str | None = None,
    endDate: str | None = None,
    minSpans: int | None = None,
    current_user: SAMLUser = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    start_time = time()
    try:
        # Process date parameters
        from_date = None
        to_date = None

        # If dates are provided in query parameters, use them
        if startDate:
            try:
                from_date = datetime.fromisoformat(startDate)
                # Ensure UTC timezone if not specified
                if from_date.tzinfo is None:
                    from_date = from_date.replace(tzinfo=UTC)
            except ValueError:
                raise Exception ("Invalid startDate format. Use ISO format (YYYY-MM-DD).")

        if endDate:
            try:
                to_date = datetime.fromisoformat(endDate)
                # Ensure UTC timezone if not specified
                if to_date.tzinfo is None:
                    to_date = to_date.replace(tzinfo=UTC)
                # Set time to end of day if only date is provided
                if to_date.hour == 0 and to_date.minute == 0 and to_date.second == 0:
                    to_date = to_date.replace(hour=23, minute=59, second=59)
            except ValueError:
                raise Exception ("Invalid endDate format. Use ISO format (YYYY-MM-DD).")

        # If no start date provided, default to 30 days back
        if not from_date:
            minutes_back = -(60 * 24 * 30)  # 30 days in minutes
            from_date = datetime.now(UTC) + timedelta(minutes=minutes_back)

        traces = await runtime_client.get_traces(service_name, from_date, to_date, tenant_id=tenant_id)

        # Filter traces by minimum spans count if minSpans is provided
        if minSpans is not None and minSpans > 0:
            traces = [trace for trace in traces if trace.get("spansNum", 0) >= minSpans]

        result = {
            "traces": traces,
            "groups": await runtime_client.get_groups(service_name, tenant_id=tenant_id)
        }

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_storage_traces",
            element=service_name,
            response_time_ms=(time() - start_time) * 1000,
            status_code=200,
            success=True,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            payload_size=sys.getsizeof(result),
            metadata={
                "trace_count": len(result["traces"]),
                "service_name": service_name,
                "time_window_days": 30,
                "min_spans_filter": minSpans,
                "tenant_id": tenant_id
            }
        )

        return result
    except Exception as e:
        await runtime_client.cleanup(tenant_id)

        error_msg = str(e)
        logger.error(f"Error get_storage_traces: {error_msg}")
        logger.error(traceback.format_exc())

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_storage_traces",
            element=service_name,
            response_time_ms=(time() - start_time) * 1000,
            status_code=500,
            success=False,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            error_message=error_msg,
            metadata={"tenant_id": tenant_id}
        )

        raise HTTPException(status_code=500, detail=error_msg)

### TODO: DEPRECATED?!?!
@storage_router.get("/{service_name}/traces") # return all traces for service_name
async def get_storage_service_details(
    request: Request,
    service_name: str,
    current_user: SAMLUser = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    start_time = time()
    try:
        # get traces for the past 30 days for the service_name
        minutes_back = -(60 * 24 * 30)
        from_date = datetime.now(UTC) + timedelta(minutes=minutes_back)
        result = await runtime_client.get_traces_with_content(service_name, from_date, None, tenant_id=tenant_id)

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_storage_trace_details",
            element=service_name,
            response_time_ms=(time() - start_time) * 1000,
            status_code=200,
            success=True,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            payload_size=sys.getsizeof(result),
            metadata={
                "trace_count": len(result),
                "service_name": service_name,
                "tenant_id": tenant_id
            }
        )

        return result
    except Exception as e:
        await runtime_client.cleanup(tenant_id)

        error_msg = str(e)
        logger.error(f"Error get_storage_service_details: {error_msg}")
        traceback.print_exc()

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_storage_trace_details",
            element=service_name,
            response_time_ms=(time() - start_time) * 1000,
            status_code=500,
            success=False,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            error_message=error_msg,
            metadata={"tenant_id": tenant_id}
        )

        raise HTTPException(status_code=500, detail=error_msg)

@storage_router.get("/{service_name}/traces/{trace_id}") # return all artifacts for (service and) traceid
async def get_storage_trace_details(
    request: Request,
    service_name: str,
    trace_id: str,
    spans: str | None = "false",
    current_user: SAMLUser = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    start_time = time()
    try:
        with_spans = spans.lower() in ('true', '1', 'yes', 'on')
        result = await runtime_client.get_trace_artifacts(trace_id, with_spans=with_spans, tenant_id=tenant_id)

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_storage_trace_details",
            element=trace_id,
            response_time_ms=(time() - start_time) * 1000,
            status_code=200,
            success=True,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            payload_size=sys.getsizeof(result),
            metadata={
                "trace_count": len(result),
                "trace_id": trace_id,
                "tenant_id": tenant_id
            }
        )

        return result
    except Exception as e:
        await runtime_client.cleanup(tenant_id)

        error_msg = str(e)
        logger.error(f"Error get_storage_trace_details: {error_msg}")
        import traceback
        traceback.print_exc()

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_storage_trace_details",
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


    # Add this route to your storage_router in the FastAPI file

@storage_router.get("/traces/{trace_id}/spans")
async def get_spans_for_trace(
    request: Request,
    trace_id: str,
    current_user: SAMLUser = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    start_time = time()
    try:
        result = await runtime_client.get_spans(trace_id, tenant_id=tenant_id)

        # Convert BaseSpanComposite objects to dictionaries for JSON response
        spans_data = [span.model_dump(mode='json') for span in result]

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_spans_for_trace",
            element=trace_id,
            response_time_ms=(time() - start_time) * 1000,
            status_code=200,
            success=True,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            payload_size=sys.getsizeof(spans_data),
            metadata={
                "trace_id": trace_id,
                "span_count": len(spans_data),
                "tenant_id": tenant_id
            }
        )

        return spans_data

    except Exception as e:
        await runtime_client.cleanup(tenant_id)

        error_msg = str(e)
        logger.error(f"Error get_spans_for_trace: {error_msg}")
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
