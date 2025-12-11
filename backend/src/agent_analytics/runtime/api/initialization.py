# api/initialization.py
import asyncio
import base64
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from typing import Any

from elasticsearch import AsyncElasticsearch
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from opensearchpy import AsyncOpenSearch
from pymongo import ASCENDING, DESCENDING, IndexModel

from agent_analytics.core.data.action_data import ActionData
from agent_analytics.core.data.annotation_data import AnnotationData
from agent_analytics.core.data.issue_data import IssueData
from agent_analytics.core.data.metric_data import MetricData
from agent_analytics.core.data.span_data import BaseSpanData
from agent_analytics.core.data.task_data import TaskData
from agent_analytics.core.data.trace_data import BaseTraceData
from agent_analytics.core.data.trace_group_data import TraceGroupData
from agent_analytics.core.data.trace_workflow_data import TraceWorkflowData
from agent_analytics.core.data.workflow_data import WorkflowData
from agent_analytics.core.data.workflow_edge_data import WorkflowEdgeData
from agent_analytics.core.data.workflow_node_data import WorkflowNodeData
from agent_analytics.runtime.api import TenantComponents, app_state
from agent_analytics.runtime.api.config import Settings
from agent_analytics.runtime.api.exceptions_handlers import (
    ValidationException,
    setup_exception_handlers,
)
from agent_analytics.runtime.api.tenant_config_service import (
    StoreType,
    TenantConfig,
    tenant_config_service,
)
from agent_analytics.runtime.executor.analytics_execution_engine import AnalyticsRuntimeEngine
from agent_analytics.runtime.executor.executor_results_data_manager import (
    ExecutionResultsDataManager,
)
from agent_analytics.runtime.registry.analytics_registry import AnalyticsRegistry
from agent_analytics.runtime.registry.registry_data_manager import RegistryDataManager
from agent_analytics.runtime.storage.elasticsearch_store import (
    ElasticSearchStoreConfig,
    ElasticSearchStoreFactory,
)
from agent_analytics.runtime.storage.jaeger_store import JaegerStoreConfig, JaegerStoreFactory
from agent_analytics.runtime.storage.logical_data_manager import AnalyticsDataManager
from agent_analytics.runtime.storage.memory_store import MemoryStoreConfig, MemoryStoreFactory
from agent_analytics.runtime.storage.mongo_store import MongoStoreConfig, MongoStoreFactory
from agent_analytics.runtime.storage.open_search_store import (
    OpenSearchStoreConfig,
    OpenSearchStoreFactory,
)

logger = logging.getLogger(__name__)
DEFAULT_TENANT_ID = os.getenv('DEFAULT_TENANT_ID', 'default')

MINIMAL_SETTING = {
    "index": {
        "mapping": {
            "total_fields": {
                "limit": 2000
            }
        }
    }
}
MINIMAL_MAPPING = {
        "dynamic": False,
        "properties": {
            "log_reference": {
                "properties": {
                    "span_id": {
                        "type": "keyword"
                    },
                    "trace_id": {
                        "type": "keyword"
                    }
                }
            },
            "id": {
                "type": "keyword"
            },
            "start_time": {
                "type": "date"
            },
            "end_time": {
                "type": "date"
            },
            "type": {
                "type": "keyword"
            },
            "tenant_id": {
                "type": "keyword"
            },
            "status": {
                "type": "keyword"
            },
            "element_id": {
                "type": "keyword"
            },
            "analytics_id": {
                "type": "keyword"
            },
            "root_id": {
                "type": "keyword"
            },
            "result_id": {
                "type": "keyword"
            },
            "name": {
                "type": "keyword"
            },
            "parent_id": {
                "type": "keyword"
            },
            "dependent_ids": {
                "type": "keyword"
            },
            "related_to_ids":
            {
              "type": "keyword"
            },
            "related_to_types":
            {
              "type": "keyword"
            },
            "created_at": {
                "type": "date"
            },
            "updated_at": {
                "type": "date"
            },
            "service_name": {
                "type": "keyword"
            },
            "annotation_type": {
                "type": "keyword"
            },
            "timestamp": {
                "type": "date"
            },
            "level": {
                "type": "keyword"
            },
            "plugin_metadata_id": {
                "type": "keyword"
            }
        }
    }

