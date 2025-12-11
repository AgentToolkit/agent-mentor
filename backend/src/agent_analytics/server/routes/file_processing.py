import os
import sys
import traceback
from time import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile

from agent_analytics.server.auth import SAMLUser, get_current_user
from agent_analytics.server.db.operations import UsageTracker
from agent_analytics.server.logger import logger
from agent_analytics.server.routes import get_tenant_id, runtime_client

# Create router with tenant_id dependency
file_router = APIRouter(
    tags=["File Processing"],
    dependencies=[Depends(get_tenant_id)]
)

# File Processing Route
@file_router.post("/process")
async def process_log_file(
    request: Request,
    file: UploadFile,
    return_source_traces_only: bool = Query(False, description="Return only the original traces from the uploaded file"),
    current_user: SAMLUser = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    start_time = time()
    try:
        if not file or not file.filename:
            raise HTTPException(
                status_code=400,
                detail="Invalid file upload - filename is required"
            )
        _, extension = os.path.splitext(file.filename)

        if extension not in ['.log', '.json']:
            raise HTTPException(status_code=400, detail="Only .log and .json files are allowed")

        contents = await file.read()
        file_content = contents.decode()
        if len(file_content) > 2e8:
            raise Exception("Uploaded file is larger than 200M. Try creating a smaller trace file.")

        # Pass tenant_id to platform client
        result = await runtime_client.process_file(file_content, tenant_id=tenant_id, return_source_traces_only=return_source_traces_only)

        await UsageTracker.log_action(
            username=current_user.username,
            action="process",
            element=file.filename,
            response_time_ms=(time() - start_time) * 1000,
            status_code=200,
            success=True,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            payload_size=sys.getsizeof(result),
            metadata={
                "file_type": file.filename.split('.')[-1],
                "file_size": len(contents),
                "tenant_id": tenant_id
            }
        )

        return result

    except Exception as e:
        await runtime_client.cleanup(tenant_id)

        error_msg = str(e)
        logger.error(f"Error process_log_file file: {error_msg}")
        traceback.print_exc()

        await UsageTracker.log_action(
            username=current_user.username,
            action="process",
            element=file.filename if file else "unknown",
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
        return { "error": error_msg }
