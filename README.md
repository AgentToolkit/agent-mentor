# Agent Analytics


Backend analytics platform for agentic AI applications with observability and analytics.

## Repository Structure
```
agent-analytics/
├── backend/                    # Core analytics platform backend
│   ├── pyproject.toml         # Backend package configuration
│   ├── README.md
│   ├── src/
│   │   └── agent_analytics/   # Main package 
│   │       ├── __init__.py
│   │       ├── runtime/       # Runtime execution and orchestration
│   │       ├── core/          # Core analytics engine
│   │       ├── client/        # Internal client utilities
│   │       ├── server/        # FastAPI server and endpoints
│   │       └── extensions/    # Plugin system and extensions
│   └── tests/
│
├── sdk/                        # Client observability SDK
│   ├── pyproject.toml         # SDK package configuration
│   ├── README.md
│   ├── src/
│   │   └── agent_analytics_sdk/  # SDK package 
│   │       ├── __init__.py
│   │       ├── client.py
│   │       ├── decorators.py
│   │       └── ...
│   └── tests/
│
└── common/                     # Shared utilities and models
    ├── pyproject.toml         # Common package configuration
    ├── README.md
    ├── src/
        └── agent_analytics_common/  # Common package
   
```

## Packages

### Backend (`agent-analytics`)
Core analytics platform supporting trace collection and analytics.


### SDK 
Client library for instrumenting applications with analytics and observability.


### Common 
Shared data models, utilities, and types used across backend and SDK.