INDEX_BASE_NAMES = {
    'artifacts': 'analytics_artifacts',
    'execution_results': 'execution_results',
    'metadata': 'analytics_metadata'
}

# Global list of all supported artifact types - single source of truth
SUPPORTED_ARTIFACT_TYPES = [
    BaseTraceData,
    IssueData,
    MetricData,
    TaskData,
    TraceWorkflowData,
    WorkflowData,
    WorkflowEdgeData,
    WorkflowNodeData,
    TraceGroupData,
    AnnotationData,
    ActionData,
]


# Global certificate caching
_ca_cert_path: str | None = None
_ca_cert_content: str | None = None
_shared_clients: dict[str, Any] = {}
_clients_lock = asyncio.Lock()


def get_index_name_for_artifact_type(artifact_type: type) -> str:
    """Generate consistent index name for artifact type"""
    return f"{INDEX_BASE_NAMES['artifacts']}_{artifact_type.__name__.lower()}"

def get_all_artifact_index_names() -> list[str]:
    """Get all artifact index names"""
    return [get_index_name_for_artifact_type(artifact_type) for artifact_type in SUPPORTED_ARTIFACT_TYPES]

def get_all_index_names() -> list[str]:
    """Get all index names that need to be created"""
    artifact_indexes = get_all_artifact_index_names()
    other_indexes = [
        INDEX_BASE_NAMES['execution_results'],
        INDEX_BASE_NAMES['metadata']
    ]
    return artifact_indexes + other_indexes

def get_client_key(host: str, username: str, store_type: str) -> str:
    """Generate client key"""
    return f"{store_type}:{host}:{username}"

async def get_or_create_es_client(host: str, username: str, password: str) -> AsyncElasticsearch:
    """Get or create shared ES client with index initialization"""
    client_key = get_client_key(host, username, "es")

    if client_key in _shared_clients:
        return _shared_clients[client_key]

    async with _clients_lock:
        if client_key in _shared_clients:
            return _shared_clients[client_key]

        logger.info(f"Creating ES client and initializing indexes for {host}")

        # Create client (same as your existing code)
        if host.startswith('https://'):
            ca_cert_path = get_ca_cert_path()
            config = {
                "hosts": [host],
                "basic_auth": (username, password),
                "verify_certs": True if ca_cert_path else False,
                "ssl_show_warn": False,
                "request_timeout": 30
            }
            if ca_cert_path:
                config["ca_certs"] = ca_cert_path
            client = AsyncElasticsearch(**config)
        else:
            client = AsyncElasticsearch(
                hosts=[host],
                basic_auth=(username, password)
            )

        # Initialize all indexes immediately
        await _initialize_es_indexes(client)

        _shared_clients[client_key] = client
        return client

async def get_or_create_os_client(host: str, username: str, password: str) -> AsyncOpenSearch:
    """Get or create shared OS client with index initialization"""
    client_key = get_client_key(host, username, "os")

    if client_key in _shared_clients:
        return _shared_clients[client_key]

    async with _clients_lock:
        if client_key in _shared_clients:
            return _shared_clients[client_key]

        logger.info(f"Creating OS client and initializing indexes for {host}")


        if host and host.startswith('https://'):

            ca_cert_path = get_ca_cert_path()
            config = {
                "hosts": [host],
                "http_auth": (username, password),
                "use_ssl": True,
                "verify_certs": True if ca_cert_path else False,
                "ssl_show_warn": False,
                "timeout": 30,
                "max_retries": 3,
                "retry_on_timeout": True
            }
            if ca_cert_path:
                config["ca_certs"] = ca_cert_path
            client = AsyncOpenSearch(**config)
        else:
            client = AsyncOpenSearch(
                hosts=[host],
                http_auth=(username, password),
                use_ssl=False,
                verify_certs=False,
                ssl_show_warn=False,
                timeout=30,
                max_retries=3,
                retry_on_timeout=True
            )

        # Initialize all indexes immediately
        await _initialize_os_indexes(client)

        _shared_clients[client_key] = client
        return client

