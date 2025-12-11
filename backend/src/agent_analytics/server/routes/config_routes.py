import logging
import os

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from agent_analytics.server.logger import logger
from agent_analytics.server.routes import get_tenant_id, runtime_client

JAEGER_EMBED_PATH = os.environ.get('JAEGER_EMBED_PATH', None) # "/jaeger")

# Create router without tenant_id dependency
config_router = APIRouter(
    tags=["Configuration"]
)

@config_router.get("/config/jaeger-url")
async def get_jaeger_url(request: Request,
                         tenant_id: str = Depends(get_tenant_id)
            ):
    return { "url": JAEGER_EMBED_PATH }

@config_router.get("/config/extensions-enabled")
async def get_extensions_enabled(request: Request,
                                 tenant_id: str = Depends(get_tenant_id)
            ):
    return { "state": runtime_client.ENABLE_EXTENSIONS }




