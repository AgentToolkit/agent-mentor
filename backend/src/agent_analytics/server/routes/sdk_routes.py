import sys
import traceback
from time import time

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field

from agent_analytics.sdk.client import AgentOpsClient
from agent_analytics.server.auth import SAMLUser, get_current_user
from agent_analytics.server.db.operations import UsageTracker
from agent_analytics.server.logger import logger
from agent_analytics.server.routes import get_agentops_client, get_tenant_id
from agent_analytics.server.utils.helper_utils import create_trace_group_name

# Create router
sdk_router = APIRouter(
    prefix="/api/v1",
    tags=["API"]
)

@sdk_router.get("/trace_group/{trace_group_id}")
async def get_trace_group_artifacts(
    request: Request,
    trace_group_id: str = Path(..., description="Unique identifier of the trace group to visualize"),
    current_user: SAMLUser = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
    client: AgentOpsClient = Depends(get_agentops_client)
):
    start_time = time()


    try:
        # Process the trace group to generate workflow (or fetch if already exists)
        process_result = await client.trace_groups.process([trace_group_id])

        # Extract the result for this specific trace group
        if not process_result["results"]:
            raise HTTPException(status_code=500, detail="No results returned from workflow processing")

        trace_group_result = process_result["results"][0]

        # Check if processing failed
        if trace_group_result["status"] == "failed":
            error_msg = trace_group_result.get("error", "Workflow processing failed")
            raise HTTPException(status_code=500, detail=error_msg)

        if trace_group_result["status"] == "error":
            error_msg = trace_group_result.get("error", "Unknown error during processing")
            raise HTTPException(status_code=500, detail=error_msg)

        # Transform to expected response format
        result = {
            "workflows_metrics": trace_group_result.get("metrics", []),
            "workflows": trace_group_result.get("workflow"),
            "trace_group_metrics": trace_group_result.get("trace_group_aggregate_metrics", []),
            "error": trace_group_result.get("error")
        }

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_workflow",
            element=trace_group_id,
            response_time_ms=(time() - start_time) * 1000,
            status_code=200,
            success=True,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            payload_size=sys.getsizeof(result),
            metadata={
                "workflow": result.get("workflows"),
                "metrics": len(result.get("metrics", [])),
                "failure": result.get("error"),
                "status": trace_group_result["status"],
                "workflow_already_existed": trace_group_result.get("workflow_already_existed", False)
            }
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in get_trace_group: {error_msg}")
        traceback.print_exc()

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_trace_group",
            element=trace_group_id,
            response_time_ms=(time() - start_time) * 1000,
            status_code=500,
            success=False,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            error_message=error_msg,
            metadata={"tenant_id": tenant_id}
        )

        raise HTTPException(status_code=500, detail=error_msg) from e

# Create trace group for the specified trace - Request/Response models and route
class CreateTraceGroupRequest(BaseModel):
    trace_ids: list[str] = Field(..., min_length=1, description="List of trace IDs to group together")


class TraceGroupResponse(BaseModel):
    trace_group_id: str = Field(..., description="Unique identifier for the created trace group")


@sdk_router.post("/trace_group", status_code=201, response_model=TraceGroupResponse)
async def create_trace_group(
    request: Request,
    body: CreateTraceGroupRequest,
    name: str | None = Query(None, description="Optional name for the trace group"),
    current_user: SAMLUser = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
    client: AgentOpsClient = Depends(get_agentops_client)
):
    """
    Create a trace group from trace IDs.
    Returns a unique trace group identifier that can be used to retrieve
    the grouped traces and their associated workflows.
    """
    start_time = time()

    try:
        traces_id = body.trace_ids
        logger.info(f"Creating trace group for {len(traces_id)} trace_ids")

        if not name:
            name = create_trace_group_name(traces_id)

        # Check if trace group with same name already exists
        trace_group = await client.trace_groups.fetch(
            service_name=tenant_id, 
            names=[name]
        )
        if not trace_group:
            # Call runtime client to create trace group along with group metrics
            trace_group = await client.trace_groups.create(
                service_name=tenant_id, # We don't have any other explicit service name here
                name = name,
                trace_ids=traces_id
            )
        else:
            trace_group = trace_group[0]  # Get the existing trace group
            fetched_traces_id = trace_group.traces_ids
            if set(fetched_traces_id) != set(traces_id):
                # If the existing trace group has different traces, we can choose to update it or raise an error
                error_msg = f"Trace group with name '{name}' already exists with different traces."
                logger.error(error_msg)
                raise HTTPException(status_code=400, detail=error_msg)

        #validate if those traces already has tasks, if not this will create them
        await client.traces.process(trace_ids=traces_id)

        # Log successful processing
        await UsageTracker.log_action(
            username=current_user.username,
            action="create_trace_group",
            element=trace_group.id,
            response_time_ms=(time() - start_time) * 1000,
            status_code=201,
            success=True,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            metadata={
                "trace_count": len(body.trace_ids),
                "trace_group_id": trace_group.id,
                "trace_group_name": name,
                "tenant_id": tenant_id
            }
        )

        return TraceGroupResponse(trace_group_id=trace_group.id)

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error creating trace group: {error_msg}")
        traceback.print_exc()

        await UsageTracker.log_action(
            username=current_user.username,
            action="create_trace_group",
            element="trace_group",
            response_time_ms=(time() - start_time) * 1000,
            status_code=500,
            success=False,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            error_message=error_msg,
            metadata={"tenant_id": tenant_id}
        )

        raise HTTPException(status_code=500, detail=error_msg) from e