async def _initialize_es_indexes(client: AsyncElasticsearch):
    """Initialize all ES indexes once when client is created"""
    indexes_to_create = get_all_index_names()

    for index_name in indexes_to_create:
        try:
            exists = await client.indices.exists(index=index_name)
            if not exists:
                body = {
                    "settings": MINIMAL_SETTING,
                    "mappings": MINIMAL_MAPPING
                }
                await client.indices.create(index=index_name, body=body)
                logger.info(f"Created ES index: {index_name}")
            else:
                logger.debug(f"ES index already exists: {index_name}")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.debug(f"ES index {index_name} created by another process")
            else:
                logger.error(f"Error creating ES index {index_name}: {e}")
                raise

async def _initialize_os_indexes(client: AsyncOpenSearch):
    """Initialize all OS indexes once when client is created"""
    indexes_to_create = get_all_index_names()

    for index_name in indexes_to_create:
        try:
            exists = await client.indices.exists(index=index_name)
            if not exists:
                body = {
                    "settings": MINIMAL_SETTING,
                    "mappings": MINIMAL_MAPPING
                }
                await client.indices.create(index=index_name, body=body)
                logger.info(f"Created OS index: {index_name}")
            else:
                logger.debug(f"OS index already exists: {index_name}")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.debug(f"OS index {index_name} created by another process")
            else:
                logger.error(f"Error creating OS index {index_name}: {e}")
                raise

def format_pem_certificate(cert_data: str) -> str:
    """Format certificate data into proper PEM format with 64-character line wrapping."""
    # Remove any existing headers/footers and whitespace
    cert_data = cert_data.replace('-----BEGIN CERTIFICATE-----', '')
    cert_data = cert_data.replace('-----END CERTIFICATE-----', '')
    cert_data = ''.join(cert_data.split())  # Remove all whitespace

    # Wrap base64 data at 64 characters per line
    wrapped_data = '\n'.join(cert_data[i:i+64] for i in range(0, len(cert_data), 64))

    # Construct proper PEM format
    return f"-----BEGIN CERTIFICATE-----\n{wrapped_data}\n-----END CERTIFICATE-----"


def get_ca_cert_path() -> str | None:
    """Get CA certificate path from environment variables with caching."""
    global _ca_cert_path, _ca_cert_content

    # Return cached path if it still exists
    if _ca_cert_path and _ca_cert_content and os.path.exists(_ca_cert_path):
        return _ca_cert_path

    # Recreate temp file if it disappeared
    if _ca_cert_path and _ca_cert_content and not os.path.exists(_ca_cert_path):
        logger.warning("Certificate file disappeared, recreating...")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
            f.write(_ca_cert_content)
            _ca_cert_path = f.name
        return _ca_cert_path

    # First time setup
    if _ca_cert_content is None:
        # Option 1: Certificate content directly in env var
        if os.environ.get('CA_CERT_CONTENT'):
            cert_content = os.environ.get('CA_CERT_CONTENT', '')
            _ca_cert_content = format_pem_certificate(cert_content)

        # Option 2: Base64 encoded certificate in env var
        elif os.environ.get('CA_CERT_B64'):
            try:
                cert_b64 = os.environ.get('CA_CERT_B64', '')
                cert_content = base64.b64decode(cert_b64).decode('utf-8')
                _ca_cert_content = format_pem_certificate(cert_content)
            except Exception as e:
                logger.error(f"Failed to decode base64 certificate: {e}")
                return None

        # Option 3: Path to mounted certificate file
        elif os.environ.get('CA_CERT_PATH'):
            cert_path = os.environ.get('CA_CERT_PATH', '')
            if os.path.exists(cert_path):
                return cert_path  # Return directly, no temp file needed
            else:
                logger.error(f"Certificate file not found: {cert_path}")
                return None
        else:
            return None  # No certificate configuration

        # Create temp file for options 1 and 2
        if _ca_cert_content:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
                f.write(_ca_cert_content)
                _ca_cert_path = f.name

    return _ca_cert_path

