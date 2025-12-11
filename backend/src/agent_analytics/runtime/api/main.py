import uvicorn

from agent_analytics.runtime.api.initialization import create_app


def main():
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=9001)

if __name__ == "__main__":
    main()
