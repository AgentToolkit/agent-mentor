import asyncio
import sys
import traceback
from datetime import datetime
from time import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from agent_analytics.server.auth import SAMLUser, get_current_user
from agent_analytics.server.db.operations import UsageTracker
from agent_analytics.server.logger import logger
from agent_analytics.server.routes import get_tenant_id, runtime_client

# Create router with tenant_id dependency
analytics_router = APIRouter(
    tags=["Analytics"],
    dependencies=[Depends(get_tenant_id)]
)

# Store metric status in memory (TODO: Need to replace with a more robust mechanism)
metric_status = {}

class AnalyticsCommand(BaseModel):
    command: str

async def launch_eval_metric(trace_id: str, metric_id: str, tenant_id: str):
    try:
        # Update status to RUNNING
        metric_status[f"{trace_id}:{metric_id}:{tenant_id}"] = {
            "status": runtime_client.STATUS_RUNNING,
            "results": None
        }

        # Launch eval metrics with tenant_id
        results = await runtime_client.launch_eval_metrics(trace_id, tenant_id=tenant_id)

        if results != None:
            metrics = await runtime_client.get_trace_metrics(trace_id, tenant_id=tenant_id)
            eval_metrics = []
            for metric in metrics:
                if runtime_client.EVAL_METRICS == metric.plugin_metadata_id:
                    eval_metrics.append(metric.model_dump())

            if len(eval_metrics) > 0:
                result = {
                    "status": runtime_client.STATUS_READY,
                    "results": eval_metrics
                }
                metric_status[f"{trace_id}:{metric_id}:{tenant_id}"] = result
            else:
                metric_status[f"{trace_id}:{metric_id}:{tenant_id}"] = {
                    "status": "ERROR",
                    "error": "Couldn't pull metrics for tasks"
                }
        else:
            metric_status[f"{trace_id}:{metric_id}:{tenant_id}"] = {
                "status": "ERROR",
                "error": "No metrics computed for any tasks"
            }

    except Exception as e:
        # Handle any errors by updating the status
        metric_status[f"{trace_id}:{metric_id}:{tenant_id}"] = {
            "status": "ERROR",
            "error": str(e)
        }

@analytics_router.get("/traces/{trace_id}/analytics/{metric_id}")
async def get_metric_status(
    request: Request,
    trace_id: str,
    metric_id: str,
    current_user: SAMLUser = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    start_time = time()
    try:
        # Use tenant_id in the key
        key = f"{trace_id}:{metric_id}:{tenant_id}"
        if key not in metric_status:
            # Include tenant_id when getting metrics
            metrics = await runtime_client.get_trace_metrics(trace_id, tenant_id=tenant_id)
            eval_metrics = []
            for metric in metrics:
                if runtime_client.EVAL_METRICS == metric.plugin_metadata_id:
                    eval_metrics.append(metric.model_dump())

            if len(eval_metrics) > 0:
                result = {
                    "status": runtime_client.STATUS_READY,
                    "results": eval_metrics
                }
                metric_status[key] = result
            else:
                result = {"status": runtime_client.STATUS_NOT_STARTED}
        else:
            # Result is either ready with the metrics or still running
            result = metric_status[key]

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_metric_details",
            element=trace_id,
            response_time_ms=(time() - start_time) * 1000,
            status_code=200,
            success=True,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            payload_size=sys.getsizeof(result),
            metadata={
                "trace_id": trace_id,
                "metric_id": metric_id,
                "tenant_id": tenant_id
            }
        )

        return result
    except Exception as e:
        await runtime_client.cleanup(tenant_id)

        error_msg = str(e)
        logger.error(f"Error get_metric_status: {error_msg}")
        traceback.print_exc()

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_metric_details",
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

@analytics_router.post("/traces/{trace_id}/analytics/{metric_id}")
async def run_metrics(
    request: Request,
    trace_id: str,
    metric_id: str,
    command: AnalyticsCommand,
    current_user: SAMLUser = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    start_time = time()
    try:
        result = None
        if command.command == "launch":
            # Use tenant_id in the key
            key = f"{trace_id}:{metric_id}:{tenant_id}"
            if key in metric_status and metric_status[key]['status'] != runtime_client.STATUS_FAILED:
                result = metric_status[key]
            else:
                # Get metrics with tenant_id
                metrics = await runtime_client.get_trace_metrics(trace_id, tenant_id=tenant_id)
                eval_metrics = []
                for metric in metrics:
                    if runtime_client.EVAL_METRICS == metric.plugin_metadata_id:
                        eval_metrics.append(metric.model_dump())

                if len(eval_metrics) > 0:
                    result = {
                        "status": runtime_client.STATUS_READY,
                        "results": eval_metrics
                    }
                else:
                    # Launch with tenant_id
                    asyncio.ensure_future(launch_eval_metric(trace_id, metric_id, tenant_id))

                    # Update status immediately
                    result = {
                        "status": runtime_client.STATUS_RUNNING,
                        "results": None
                    }
                metric_status[key] = result
        else:
            # Handle unknown commands
            raise HTTPException(
                status_code=400,
                detail=f"Unknown command: {command.command}"
            )

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_metric_details",
            element=trace_id,
            response_time_ms=(time() - start_time) * 1000,
            status_code=200,
            success=True,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            payload_size=sys.getsizeof(result),
            metadata={
                "trace_id": trace_id,
                "metric_id": metric_id,
                "tenant_id": tenant_id
            }
        )

        return result
    except Exception as e:
        # Use tenant_id in the key
        key = f"{trace_id}:{metric_id}:{tenant_id}"
        result = {
            "status": runtime_client.STATUS_FAILED,
            "results": None
        }
        metric_status[key] = result

        await runtime_client.cleanup(tenant_id)

        error_msg = str(e)
        logger.error(f"Error run_metrics: {error_msg}")
        traceback.print_exc()

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_metric_details",
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