async def init_memory_for_tenant(tenant_config: TenantConfig) -> tuple[Any, RegistryDataManager, ExecutionResultsDataManager, AnalyticsDataManager]:
    """Initialize Memory stores for a specific tenant."""
    factory = MemoryStoreFactory()
    store_configs = {}

    # All artifacts with tenant isolation
    for artifact_type in SUPPORTED_ARTIFACT_TYPES:
        data_artifacts_config = MemoryStoreConfig(
            id_field="element_id",
            tenant_id=tenant_config.tenant_id,
            soft_delete=True,
            case_sensitive=False
        )
        store_configs[(artifact_type,)] = (factory, data_artifacts_config)

    #Also explicitly setup config for BaseSpanData, in memory store we keep everything
    base_span_data_config = MemoryStoreConfig(
            id_field="element_id",
            tenant_id=tenant_config.tenant_id,
            soft_delete=True,
            case_sensitive=False
        )
    store_configs[(BaseSpanData,)] = (factory, base_span_data_config)

    data_artifacts_manager = await AnalyticsDataManager.create(store_configs=store_configs)

    # Execution results with tenant isolation
    execution_results_config = MemoryStoreConfig(
        id_field="result_id",
        tenant_id=tenant_config.tenant_id,
        soft_delete=True,
        case_sensitive=False
    )
    execution_results_data_manager = await ExecutionResultsDataManager.create(factory, execution_results_config)

    # Registry with tenant isolation
    registry_config = MemoryStoreConfig(
        id_field="id",
        tenant_id=tenant_config.tenant_id,
        soft_delete=True,
        case_sensitive=False
    )
    registry_data_manager = await RegistryDataManager.create(factory, registry_config)

    return None, registry_data_manager, execution_results_data_manager, data_artifacts_manager

async def init_mongo_for_tenant(tenant_config: TenantConfig) -> tuple[Any, RegistryDataManager, ExecutionResultsDataManager, AnalyticsDataManager]:
    """Initialize MongoDB stores for a specific tenant."""
    connection_str = tenant_config.connection_str
    if tenant_config.username and tenant_config.password and connection_str:
        # Insert credentials into connection string if provided
        connection_str = connection_str.replace("://", f"://{tenant_config.username}:{tenant_config.password}@")

    mongo_client = AsyncIOMotorClient(connection_str)
    db = mongo_client[tenant_config.database_name or '']
    factory = MongoStoreFactory(db)

    # Get collection names with tenant prefix
    if not tenant_config.additional_config:
        raise ValidationException("init_mongo_for_tenant: tenant_config.additional_config cannot be None")

    data_collection = 'data_artifacts_collection'
    execution_collection = 'executor_results_collection'
    analytics_collection = 'analytics_collection'

    # Data artifacts manager config
    data_manager_config = MongoStoreConfig(
        collection_name=data_collection,
        indexes=[
            IndexModel([("element_id", ASCENDING)], unique=True),
            IndexModel([("root_id", ASCENDING)]),
            IndexModel([("tenant_id", ASCENDING)]),
            IndexModel([("type", ASCENDING)]),
            IndexModel([("type", ASCENDING), ("root_id", ASCENDING)])
        ],
        tenant_id=tenant_config.tenant_id
    )
    data_artifacts_manager = await AnalyticsDataManager.create(store_configs=(factory, data_manager_config))

    # Execution results manager config
    execution_data_config = MongoStoreConfig(
        collection_name=execution_collection,
        indexes=[
            IndexModel([("result_id", ASCENDING)], unique=True),
            IndexModel([("tenant_id", ASCENDING)]),
            IndexModel([("analytics_id", ASCENDING)]),
            IndexModel([("start_time", DESCENDING)])
        ],
        tenant_id=tenant_config.tenant_id
    )
    execution_results_data_manager = await ExecutionResultsDataManager.create(factory, execution_data_config)

    # Registry manager config
    registry_config = MongoStoreConfig(
        collection_name=analytics_collection,
        indexes=[
            IndexModel([("id", ASCENDING)], unique=True),
            IndexModel([("tenant_id", ASCENDING)]),
            IndexModel([("name", ASCENDING)]),
            IndexModel([("version", ASCENDING)])
        ],
        tenant_id=tenant_config.tenant_id
    )
    registry_data_manager = await RegistryDataManager.create(factory, registry_config)

    return mongo_client, registry_data_manager, execution_results_data_manager, data_artifacts_manager

