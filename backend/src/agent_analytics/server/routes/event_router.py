import sys
import traceback
from time import time

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request

from agent_analytics.core.plugin.base_plugin import ExecutionResult, ExecutionStatus

# Import the Pydantic models
from agent_analytics.runtime.api.events import (
    EventNotificationRequest,
    EventResponse,
)
from agent_analytics.server.auth import SAMLUser, get_current_user
from agent_analytics.server.db.operations import UsageTracker
from agent_analytics.server.logger import logger
from agent_analytics.server.routes import get_tenant_id, runtime_client

# Create router with tenant_id dependency
event_router = APIRouter(
    prefix="/api/events",
    tags=["Events"],
    dependencies=[Depends(get_tenant_id)]
)

# Add these methods to the RuntimeClient class or as module-level functions

def _encode_event_id(analytics_id: str, trace_id: str = None, trace_group_id: str = None) -> str:
    """
    Encode analytics_id and trace/group id into event_id.
    Format: {analytics_id}:{trace_id or trace_group_id}
    """
    identifier = trace_id if trace_id else trace_group_id
    if not identifier:
        raise ValueError("Either trace_id or trace_group_id must be provided")
    return f"{analytics_id}:{identifier}"

def _decode_event_id(event_id: str) -> tuple[str, str]:
    """
    Decode event_id back to analytics_id and trace/group id.
    Returns: (analytics_id, trace_or_group_id)
    """
    parts = event_id.split(":", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid event_id format: {event_id}")
    return parts[0], parts[1]

async def process_event_in_background(
    event_data: EventNotificationRequest,
    event_id: str,
    analytics_id: str,
    username: str,
    tenant_id: str,
    ip_address: str,
    user_agent: str
):
    """
    Background task to process the event asynchronously.
    This runs after the HTTP response has been sent to the client.
    """
    start_time = time()
    try:
        logger.info(f"Processing event {event_id} in background: {event_data.event_type} for {event_data.data_item_type}")

        # Process the event based on event_type and data_item_type
        if event_data.event_type == "data_available" and event_data.data_item_type == "span":
            # Call the platform client method to handle span data available event
            result = await runtime_client.process_event(
                trace_id=event_data.content.trace_id,
                trace_group_id=event_data.content.trace_group_id,
                analytics_id = analytics_id,
                creating_plugin_id=event_data.content.creating_plugin_id,
                metadata=event_data.content.metadata,
                timestamp=event_data.content.timestamp,
                tenant_id=tenant_id
            )

            logger.info(f"Event {event_id} processed successfully")

            # Log successful processing
            await UsageTracker.log_action(
                username=username,
                action="process_event_background",
                element=event_data.event_type,
                response_time_ms=(time() - start_time) * 1000,
                status_code=200,
                success=True,
                ip_address=ip_address,
                user_agent=user_agent,
                payload_size=sys.getsizeof(result) if result else 0,
                metadata={
                    "event_type": event_data.event_type,
                    "data_item_type": event_data.data_item_type,
                    "trace_id": event_data.content.trace_id,
                    "event_id": event_id,
                    "tenant_id": tenant_id
                }
            )
        else:
            logger.warning(f"Unsupported event type in background task: {event_data.event_type}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error processing event {event_id} in background: {error_msg}")
        traceback.print_exc()

        await runtime_client.cleanup(tenant_id)

        # Log failed processing
        await UsageTracker.log_action(
            username=username,
            action="process_event_background",
            element=event_data.event_type,
            response_time_ms=(time() - start_time) * 1000,
            status_code=500,
            success=False,
            ip_address=ip_address,
            user_agent=user_agent,
            error_message=error_msg,
            metadata={
                "event_id": event_id,
                "tenant_id": tenant_id
            }
        )


@event_router.post("")
async def on_event(
    request: Request,
    background_tasks: BackgroundTasks,
    event_data: EventNotificationRequest = Body(...),
    current_user: SAMLUser = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    Process an event notification.
    Main entry point for event notification processing.
    Returns immediately while processing happens in the background.
    """
    start_time = time()

    try:
        # Log the incoming event
        logger.info(f"Received event: {event_data.event_type} for {event_data.data_item_type}")

        # Validate event type
        if event_data.event_type == "data_available" and event_data.data_item_type == "span":
            analytics_id=runtime_client.TASK_ANALYTICS
            trace_id=event_data.content.trace_id
            # Create event_id that encodes analytics_id and trace_id
            event_id = _encode_event_id(
                analytics_id=analytics_id,
                trace_id=trace_id
            )
            logger.info(f"Received event: {event_data.event_type} for {event_data.data_item_type}, assigned id: {event_id}")
            # Schedule the background task - this is the key difference!
            # The task will run AFTER the response is returned to the client
            background_tasks.add_task(
                process_event_in_background,
                event_data=event_data,
                event_id=str(event_id),
                analytics_id = analytics_id,
                username=current_user.username,
                tenant_id=tenant_id,
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent", "")
            )
        else:
            # Handle unsupported event types
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported event type: {event_data.event_type}"
            )

        # Log successful acceptance (not processing completion)
        await UsageTracker.log_action(
            username=current_user.username,
            action="on_event_accepted",
            element=event_data.event_type,
            response_time_ms=(time() - start_time) * 1000,
            status_code=200,
            success=True,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            payload_size=sys.getsizeof(event_data.model_dump()),
            metadata={
                "event_type": event_data.event_type,
                "data_item_type": event_data.data_item_type,
                "trace_id": event_data.content.trace_id,
                "event_id": str(event_id),
                "tenant_id": tenant_id,
                "processing": "background"
            }
        )

        # Return success response immediately - background task continues running
        return EventResponse(
            success=True,
            event_id=event_id,
            message="Event accepted for processing"
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error accepting event: {error_msg}")
        traceback.print_exc()

        await UsageTracker.log_action(
            username=current_user.username,
            action="on_event_accepted",
            element=event_data.event_type if event_data else "unknown",
            response_time_ms=(time() - start_time) * 1000,
            status_code=500,
            success=False,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            error_message=error_msg,
            metadata={"tenant_id": tenant_id}
        )

        raise HTTPException(status_code=500, detail=error_msg)

@event_router.get("/{event_id}/status")
async def get_event_status(
    request: Request,
    event_id: str,
    current_user: SAMLUser = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    Get the processing status of an event.
    Returns the execution result if available.
    """
    start_time = time()

    try:
        # Decode event_id to get analytics_id and trace_id
        analytics_id, trace_or_group_id = _decode_event_id(event_id)

        # Get execution results
        tenant_components, _ = await runtime_client.ensure_initialized(tenant_id)
        results: dict[str, list[ExecutionResult]] = await tenant_components.executor.execution_results_data_manager.get_results_by_trace_or_group_id(
            analytics_id=analytics_id,
            trace_or_group_ids=[trace_or_group_id]
        )

        # Determine status
        if trace_or_group_id not in results or not results[trace_or_group_id]:
            status = "pending"
            execution_result = None
        else:
            # Get the most recent result from the list
            result_list: list[ExecutionResult] = results[trace_or_group_id]
            latest_result: ExecutionResult = max(result_list, key=lambda r: r.start_time)

            if latest_result.status == ExecutionStatus.SUCCESS:
                status = "completed"
            elif latest_result.status == ExecutionStatus.FAILURE:
                status = "failed"
            elif latest_result.status == ExecutionStatus.IN_PROGRESS:
                status = "processing"
            else:
                status = latest_result.status.value

            execution_result = {
                "status": latest_result.status.value,
                "start_time": latest_result.start_time.isoformat() if latest_result.start_time else None,
                "end_time": latest_result.end_time.isoformat() if latest_result.end_time else None,
                "execution_time": latest_result.execution_time,
                "error": latest_result.error.model_dump() if latest_result.error else None
            }

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_event_status",
            element=event_id,
            response_time_ms=(time() - start_time) * 1000,
            status_code=200,
            success=True,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            metadata={
                "event_id": event_id,
                "status": status,
                "tenant_id": tenant_id
            }
        )

        return {
            "event_id": event_id,
            "status": status,
            "execution_result": execution_result
        }

    except ValueError as e:
        # Invalid event_id format
        raise HTTPException(status_code=400, detail=f"Invalid event_id format: {str(e)}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error getting event status: {error_msg}")
        traceback.print_exc()

        await UsageTracker.log_action(
            username=current_user.username,
            action="get_event_status",
            element=event_id,
            response_time_ms=(time() - start_time) * 1000,
            status_code=500,
            success=False,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            error_message=error_msg,
            metadata={"tenant_id": tenant_id}
        )

        raise HTTPException(status_code=500, detail=error_msg)
