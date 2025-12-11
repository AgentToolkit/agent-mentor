import logging
import os
import re

import httpx
import requests
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from agent_analytics.server.routes import get_tenant_id, runtime_client
from agent_analytics.server.routes.jaeger_theme import CARBON_THEME_CSS, CARBON_THEME_JS

# Set up logging
logger = logging.getLogger(__name__)

PROXY_BASE_PATH = "/jaeger"
JAEGER_EMBED_PATH = os.environ.get('JAEGER_EMBED_PATH', "/jaeger")
proxy_server_url = os.environ.get('PROXY_SERVER_URL', None)

jaeger_router = APIRouter(
    prefix=PROXY_BASE_PATH,
    tags=["Jaeger"],
    dependencies=[Depends(get_tenant_id)]
)

@jaeger_router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def jaeger_proxy(path: str, request: Request, tenant_id: str = Depends(get_tenant_id)):
    """Jaeger reverse proxy with Carbon Design System styling"""

    # Handle root path
    if not path:
        path = ""

    # Main calls are of this type - but there could be request to static assets!!!
    # https://localhost:8765/jaeger/trace/d5f14eddd3edac5b883c3d3b736f5335
    # https://localhost:8765/jaeger/api/traces/d5f14eddd3edac5b883c3d3b736f5335

    ### This is a pre-flight call to the proxy to update the cache before we get there.
    path.split('/')[-1]
    if proxy_server_url and \
        (path.startswith("api/traces") or path.startswith("trace/")):
        trace_id = path.split('/')[-1]
        # TODO: Need to handle passing of multiple trace_ids
        payload = [{
            "trace_id": trace_id,
            "tenant_id": tenant_id
        }]
        response = requests.post(f'{proxy_server_url}/trace-tenant', json=payload)

    jaeger_base_url = await runtime_client.get_jaeger_url(tenant_id)
    jaeger_url = f"{jaeger_base_url}/{path}"

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        try:
            body = await request.body()

            # Clean headers
            headers = {
                key: value for key, value in request.headers.items()
                if key.lower() not in ["host", "content-length"]
            }

            # Handle parameters
            params = dict(request.query_params)

            response = await client.request(
                method=request.method,
                url=jaeger_url,
                params=params,
                content=body,
                headers=headers
            )

            # Process content
            content = response.content
            content_type = response.headers.get("content-type", "")

            if "text/html" in content_type.lower():
                content_str = content.decode('utf-8', errors='ignore')
                content_str = rewrite_html_urls(content_str, str(request.base_url))
                content_str = inject_carbon_styling(content_str)
                content = content_str.encode('utf-8')

            # Filter problematic headers
            filtered_headers = {
                key: value for key, value in response.headers.items()
                if key.lower() not in [
                    "connection", "keep-alive", "transfer-encoding", "content-encoding", "content-length"
                ]
            }

            return Response(
                content=content,
                status_code=response.status_code,
                headers=filtered_headers
            )

        except httpx.TimeoutException:
            logger.error(f"Timeout accessing {jaeger_url}")
            raise HTTPException(status_code=504, detail="Gateway timeout")
        except httpx.RequestError as e:
            logger.error(f"Request error accessing {jaeger_url}: {e}")
            raise HTTPException(status_code=502, detail=f"Bad gateway: {str(e)}")

def rewrite_html_urls(content: str, base_url: str) -> str:
    """Rewrite URLs in HTML"""

    # proxy_base = f"{base_url.rstrip('/')}{PROXY_BASE_PATH}"
    proxy_base = f"{JAEGER_EMBED_PATH}"

    patterns = [
        # Static asset references (JS, CSS, images)
        (r'((?:src|href)\s*=\s*["\'])(/static/[^"\']*)', rf'\1{proxy_base}\2'),
        (r'((?:src|href)\s*=\s*["\'])(/[^"\']*\.(?:js|css|png|svg|ico))', rf'\1{proxy_base}\2'),

        # API base URL for fetch calls
        (r'((?:apiPrefix|API_ROOT|baseURL)\s*[:=]\s*["\'])(/api)', rf'\1{proxy_base}\2'),

        # Base href if present
        (r'(<base\s+href\s*=\s*["\'])([^"\']*)', rf'\1{proxy_base}/'),

        # Catch any remaining absolute paths in common HTML attributes
        (r'((?:action|data-[^=]*)\s*=\s*["\'])(/[^"\']*)', rf'\1{proxy_base}\2'),
    ]

    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)

    return content

def inject_carbon_styling(content: str) -> str:
    """Inject Carbon Design System styling into Jaeger HTML content"""

    # Carbon Design System color tokens
    carbon_css = f"""
    <style>
    {CARBON_THEME_CSS}
    </style>
    """

    js_script = f"""
    <script>
    {CARBON_THEME_JS}
    </script>
    """

    styling_block = carbon_css + js_script

    # Inject the CSS before the closing </head> tag or at the beginning of <body>
    if '</head>' in content:
        content = content.replace('</head>', f'{styling_block}\n</head>')
    elif '<body' in content:
        # Find the end of the opening body tag
        body_start = content.find('<body')
        body_end = content.find('>', body_start) + 1
        content = content[:body_end] + f'\n{styling_block}\n' + content[body_end:]
    else:
        # Fallback: prepend to the content
        content = styling_block + '\n' + content

    return content
