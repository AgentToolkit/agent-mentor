import sys
import traceback
from time import time

from fastapi import APIRouter, Depends, HTTPException, Request

from agent_analytics.server.auth import SAMLUser, get_current_user
from agent_analytics.server.db.operations import UsageTracker
from agent_analytics.server.logger import logger
from agent_analytics.server.routes import get_tenant_id, instana_client, runtime_client

# Create router with tenant_id dependency
instana_router = APIRouter(
    prefix="/instana",
    tags=["Instana"],
    dependencies=[Depends(get_tenant_id)]
)

# Instana Routes
@instana_router.get("/{service_name}/traces")
async def get_instana_traces(
    request: Request,
    service_name: str,
    current_user: SAMLUser = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    start_time = time()
    try:
        if not service_name:
            raise HTTPException(status_code=500, detail="SERVICE_NAME not configured")

        # 6 hours - as the baseline because 7 days buckets miss the latest traces
        traces = instana_client.get_traces(
            service_name=service_name,
            window_size_ms=21600000,
            limit=100,
            tenant_id=tenant_id  # Pass tenant_id to the client
        )

        # 7 days
        traces += instana_client.get_traces(
            service_name=service_name,
            window_size_ms=604800000,
            limit=100,
            tenant_id=tenant_id  # Pass tenant_id to the client
        )

        formatted_traces = {}
        for item in traces:
            trace = item.get('trace', {})
            formatted_traces[trace.get('id')] = {
                'id': trace.get('id'),
                'startTime': trace.get('startTime'),
                'service': trace.get('service', {}).get('label')
            }

        result = list(formatted_traces.values())

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_instana_traces",
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
                "time_window_days": 7.5,
                "tenant_id": tenant_id
            }
        )

        return result
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error get_instana_traces: {error_msg}")
        traceback.print_exc()

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_instana_traces",
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

# Obsolete - No longer called from UI
@instana_router.get("/{service_name}/traces/{trace_id}")
async def get_instana_trace_details(
    request: Request,
    service_name: str,
    trace_id: str,
    current_user: SAMLUser = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    start_time = time()
    try:
        spans = instana_client.get_trace_details(trace_id, tenant_id=tenant_id)
        if not spans:
            raise HTTPException(status_code=404, detail="Trace not found")

        spans = instana_client.convert_to_base_spans(spans)

        result = await runtime_client.get_instana_artifacts(spans, tenant_id=tenant_id)
        result = result["tasks"]

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_instana_trace_details",
            element=f"{service_name}/{trace_id}",
            response_time_ms=(time() - start_time) * 1000,
            status_code=200,
            success=True,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            payload_size=sys.getsizeof(result),
            metadata={
                "task_count": len(result),
                "service": service_name,
                "tenant_id": tenant_id
            }
        )

        return result

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error get_instana_trace_details trace {trace_id}: {error_msg}")
        traceback.print_exc()

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_instana_trace_details",
            element=f"{service_name}/{trace_id}",
            response_time_ms=(time() - start_time) * 1000,
            status_code=500 if not isinstance(e, HTTPException) else e.status_code,
            success=False,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            error_message=error_msg,
            metadata={"tenant_id": tenant_id}
        )

        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=error_msg)
