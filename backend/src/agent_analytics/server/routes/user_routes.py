from fastapi import APIRouter, Depends
from agent_analytics.server.auth import get_current_user, SAMLUser
from agent_analytics.server.routes import get_tenant_id

# Create router with tenant_id dependency
user_router = APIRouter(
    prefix="/users",
    tags=["Users"],
    dependencies=[Depends(get_tenant_id)]
)

# User Routes
@user_router.get("/me", response_model=SAMLUser)
async def read_users_me(
    current_user: SAMLUser = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    # Now has access to tenant_id
    return current_user