async def init_opensearch_for_tenant(tenant_config: TenantConfig) -> tuple[Any, RegistryDataManager, ExecutionResultsDataManager, AnalyticsDataManager]:
    global supported_types

    """Initialize OpenSearch stores for a specific tenant."""
    # Use credentials from tenant config or fall back to environment
    username = tenant_config.username or os.environ.get('OS_USERNAME')
    password = tenant_config.password or os.environ.get('OS_PASSWORD')
    host = tenant_config.hostname or os.environ.get('OS_HOST')

    os_client = await get_or_create_os_client(host, username, password)
    store_configs = {}

    # Span configuration (no tenant prefix for Jaeger)
    span_factory = JaegerStoreFactory()
    span_type = BaseSpanData
    span_artifacts_config = JaegerStoreConfig(
        url=tenant_config.jaeger_url or 'http://localhost:16686',
        tenant_id=tenant_config.tenant_id
    )
    store_configs[(span_type,)] = (span_factory, span_artifacts_config)

    # Other artifacts with tenant-prefixed indexes
    factory = OpenSearchStoreFactory(os_client,initialize_index=False)

    for artifact_type in SUPPORTED_ARTIFACT_TYPES:
        index_name = get_index_name_for_artifact_type(artifact_type)

        data_artifacts_config = OpenSearchStoreConfig(
            index_name=index_name,
            id_field="element_id",
            mappings=MINIMAL_MAPPING,
            settings=MINIMAL_SETTING,
            tenant_id=tenant_config.tenant_id
        )
        store_configs[(artifact_type,)] = (factory, data_artifacts_config)

    data_artifacts_manager = await AnalyticsDataManager.create(store_configs=store_configs)

    # Execution results with tenant prefix
    execution_results_config = OpenSearchStoreConfig(
        index_name=INDEX_BASE_NAMES['execution_results'],
        id_field="result_id",
        mappings=MINIMAL_MAPPING,
        settings=MINIMAL_SETTING,
        tenant_id=tenant_config.tenant_id
    )
    execution_results_data_manager = await ExecutionResultsDataManager.create(factory, execution_results_config)

    # Registry with tenant prefix
    registry_config = OpenSearchStoreConfig(
        index_name=INDEX_BASE_NAMES['metadata'],
        id_field="id",
        mappings=MINIMAL_MAPPING,
        settings=MINIMAL_SETTING,
        tenant_id=tenant_config.tenant_id
    )
    registry_data_manager = await RegistryDataManager.create(factory, registry_config)

    return os_client, registry_data_manager, execution_results_data_manager, data_artifacts_manager

async def init_elasticsearch_for_tenant(tenant_config: TenantConfig) -> tuple[Any, RegistryDataManager, ExecutionResultsDataManager, AnalyticsDataManager]:
    global supported_types

    """Initialize Elasticsearch stores for a specific tenant."""
    # Use credentials from tenant config or fall back to environment
    username = tenant_config.username or os.environ.get('ES_USERNAME')
    password = tenant_config.password or os.environ.get('ES_PASSWORD')
    host = tenant_config.hostname or os.environ.get('ES_HOST')

    if not host or not username or not password:
        raise ValidationException("Missing ES_HOST or ES_USERNAME or ES_PASSWORD in tenant_config!")

    # Parse the protocol
    es_client = await get_or_create_es_client(host, username, password)

    store_configs = {}

    # Span configuration (no tenant prefix for Jaeger)
    span_factory = JaegerStoreFactory()
    span_type = BaseSpanData
    span_artifacts_config = JaegerStoreConfig(
        url=tenant_config.jaeger_url or 'http://localhost:16686',
        tenant_id = tenant_config.tenant_id
    )
    store_configs[(span_type,)] = (span_factory, span_artifacts_config)

    # Other artifacts with tenant-prefixed indexes
    factory = ElasticSearchStoreFactory(es_client,initialize_index=False)

    for artifact_type in SUPPORTED_ARTIFACT_TYPES:
        index_name = get_index_name_for_artifact_type(artifact_type)

        data_artifacts_config = ElasticSearchStoreConfig(
            index_name=index_name,
            id_field="element_id",
            mappings=MINIMAL_MAPPING,
            settings=MINIMAL_SETTING,
            tenant_id=tenant_config.tenant_id
        )
        store_configs[(artifact_type,)] = (factory, data_artifacts_config)

    data_artifacts_manager = await AnalyticsDataManager.create(store_configs=store_configs)

    # Execution results with tenant prefix
    execution_results_config = ElasticSearchStoreConfig(
        index_name=INDEX_BASE_NAMES['execution_results'],
        id_field="result_id",
        mappings=MINIMAL_MAPPING,
        settings=MINIMAL_SETTING,
        tenant_id=tenant_config.tenant_id
    )
    execution_results_data_manager = await ExecutionResultsDataManager.create(factory, execution_results_config)

    # Registry with tenant prefix
    registry_config = ElasticSearchStoreConfig(
        index_name=INDEX_BASE_NAMES['metadata'],
        id_field="id",
        mappings=MINIMAL_MAPPING,
        settings=MINIMAL_SETTING,
        tenant_id=tenant_config.tenant_id
    )
    registry_data_manager = await RegistryDataManager.create(factory, registry_config)

    return es_client, registry_data_manager, execution_results_data_manager, data_artifacts_manager


