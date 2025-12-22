# Agent Analytics

**Open-source observability and analytics platform for agentic AI applications**

## Overview

Agent Analytics is a comprehensive Python-based observability platform designed specifically for AI agent applications. It provides end-to-end visibility into agent behavior, performance, and decision-making processes through automated instrumentation and advanced analytics.

### Key Components

**Observability SDK**
- Framework-agnostic instrumentation for AI agent applications
- Built on OpenTelemetry (OTEL) standards and frameworks
- Support for automatic and manual trace collection from agent runtime
- Flexible trace persistence options: filesystem or remote collectors (Jaeger, Elasticsearch)
- Compatible with popular frameworks: LangChain, LangGraph, CrewAI, and more

**Analytics Platform**
- FastAPI-powered backend server with React UI
- Ingests traces from configurable storage backends
- Performs high-level analytics on collected traces:
  - Task flow analysis and visualization
  - Performance metrics aggregation
  - Issue detection and tracking
  - Workflow graph generation
  - Resource utilization analysis
- Interactive web interface for exploring and analyzing agent behavior

**Shared Common Library**
- Standardized data models and interfaces
- Pydantic-based schema definitions for annotations, tasks, actions, metrics, and issues
- Ensures consistency across SDK and backend components

## Features

- **Zero-Code Instrumentation**: Automatic tracing for supported frameworks
- **Manual Instrumentation**: APIs for custom semantic reporting (issues, resources, annotations)
- **OTEL-Compliant**: Standard OpenTelemetry trace generation
- **Flexible Deployment**: In-memory mode for development, persistent storage for production
- **Rich Analytics**: Task hierarchies, flow graphs, aggregated metrics, and issue tracking
- **Multi-Framework Support**: Works with LangChain, LangGraph, CrewAI, LiteLLM, and more

---

## Repository Structure

```
agent-analytics/
├── backend/                    # Analytics platform backend
│   ├── src/
│   │   └── agent_analytics/
│   │       ├── server/        # FastAPI server and API endpoints
│   │       ├── runtime/       # Trace processing and analytics engine
│   │       ├── core/          # Core data models and logic
│   │       ├── extensions/    # Analytics extensions and plugins
│   │       ├── client/        # React frontend application
│   │       └── sdk/           # Backend SDK resources
│   ├── pyproject.toml         # Backend dependencies (uv)
│   ├── package.json           # npm orchestration scripts
│   └── README.md              # Backend documentation
│
├── sdk/                        # Observability SDK
│   ├── src/
│   │   └── agent_analytics/
│   │       └── instrumentation/   # Instrumentation package
│   │           ├── reportable/    # Manual reporting APIs
│   │           ├── configs/       # Configuration classes
│   │           ├── utils/         # Utility functions
│   │           └── traceloop/     # Traceloop integration
│   ├── tests/                 # SDK test suite
│   ├── docs/                  # Architecture and guides
│   ├── setup.py               # SDK package configuration
│   └── README.md              # SDK documentation
│
├── common/                     # Shared library
│   ├── src/
│   │   └── agent_analytics_common/
│   │       └── interfaces/    # Shared data models (Pydantic)
│   ├── setup.py               # Common package configuration
│   └── README.md              # Common library documentation
│
└── README.md                   # This file
```

---

## Quick Start

### For SDK Users (Instrument Your Application)

**Installation:**
```bash
pip install "git+https://github.com/AgentToolkit/agent-analytics.git@main#subdirectory=sdk"
```

**Basic Usage:**
```python
from agent_analytics.instrumentation import agent_analytics_sdk

# Initialize observability (logs to filesystem by default)
agent_analytics_sdk.initialize_observability()

# Your agent code here...
```

**📚 Full SDK Documentation:** [sdk/README.md](sdk/README.md)

---

### For Platform Users (Run the Analytics Backend)

**Prerequisites:**
- Python 3.10+
- Node.js >= 20.0.0
- npm >= 9.0.0
- uv (Python package manager)

**Installation:**
```bash
git clone https://github.com/AgentToolkit/agent-analytics.git
cd agent-analytics/backend

# Setup environment
cp .env.example .env

# Install dependencies
npm run setup

# Start in-memory mode (no external services needed)
npm run dev:memory
```

Access the platform at: http://localhost:8765

**📚 Full Backend Documentation:** [backend/README.md](backend/README.md)

---

## Documentation

- **[SDK Documentation](sdk/README.md)** - Instrumentation guide, configuration options, examples
- **[Backend Documentation](backend/README.md)** - Platform setup, deployment modes, troubleshooting
- **[Common Library](common/README.md)** - Shared data models and interfaces

---

## Architecture

### Data Flow

```
┌─────────────────┐
│  Your Agent App │
│   (with SDK)    │
└────────┬────────┘
         │ OTEL Traces
         ▼
┌─────────────────┐
│ Storage Backend │ ◄─── Filesystem / Jaeger / Elasticsearch
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Analytics       │
│ Platform        │ ──► Flow Graphs, Metrics, Issues
│ (Backend)       │
└─────────────────┘
         │
         ▼
   ┌─────────┐
   │  Web UI │
   └─────────┘
```

### Key Technologies

- **SDK**: Python, OpenTelemetry, Pydantic
- **Backend**: FastAPI, Python
- **Frontend**: React, TypeScript
- **Storage**: Elasticsearch (persistent), In-memory (development)
- **Tracing**: Jaeger, OTLP collectors

---

## Deployment Modes

### Development (In-Memory)
- No external dependencies
- Data persists during runtime only
- Fastest setup for testing and development

### Production (Persistent)
- Requires Elasticsearch and Jaeger instances
- Data persists across restarts
- Scalable for production workloads

See [backend/README.md](backend/README.md) for detailed deployment instructions.

---

## Contributing

We welcome contributions! To get started:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes and ensure tests pass
4. Run code quality checks: `npm run lint && npm run format` (backend)
5. Submit a pull request

---

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

---

## Support

For questions, issues, or feature requests, please open an issue on GitHub.