@analytics_router.get("/metrics/traces/summary")
async def get_trace_summary_metrics(
    request: Request,
    service_name: str,
    start_date: str,
    end_date: str,
    agent_ids_str: str | None = Query(None, alias="agent_ids"),
    include_overall: bool = True,  # ADD this parameter
    current_user: SAMLUser = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    start_time = time()
    agent_ids = None
    if agent_ids_str:
        agent_ids = [id.strip() for id in agent_ids_str.split(',') if id.strip()]

    logger.debug(f"Raw agent_ids_str: '{agent_ids_str}'")
    logger.debug(f"Parsed agent_ids: {agent_ids}")
    try:
        # Parse dates
        try:
            start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))


        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")

        # Call the new combined method
        result = await runtime_client.get_combined_agent_summary_metrics_traces_optimized(
            service_name=service_name,
            tenant_id=tenant_id,
            agent_ids_filter=agent_ids,
            start_time=start_datetime,
            end_time=end_datetime,
            include_overall_metric=include_overall
        )

        # Convert to list of dicts for JSON response (now returns multiple metrics)
        summary_data = [metric.model_dump(mode='json') for metric in result]

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_trace_summary_metrics",
            element=service_name,
            response_time_ms=(time() - start_time) * 1000,
            status_code=200,
            success=True,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            payload_size=sys.getsizeof(summary_data),
            metadata={
                "service_name": service_name,
                "start_date": start_date,
                "end_date": end_date,
                "agent_ids": agent_ids,
                "metric_count": len(summary_data),
                "tenant_id": tenant_id
            }
        )

        return summary_data

    except HTTPException:
        raise
    except Exception as e:
        await runtime_client.cleanup(tenant_id)

        error_msg = str(e)
        logger.error(f"Error get_trace_summary_metrics: {error_msg}")
        traceback.print_exc()

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_trace_summary_metrics",
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

@analytics_router.get("/metrics/traces/detailed")
async def get_detailed_trace_metrics(
    request: Request,
    service_name: str,
    start_date: str,
    end_date: str,
    start_index: int,
    end_index: int,
    agent_ids_str: str | None = Query(None, alias="agent_ids"),
    current_user: SAMLUser = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    start_time = time()
    agent_ids = None
    if agent_ids_str:
        agent_ids = [id.strip() for id in agent_ids_str.split(',') if id.strip()]
    logger.debug(f"Raw agent_ids_str: '{agent_ids_str}'")
    logger.debug(f"Parsed agent_ids: {agent_ids}")
    try:
        # Validate pagination parameters for 0-based indexing
        if start_index < 0 or end_index < 0:
            raise HTTPException(status_code=400, detail="Index parameters must be >= 0")
        if start_index >= end_index:
            raise HTTPException(status_code=400, detail="start_index must be < end_index (exclusive end)")

        # Optional: Add reasonable upper limit to prevent abuse
        max_page_size = 100
        if (end_index - start_index) > max_page_size:
            raise HTTPException(status_code=400, detail=f"Page size cannot exceed {max_page_size}")

        # Parse dates
        try:
            start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")

        # Call platform client method
        result = await runtime_client.get_detailed_metrics_traces(
            tenant_id=tenant_id,
            service_name=service_name,
            agent_ids_filter=agent_ids,
            start_time=start_datetime,
            end_time=end_datetime,
            pagination=(start_index, end_index)
        )

        # Convert to list of dicts for JSON response
        detailed_data = [metric.model_dump(mode='json') for metric in result]

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_detailed_trace_metrics",
            element=service_name,
            response_time_ms=(time() - start_time) * 1000,
            status_code=200,
            success=True,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            payload_size=sys.getsizeof(detailed_data),
            metadata={
                "service_name": service_name,
                "start_date": start_date,
                "end_date": end_date,
                "start_index": start_index,
                "end_index": end_index,
                "agent_ids": agent_ids,
                "metric_count": len(detailed_data),
                "tenant_id": tenant_id
            }
        )

        return detailed_data

    except HTTPException:
        raise
    except Exception as e:
        await runtime_client.cleanup(tenant_id)

        error_msg = str(e)
        logger.error(f"Error get_detailed_trace_metrics: {error_msg}")
        traceback.print_exc()

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_detailed_trace_metrics",
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


