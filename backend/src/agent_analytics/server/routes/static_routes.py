import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse

from agent_analytics.server.config import config

# Create router for static routes - no tenant_id needed here
static_router = APIRouter(tags=["Static"])

# Static Routes
@static_router.get("/")
async def read_root():
    html_file_path = Path(config.PROJECT_ROOT).joinpath("src/agent_analytics/client/build/index.html")
    with open(html_file_path) as f:
        html_content = f.read()
    test_env = os.getenv("TEST", "false").lower()
    env_script = f"""<script>
    window.ENV = {{
        TEST: "{test_env}"
    }};
</script>
"""
    html_content_modified = html_content.replace("</head>", f"{env_script}</head>")
    return HTMLResponse(content=html_content_modified)

@static_router.get("/manifest.json")
async def manifest():
    return FileResponse(Path(config.PROJECT_ROOT).joinpath("src/agent_analytics/client/build/manifest.json"))

@static_router.get("/favicon.ico")
async def favicon():
    return FileResponse(Path(config.PROJECT_ROOT).joinpath("src/agent_analytics/client/build/favicon.ico"))

@static_router.get("/logo192.png")
async def logo():
    return FileResponse(Path(config.PROJECT_ROOT).joinpath("src/agent_analytics/client/build/logo192.png"))

@static_router.get("/logo512.png")
async def logo_large():
    return FileResponse(Path(config.PROJECT_ROOT).joinpath("src/agent_analytics/client/build/logo512.png"))

@static_router.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring and integration verification.
    Returns a simple status indicating the service is running.
    """
    return {
        "status": "healthy",
        "service": "agentops",
        "version": "1.0.0"
    }

@static_router.get("/ui/v1/workflows")
async def workflows_page():
    """Serve the same index.html for the workflows page - React Router will handle the routing"""
    html_file_path = Path(config.PROJECT_ROOT).joinpath("src/agent_analytics/client/build/index.html")
    with open(html_file_path) as f:
        html_content = f.read()
    test_env = os.getenv("TEST", "false").lower()
    env_script = f"""<script>
    window.ENV = {{
        TEST: "{test_env}"
    }};
</script>
"""
    html_content_modified = html_content.replace("</head>", f"{env_script}</head>")
    return HTMLResponse(content=html_content_modified)

@static_router.get("/admin/tenants-dashboard")
async def tenants_dashboard_page():
    """Serve the same index.html for the tenants dashboard page - React Router will handle the routing"""
    html_file_path = Path(config.PROJECT_ROOT).joinpath("src/agent_analytics/client/build/index.html")
    with open(html_file_path) as f:
        html_content = f.read()
    test_env = os.getenv("TEST", "false").lower()
    env_script = f"""<script>
    window.ENV = {{
        TEST: "{test_env}"
    }};
</script>
"""
    html_content_modified = html_content.replace("</head>", f"{env_script}</head>")
    return HTMLResponse(content=html_content_modified)


