# AgentOps - Agent Analytics Platform

> Open-source analytics and monitoring platform for AI agents

## ⚡ Build Modes

AgentOps supports two build modes to accommodate different dependency requirements:

### 🎯 **Basic** (Default)

- Core platform functionality and native analytics extensions only
- Faster builds and smaller footprint
- No 3rd part repository dependencies beyond `ibm_agent_analytics_common`
- Ideal for development and basic deployments

### 🚀 **With Extensions** (Optional)

- Full platform with advanced analytics extensions
- Includes `agent_pipe_eval`, `toolops_profile`, and `security-issues-generator`
- Requires access to private repositories (requires SSH login or GIT_TOKEN)
- Complete feature set for production use

The platform automatically adapts its UI and API based on available extensions.

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Node.js 20+**
- [**uv**](https://astral.sh/uv) (Python package manager)
- **Docker & Docker Compose** (Only for running as a container or persistent storage)

- **For Extensions Mode Only:**

  - **Git SSH access** to github.ibm.com (for private repositories)
  - **GitHub Personal Access Token** (for Docker builds)

## 🏠 Local Development (Recommended)

### Default Setup (In-Memory)

The application runs in-memory by default - no external services required.

### Setup and Launch Development Environment

**Basic Mode (Default):**

```bash
# Copy environment template 
cp .env.example .env

# Install all dependencies (Python + Node.js)
npm run setup

# Start the development server
npm run dev:memory
```

**With Extensions (Full Features):**

```bash
# Copy environment template 
cp .env.example .env

# Ensure you have SSH access to github.ibm.com
ssh -T git@github.ibm.com

# Install all dependencies including extensions
npm run setup:extensions

# Start development server - either in persistent or in memory mode
npm run dev:extensions # for persistent option

#Start development server in memory with extensions
npm run dev:memory:extensions

```

### That's it! 🎉

Waint till you see the message: `Application startup complete`. And then you can now access the application at: http://localhost:8765.

**Notes:**

- Upon first entrance, the app will show a mock login page, in which you can input any name and hit "Login" to enter.
- In order to try the application, you may upload any test file from the [test folder](./tests/runtime/integration_tests)
- Extension-dependent features will show appropriate messages if extensions are not installed

During development, you also have access to:

- **Backend API**: http://localhost:8765 (All-in-one server with python auto-reload)
- **API Documentation**: http://localhost:8765/docs
- **Frontend Dev Server**: http://localhost:3000 (React with hot reload - Only works if ran `npm run dev:full`)

**If using persistent storage setup:**
- **Jaeger UI**: http://localhost:16686 (distributed tracing)
- **Elasticsearch**: http://localhost:9200 (with credentials elastic/changeme)

## 🗄️ Persistent Storage Setup (Optional)

If you want results to persist across system runs, you can configure the system to use Elasticsearch:

### Start Infrastructure Services

```bash
# Start Elasticsearch + Jaeger in Docker
./docker/run_infra_only.sh

# Or - manually with docker-compose
docker compose -f docker/docker-compose-infra.yaml up
```

### Configure Persistent Storage

Copy the persistent storage environment template:

```bash
# Copy environment template for persistent mode
cp .env.example .env
```

Then restart the application.

## 🏢 Multi-Tenancy Setup (Optional)

AgentOps supports multi-tenancy for isolating trace data between different tenants. This is useful for SaaS deployments or environments with multiple teams/projects.

**Quick Start:**
```bash
# Deploy multi-tenant infrastructure
./docker/run_multi.sh
```

**Documentation:**
- **[Quick Start Guide](docker/MULTI_TENANCY_QUICK_START.md)** - Get multi-tenancy running in 5 minutes
- **[Detailed Guide](docker/MULTI_TENANCY_DETAILED.md)** - Comprehensive architecture, configuration, and best practices

**Key Features:**
- Complete data isolation between tenants
- Flexible routing to shared or dedicated Elasticsearch instances
- Transparent proxy architecture (Jaeger unaware of multi-tenancy)
- Support for dynamic tenant provisioning

## 🐳 Docker Development (Alternative)

If you prefer containerized development:

### Prerequisites for Docker

- Docker and Docker Compose
- **GIT_TOKEN** with access to github.ibm.com private repositories

### Setup

```bash
# First, copy the environment template
cp .env.example .env

```

### 🔐 Git Authentication Setup

This project has dependencies on private repositories for the extensions mode.
Add `GIT_TOKEN=your_github_token_here` to your .env file. The token can be obtained from your IBM's Github account and your account should have access to the relevant repos.

### Docker Build Options

**Basic (Default):**

```bash
# Quick start minimal build (no extensions)
./docker/run_build.sh
```

**With Extensions (Full Features):**

```bash
# Quick start with extensions (requires GIT_TOKEN)
./docker/run_build_extensions.sh
```

**First run might take a few minutes due to building the docker. Wait till you see the `Uvicorn running on http://0.0.0.0:8765` message and then access the application**: http://localhost:8765

## 📋 Development Commands

### Basic Commands (Work in Both Modes)

```bash
# Local Development
npm run dev              # Build frontend + start Python server (minimal mode)
ENABLE_EXTENSIONS=true npm run dev   # Build frontend + start Python server (with extensions)
npm run dev:quick        # Start both servers without building (faster, but needs existing build)
npm run dev:full         # Build frontend + Start both servers (useful for frontend development)
npm run dev:frontend     # Start React dev server only
npm run dev:backend      # Start FastAPI server only

# Building
npm run build            # Build both frontend and backend
npm run build:frontend   # Build React app for production
npm run build:backend    # Build Python package

# Testing
npm run test             # Run all tests
npm run test:frontend    # Frontend tests only
npm run test:platform    # Python platform tests
npm run test:extensions  # Python extension tests
npm run test:e2e         # End-to-end Cypress tests

# Code Quality
npm run lint             # Lint all code
npm run lint:fix         # Fix linting issues automatically
npm run format           # Format all code


# Setup options
npm run setup                 # Install all dependencies except extensions
npm run setup:with_extensions # Install all dependencies including extensions
npm run setup:extensions_only # Install only extensions

```

## 🐛 Debugging

### VSCode Users

**Quick Start:**

1. Install recommended VSCode extensions (you'll be prompted)
2. Set breakpoints in your code
3. Press `F5` or use the Debug panel
4. Choose your debug configuration (see options below) and click Run.

### Debug Configuration Setup

The project includes debug configurations for both modes:

**For Basic Mode (no extensions):**
- Use debug configurations with 🔧 icon (wrench)
- No additional setup required

**For Extensions Mode:**
- First install extensions: `npm run setup:extensions`
- Use debug configurations with 🧩 icon (puzzle piece)
- These configurations set `ENABLE_EXTENSIONS=true` automatically

This project includes pre-configured debug settings:

- **🔧 Debug Python Server**: Basic mode without extensions
- **🧩 Debug Python Server with extensions**: Full-featured mode with extensions
- **⚛️ React Client**: Debug frontend in Chrome with source maps
- **🚀 Full Stack**: Debug both frontend and backend simultaneously
- **🧪 Tests**: Debug individual test files or test suites

Icons help distinguish between basic mode (🔧) and extensions mode (🧩) configurations.

## 🗃️ Project Structure

```
agentops/
├── src/
│   ├── core/                # Common classes and interfaces
│   ├── client/              # React frontend application
│   ├── server/              # FastAPI backend server (main.py)
│   ├── runtime/             # Core platform logic
│   └── extensions/          # Analytics extensions (optional features)
├── docker/                  # Docker configuration files
├── tests/                   # All tests (frontend, backend, e2e)
├── pyproject.toml          # Python dependencies and config
└── package.json            # Node.js orchestration scripts
```

## 🔧 Troubleshooting

### Common Issues

**Infrastructure Services Not Running (Persistent Storage Only):**

```bash
# Only needed if you configured persistent storage in proxy-config.yaml
# Check if Elasticsearch is running
curl -u elastic:changeme http://localhost:9200/_cluster/health

# Check if Jaeger is running
curl http://localhost:16686

# If not running, start infrastructure
./docker/run_infra_only.sh
```

**Backend Fails to Connect to Elasticsearch/Jaeger:**

- Ensure infrastructure is running on default ports (ES: 9200, Jaeger: 16686)
- Check Docker containers: `docker ps`
- Verify Elasticsearch credentials: `elastic/changeme`

**Static Files Error (`Directory 'src/client/build/static' does not exist`):**

```bash
# Build the frontend first
npm run build:frontend

# Or use the dev command that auto-builds
npm run dev
```

**PROJECT_ROOT Issues:**

- The app auto-detects the project root based on the main.py file location
- For local development: don't set PROJECT_ROOT (let it auto-detect)
- For containers: PROJECT_ROOT is set to `/app` automatically
- For custom paths: set PROJECT_ROOT to absolute path

**SSH Authentication Failed (Extensions Mode):**

```bash
# Verify SSH access
ssh -T git@github.ibm.com

# If it fails, check your SSH keys
ls -la ~/.ssh/
# Make sure you have id_rsa and id_rsa.pub (or similar key pair)
```

**Docker Build Fails with Git Authentication:**

```bash
# Make sure GIT_TOKEN is set in your .env file
grep GIT_TOKEN .env

# Verify the token has repository access
curl -H "Authorization: token $GIT_TOKEN" https://api.github.ibm.com/user
```

**UV Sync Issues:**

```bash
# Clear UV cache and retry
rm -rf .venv
uv cache clean
npm run setup
```

**Feature Not Available Errors:**

- These are normal when extensions are not installed
- The application gracefully handles missing extensions
- To enable full features, use extensions mode: `npm run setup:extensions`

**Windows Environment Variable Issues:**
- In case you encounter  "is not recognized as an internal or external command" errors when running npm scripts
- This configures npm to use bash shell instead of Window's cmd.exe
- Provide a path to bash shell installed on your environment 
```bash
# If npm scripts fail with environment variable errors on Windows, configure npm to use bash shell.
# In this invocation Git bash shell is used
npm config set script-shell "C:\\Program Files\\Git\\bin\\bash.exe"
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and ensure tests pass: `npm run test`
4. Run code quality checks: `npm run lint && npm run format`
5. Submit a pull request

**For Extension Development:**

- Use extensions mode: `npm run setup:with_extensions`
- Test both minimal and extensions modes
- Ensure graceful degradation when extensions are not available

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.