async def init_backend_for_tenant(tenant_id: str | None = None) -> TenantComponents:
    """Initialize backend components for a specific tenant."""
    # Get tenant configuration
    tenant_config =  await tenant_config_service.get_tenant_config(tenant_id)

    # Determine store type
    store_type = tenant_config.store_type

    # Initialize based on store type
    if store_type == StoreType.OPENSEARCH:
        client, registry_dm, execution_dm, data_dm = await init_opensearch_for_tenant(tenant_config)
    elif store_type == StoreType.MONGODB:
        client, registry_dm, execution_dm, data_dm = await init_mongo_for_tenant(tenant_config)
    elif store_type == StoreType.MEMORY:
        client, registry_dm, execution_dm, data_dm = await init_memory_for_tenant(tenant_config)
    else:  # elasticsearch
        client, registry_dm, execution_dm, data_dm = await init_elasticsearch_for_tenant(tenant_config)

    # Create tenant components
    registry = AnalyticsRegistry(store=registry_dm)
    executor = AnalyticsRuntimeEngine(registry, execution_dm, data_dm)

    components = TenantComponents(
        tenant_id=tenant_config.tenant_id,
        db_client=client,
        registry=registry,
        executor=executor,
        execution_results_manager=execution_dm,
        data_manager=data_dm,
        initialized=True
    )

    logger.info(f"Initialized backend for tenant: {tenant_config.tenant_id}")
    return components

async def ensure_tenant_initialized(tenant_id: str | None = None) -> tuple[TenantComponents, TenantConfig, bool]:
    """Ensure tenant is initialized, with thread-safe initialization."""
    if app_state.is_tenant_initialized(tenant_id):
        return app_state.get_tenant_components(tenant_id), await tenant_config_service.get_tenant_config(tenant_id), False

    # Use tenant-specific lock to prevent concurrent initialization
    async with app_state.get_initialization_lock(tenant_id):
        # Double-check after acquiring lock
        if app_state.is_tenant_initialized(tenant_id):
            return app_state.get_tenant_components(tenant_id), await tenant_config_service.get_tenant_config(tenant_id), False

        # Initialize tenant
        components = await init_backend_for_tenant(tenant_id)
        app_state.set_tenant_components(tenant_id, components)

        return components, await tenant_config_service.get_tenant_config(tenant_id), True

async def clear_backend_for_tenant(tenant_id: str | None = None):
    """Clear backend resources for a specific tenant."""
    await app_state.cleanup_tenant(tenant_id)

async def clear_all_backends():
    """Clear all tenant backends."""
    await app_state.cleanup_all_tenants()


def create_app() -> FastAPI:
    """Create FastAPI application with tenant support."""
    if app_state.app:
        return app_state.app

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: Initialize default tenant
        try:
            await ensure_tenant_initialized(None)  # Initialize default tenant
            logger.info("Application startup complete")
        except Exception as e:
            logger.error(f"Failed to initialize default tenant: {e}")
            raise

        yield

        # Shutdown: Cleanup all tenants
        try:
            await clear_all_backends()
            logger.info("Application shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    settings = Settings()
    app = FastAPI(
        title="Multi-Tenant Analytics Registry API",
        lifespan=lifespan
    )

    app_state.app = app
    app_state.config = settings.model_dump()

    # Setup components
    setup_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


    return app