import logging
import os
import re
from typing import Annotated, Any, Dict, Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from agent_analytics.sdk.client import AgentOpsClient
from agent_analytics.server.auth import DEPLOYMENT_PLATFORM
from agent_analytics.server.instana_client import InstanaClient
from agent_analytics.server.runtime_client import RuntimeClient

_logger = logging.getLogger(__name__)

### Auth related init
auth_scheme = HTTPBearer(auto_error=False)
BYPASS_AUTH = os.getenv("BYPASS_AUTH", "false").lower() == "true"
API_KEY_AUTH_ENABLED = os.getenv("API_KEY_AUTH_ENABLED", "false").lower() == "true"
INBOUND_API_KEY = os.getenv("INBOUND_API_KEY", "")
DEFAULT_TENANT_ID = os.getenv('DEFAULT_TENANT_ID', 'default')

# Create main router
router = APIRouter()

# Initialize clients
instana_client = InstanaClient(
    base_url=os.getenv('INSTANA_URL', ''),
    api_token=os.getenv('API_TOKEN', '')
)

runtime_client = RuntimeClient()

# AgentOps clients - one per tenant, initialized on demand
agentops_clients: dict[str, AgentOpsClient] = {}

def get_tenant_from_crn(crn: str) -> str | None:
    regex = r"^(crn):(v\d+):(\w+(?:-\w+)*):(\w+(?:-\w+)*):(\w+-\w+(?:-\w+)*):(\w+(?:-\w+)*):(\w+\/[\w-]+):(\w+-\w+-\w+-\w+-\w+)::$"
    match = re.match(regex, crn)
    if match:
        account_id = match.group(7).split('/')[1]
        resource_id = match.group(8)
        return f"{account_id}_{resource_id}"
    else:
        print("CRN does not match the expected pattern.")
        return None

async def get_user_info_for_token(token: Annotated[HTTPAuthorizationCredentials, Depends(auth_scheme)]):

    # If we're in bypass mode, return default user info
    if BYPASS_AUTH:
        return {
            'user_id': 'bypass_user',
            'tenant_id': DEFAULT_TENANT_ID,
            'username': 'bypass_user',
        }

    # If no token provided and not in bypass mode, return None
    if token is None or token.credentials is None:
        return None

    token_str = token.credentials
    try:
        payload = jwt.decode(token_str, key=None, options={"verify_signature": False, "verify_exp": False, "verify_aud": False})
        if payload is None:
            return None
            # raise credentials_exception

        user_id = None
        tenant_id = None
        # username: str = payload.get("preferred_username") or payload.get("username", "defaultLocalUser@default.com")
        # if(DEPLOYMENT_PLATFORM.lower() == 'saas' or DEPLOYMENT_PLATFORM.lower() == 'local' or DEPLOYMENT_PLATFORM.lower() == 'laptop-lite'):
        #     user_id = payload.get("woUserId")
        #     tenant_id = payload.get("woTenantId")
        # elif DEPLOYMENT_PLATFORM == 'ibmcloud' or DEPLOYMENT_PLATFORM == 'on_prem':
        #     user_id = payload.get("sub")
        #     crn = payload.get("crn")
        #     tenant_id = get_tenant_from_crn(crn)
        # else:
        #     raise platform_unkown_exception
        user_id = payload.get("woUserId") or payload.get("sub")
        tenant_id = payload.get("woTenantId")
        if payload.get('crn'):
            tenant_id = get_tenant_from_crn(payload['crn'])
        elif payload.get('aud'):
            for aud_element in payload.get('aud'):
                if aud_element[:3] == "crn":
                    tenant_id = get_tenant_from_crn(aud_element)

        if user_id is None or tenant_id is None:
            return None
            # raise credentials_exception

        username = (
            payload.get("preferred_username")
            or payload.get("name")
            or payload.get("username") or None
        )

    except Exception as e:
        _logger.error(f"JWT Error: {e}")
        return None
        # raise credentials_exception

    return {
        'user_id': user_id,
        'tenant_id': tenant_id,
        'username': username,
    }

# Tenant ID dependency function
async def get_tenant_id(
    user_info_dict: Annotated[dict[str, Any], Depends(get_user_info_for_token)],
    x_tenant_id: str = Header(None)
) -> str:
    if (API_KEY_AUTH_ENABLED or BYPASS_AUTH) and x_tenant_id and x_tenant_id != 'null':
        # print(f">>>get_tenant_id: BYPASS_AUTH={BYPASS_AUTH} x_tenant_id={x_tenant_id}")
        return x_tenant_id
    if user_info_dict and user_info_dict['tenant_id']:
        # print(f">>>get_tenant_id: user_info_dict={user_info_dict} tenant_id={user_info_dict['tenant_id'] if user_info_dict else ''}")
        return user_info_dict['tenant_id']
    else:
        # print(f">>>get_tenant_id: DEFAULT_TENANT_ID={DEFAULT_TENANT_ID} x_tenant_id={x_tenant_id}")
        # Return default tenant if none provided
        return DEFAULT_TENANT_ID if not x_tenant_id or x_tenant_id == 'null' else x_tenant_id


async def get_agentops_client(tenant_id: str = Depends(get_tenant_id)) -> AgentOpsClient:
    """Dependency that provides a tenant-specific AgentOpsClient instance."""
    if tenant_id not in agentops_clients:
        _logger.info(f"Creating AgentOpsClient for tenant: {tenant_id}")
        agentops_clients[tenant_id] = await AgentOpsClient.create(tenant_id=tenant_id)
        _logger.info(f"AgentOpsClient created successfully for tenant: {tenant_id}")
    return agentops_clients[tenant_id]


# Initialization and teardown functions
async def initialize():
    await runtime_client.initialize()
    # AgentOps clients are now created on-demand per tenant


async def teardown():
    await runtime_client.cleanup_all()
    # Cleanup all tenant-specific AgentOps clients
    if agentops_clients:
        _logger.info(f"Cleaning up {len(agentops_clients)} AgentOps client(s)")
        agentops_clients.clear()

# Import and include sub-routers
from agent_analytics.server.routes.admin_routes import admin_router
from agent_analytics.server.routes.analytics_routes import analytics_router
from agent_analytics.server.routes.api_routes import api_router
from agent_analytics.server.routes.config_routes import config_router
from agent_analytics.server.routes.event_router import event_router
from agent_analytics.server.routes.file_processing import file_router
from agent_analytics.server.routes.instana_routes import instana_router
from agent_analytics.server.routes.jaeger_routes import jaeger_router
from agent_analytics.server.routes.sdk_routes import sdk_router
from agent_analytics.server.routes.static_routes import static_router
from agent_analytics.server.routes.storage_routes import storage_router
from agent_analytics.server.routes.user_routes import user_router

# Include all routers
router.include_router(static_router)
router.include_router(user_router)
router.include_router(instana_router)
router.include_router(file_router)
router.include_router(storage_router)
router.include_router(analytics_router)
router.include_router(admin_router)
router.include_router(config_router)
router.include_router(jaeger_router)
router.include_router(api_router)
router.include_router(sdk_router)
router.include_router(event_router)

