from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    TARGET_URL: str = "https://dashboard-agent-analytics.agent-analytics-9ca4d14d48413d18ce61b80811ba4308-0000.us-south.containers.appdomain.cloud/"

app = FastAPI(title="Redirect Service")
settings = Settings()

@app.get("/{full_path:path}")
async def redirect_all(request: Request, full_path: str = ""):
    """
    Redirects all incoming requests to the root of the target URL,
    ignoring any paths from the original request
    """
    # Just use the base TARGET_URL, ensuring it doesn't end with a slash
    target = settings.TARGET_URL.rstrip('/')
    
    print(f"Redirecting to: {target}")  # Add logging to help debug
    return RedirectResponse(url=target)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)