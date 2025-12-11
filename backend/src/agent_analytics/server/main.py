import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

load_dotenv()
print(f"PROJECT_ROOT from env: {os.getenv('PROJECT_ROOT', 'NOT SET')}")

def get_version():
    """Extract version from pyproject.toml"""
    try:
        project_root = Path(os.getenv('PROJECT_ROOT', os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        pyproject_path = project_root / 'pyproject.toml'
        if pyproject_path.exists():
            content = pyproject_path.read_text()
            match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
            if match:
                return match.group(1)
    except Exception:
        pass
    return "unknown"

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles

from agent_analytics.server.auth import (
    auth_auto_login,
    auth_login_get,
    auth_login_post,
    auth_logout,
    refresh_metadata,
    saml_acs,
    saml_auth,
    saml_login,
    saml_logout,
    should_bypass_auth,
)
from agent_analytics.server.config import config  # noqa: E402, I001
from agent_analytics.server.db.database import init_db  # noqa: E402
from agent_analytics.server.routes import initialize, router, teardown  # noqa: E402
from agent_analytics.runtime.api.config import Settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await initialize()
    if Settings().LOG_USER:
        await init_db()

    try:
        yield  # Server is running
    finally:
        # Shutdown
        await teardown()

def custom_openapi(include_admin: bool = False):
    """Generate OpenAPI schema with optional admin routes based on authentication"""
    # This call generates the base schema, including schemas from your Pydantic models
    openapi_schema = get_openapi(
        title="Agent Analytics",
        version="1.0.0",
        description="Agent Analytics",
        routes=app.routes,
    )

    # 1. Define the tags you want to hide
    hidden_tags = ["Static", "Users", "Instana", "Configuration", "default"]

    # Add "Admin" to hidden tags if user doesn't have admin access
    if not include_admin:
        hidden_tags.append("Admin")

    # 2. Filter out the paths that have any of the hidden tags
    # openapi_schema["paths"] = {
    #     path: path_item
    #     for path, path_item in openapi_schema["paths"].items()
    #     if not any(
    #         tag in hidden_tags
    #         for method in path_item.values()
    #         for tag in method.get("tags", [])
    #     )
    # }
    # 2. A more robust way to filter paths and methods
    new_paths = {}
    for path, path_item in openapi_schema["paths"].items():
        # Create a new dictionary for the methods we want to keep
        new_path_item = {}
        for method, method_data in path_item.items():
            tags = method_data.get("tags", [])
            # Condition to KEEP a method:
            # - It MUST have tags (tags list is not empty).
            # - AND none of its tags can be in the hidden_tags list.
            if tags and not any(t in hidden_tags for t in tags):
                new_path_item[method] = method_data

        # Only add the path to the new schema if it still has methods left
        if new_path_item:
            new_paths[path] = new_path_item

    openapi_schema["paths"] = new_paths


    # --- THE FIX - PART 1: Merge schemas instead of replacing them ---
    # Ensure the components and schemas keys exist before trying to update them
    openapi_schema.setdefault("components", {}).setdefault("schemas", {})

    # Your manually defined schemas
    manual_schemas = {
        "HTTPValidationError": {
            "title": "HTTPValidationError",
            "type": "object",
            "properties": {
                "detail": {
                    "title": "Detail", "type": "array", "items": {"$ref": "#/components/schemas/ValidationError"}
                }
            },
        },
        "ValidationError": {
            "title": "ValidationError",
            "required": ["loc", "msg", "type"],
            "type": "object",
            "properties": {
                "loc": {
                    "title": "Location", "type": "array", "items": {"anyOf": [{"type": "string"}, {"type": "integer"}]}
                },
                "msg": {"title": "Message", "type": "string"},
                "type": {"title": "Error Type", "type": "string"},
            },
        },
        "Body_process_log_file_process_post": {
            "title": "Body_process_log_file_process_post",
            "required": ["file"],
            "type": "object",
            "properties": {"file": {"title": "File", "type": "string", "format": "binary"}},
        },
    }

    # Use update() to add your manual schemas to the auto-generated ones
    openapi_schema["components"]["schemas"].update(manual_schemas)


    # --- THE FIX - PART 2: Clean up '-Input' suffixes from names and references ---
    # 1. Fix references in paths
    for path_data in openapi_schema.get('paths', {}).values():
        for method_data in path_data.values():
            if 'requestBody' in method_data:
                content = method_data['requestBody'].get('content', {})
                for media_type in content.values():
                    if '$ref' in media_type.get('schema', {}):
                        media_type['schema']['$ref'] = media_type['schema']['$ref'].replace('-Input', '')

    # 2. Fix the names in the schema definitions themselves
    if 'schemas' in openapi_schema.get('components', {}):
        schemas = openapi_schema['components']['schemas']
        for schema_name in list(schemas.keys()):
            if schema_name.endswith('-Input'):
                new_name = schema_name.replace('-Input', '')
                schemas[new_name] = schemas.pop(schema_name)


    # Add security schemes
    def should_bypass_auth():
        # Replace with your actual logic
        return False

    if not should_bypass_auth():
        openapi_schema["components"]["securitySchemes"] = {
            "SAMLAuth": {
                "type": "openIdConnect",
                "openIdConnectUrl": "/auth/login",
                "description": "SAML Authentication via SSO",
            }
        }
        openapi_schema["security"] = [{"SAMLAuth": []}]

    return openapi_schema


app = FastAPI(lifespan=lifespan, debug=True, docs_url=None, redoc_url=None, openapi_url=None)

# Add CORS middleware
def generate_dev_origins():
    """Generate allowed origins for development ports """
    origins = [
        "https://localhost",
        "http://localhost"
    ]

    # Add range of development ports (3000-3010)
    for port in range(3000, 3011):
        origins.extend([
            f"https://localhost:{port}",
            f"http://localhost:{port}"
        ])

    return origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=generate_dev_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom OpenAPI endpoint that checks for admin API key
@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_endpoint(admin_key: str | None = None):
    """Dynamic OpenAPI schema that includes admin routes only for admin users"""
    admin_api_key = os.getenv("ADMIN_API_KEY", "")
    include_admin = bool(admin_api_key and admin_key == admin_api_key)
    return custom_openapi(include_admin=include_admin)

# Custom docs endpoints
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html(admin_key: str | None = None):
    """Swagger UI that dynamically includes admin routes based on API key"""
    # Validate admin key if provided
    admin_api_key = os.getenv("ADMIN_API_KEY", "")
    if admin_key and admin_api_key and admin_key == admin_api_key:
        # Pass admin key to openapi.json via query parameter
        openapi_url = f"/openapi.json?admin_key={admin_key}"
    else:
        openapi_url = "/openapi.json"

    return get_swagger_ui_html(
        openapi_url=openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )

@app.get("/redoc", include_in_schema=False)
async def redoc_html(admin_key: str | None = None):
    """ReDoc UI that dynamically includes admin routes based on API key"""
    # Validate admin key if provided
    admin_api_key = os.getenv("ADMIN_API_KEY", "")
    if admin_key and admin_api_key and admin_key == admin_api_key:
        # Pass admin key to openapi.json via query parameter
        openapi_url = f"/openapi.json?admin_key={admin_key}"
    else:
        openapi_url = "/openapi.json"

    return get_redoc_html(
        openapi_url=openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
    )

# Include main router
app.include_router(router)

# Static files configuration
project_root_path = Path(config.PROJECT_ROOT)
if not project_root_path.is_absolute():
    project_root_path = Path.cwd() / project_root_path
build_path = project_root_path.joinpath("src/agent_analytics/client/build")
static_path = build_path / "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Add authentication routes
app.get("/auth/login")(auth_login_get)
app.post("/auth/login")(auth_login_post)
app.get("/auth/logout")(auth_logout)
app.get("/auth/mode")(lambda: {
    "mode": "bypass" if should_bypass_auth() else ("local" if os.getenv("TEST", "false").lower() in ('true', '1', 'yes', 'on') else "saml")
})
app.post("/auth/auto-login")(auth_auto_login)

# Add SAML routes
app.get("/saml/login")(saml_login)
app.post("/saml/acs")(saml_acs)
app.get("/saml/metadata")(lambda: Response(
    content=saml_auth.init_saml_auth({}).get_settings().get_sp_metadata() if not should_bypass_auth() else "",
    media_type="application/xml"
))
app.get("/saml/logout")(saml_logout)
app.post("/saml/refresh-metadata")(refresh_metadata)

def main():
    """Entry point for the agentops console script"""
    # Print version banner
    version = get_version()
    print("=" * 70)
    print(f"  Agent Analytics Server v{version}")
    print("=" * 70)

    port = int(os.getenv("PORT", 8765))
    if 'CE_APP' in os.environ:
        uvicorn.run(app, host="0.0.0.0", port=port, timeout_keep_alive=300)
    else:
        # Try mounted certificates first, fallback to baked-in paths
        cert_base_path = "/app/config/saml-certificates"
        cert_file = Path(cert_base_path) / "certificate.pem"
        key_file = Path(cert_base_path) / "private.key"

        # Fallback to original paths if mounted certs don't exist
        if not cert_file.exists():
            cert_file = Path(config.PROJECT_ROOT) / "src/server/certificates/certificate.pem"
        if not key_file.exists():
            key_file = Path(config.PROJECT_ROOT) / "src/server/certificates/private_key.pem"

        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            timeout_keep_alive=300,
            ssl_certfile=str(cert_file),
            ssl_keyfile=str(key_file)
        )


if __name__ == "__main__":
    main()
