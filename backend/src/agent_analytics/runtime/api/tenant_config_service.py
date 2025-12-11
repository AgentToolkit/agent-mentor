import logging
from enum import Enum
from typing import Any

import aiohttp
import yaml
from pydantic import BaseModel

from agent_analytics.runtime.api.config import Settings

logger = logging.getLogger(__name__)

class StoreType(str, Enum):
    MONGODB = "mongodb"
    ELASTICSEARCH = "elasticsearch"
    OPENSEARCH = "opensearch"
    MEMORY = "memory"
    LANGFUSE_ELASTICSEARCH = "langfuse+elasticsearch"
    LANGFUSE_MEMORY = "langfuse+memory"
    LANGFUSE = "langfuse"

class TenantConfig(BaseModel):
    tenant_id: str
    connection_str: str | None=None
    database_name: str | None = None
    username: str | None = None
    password: str | None = None
    hostname: str | None = None
    jaeger_url: str | None = None
    jaeger_collect_url: str | None = None
    store_type: StoreType = StoreType.ELASTICSEARCH
    additional_config: dict[str, Any] | None = {}

class TenantConfigNotFoundError(Exception):
    """Exception raised when tenant config cannot be fetched from remote service"""
    pass

class TenantUnauthorizedError(Exception):
    """Exception raised when tenant is not authorized"""
    pass

class TenantConfigurationError(Exception):
    """Cannot initialize TenantConfigurationService, API_KEY for the service is not provided"""
    pass

class TenantConfigService:
    def __init__(self):
            self._default_settings = Settings()
            self._tenant_configs: dict[str, TenantConfig] = {}

            # CHANGE: Updated to use new environment variables
            self._tenant_config_url = self._default_settings.TENANT_CONFIG_URL
            self._config_service_api_key = self._default_settings.TENANT_API_KEY
            self._default_tenant_id = self._default_settings.DEFAULT_TENANT_ID
            self._tenant_config_file = self._default_settings.TENANT_CONFIG_FILE
            self._tenant_default_username = self._default_settings.TENANT_DEFAULT_USERNAME
            self._tenant_default_password = self._default_settings.TENANT_DEFAULT_PASSWORD
            self._tenant_default_hostname = self._default_settings.TENANT_DEFAULT_HOSTNAME
            self._tenant_default_store_type = self._default_settings.STORE_TYPE

            # CHANGE: Remove default config creation and storage, only load from file
            self._load_tenant_configs_from_file()

    def _load_tenant_configs_from_file(self):
        """Load tenant configurations from file if present"""
        if not self._tenant_config_file:
            logger.info("No tenant config file specified")
            return

        try:
            with open(self._tenant_config_file) as f:
                config = yaml.safe_load(f)
            tenants = config.get("tenants", {})
            logger.info(f"Loading configurations for {len(tenants)} tenants: {list(tenants.keys())}")

            # CHANGE: set_tenant_config now handles merging for file configs too
            for tenant_id in tenants.keys():
                try:
                    self.set_tenant_config(tenant_id, tenants[tenant_id])
                    logger.info(f"Loaded and merged config for tenant: {tenant_id}")
                except Exception as e:
                    logger.error(f"Failed to load tenant '{tenant_id}': {e}")
        except Exception as e:
            logger.error(f"Failed to load tenant configuration from {self._tenant_config_file}: {e}")
            logger.error(f"Defaulting to default config for tenant {self._default_settings.DEFAULT_TENANT_ID}")
            self.set_tenant_config(
                self._default_settings.DEFAULT_TENANT_ID,
                {
                    "store_type": self._default_settings.STORE_TYPE,
                    "hostname": self._default_settings.TENANT_DEFAULT_HOSTNAME,
                    "username": self._default_settings.TENANT_DEFAULT_USERNAME,
                    "password": self._default_settings.TENANT_DEFAULT_PASSWORD
                })


    async def _fetch_config_from_service(self, tenant_id: str) -> TenantConfig | None:
        """
        Fetch tenant configuration from remote config service.

        Args:
            tenant_id: The tenant identifier

        Returns:
            TenantConfig object if successful, None if not found

        Raises:
            TenantConfigNotFoundException: If service is unavailable or returns invalid data
        """
        # CHANGE: Updated URL to use TENANT_CONFIG_URL
        try:
            headers = {}
            if self._config_service_api_key:
                headers['X-API-Key'] = self._config_service_api_key

            async with aiohttp.ClientSession() as session:
                url = f"{self._tenant_config_url}/api/v1/credentials/{tenant_id}"
                logger.info(f"Fetching tenant config from: {url}")

                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 404:
                        error_text = await response.text()
                        raise TenantConfigNotFoundError(f"Config service error: {error_text}")
                    elif response.status == 401:
                        raise TenantUnauthorizedError(f"Unauthorized - Invalid or missing API key for tenant {tenant_id}")
                    elif response.status == 403:
                        raise TenantUnauthorizedError(f"Forbidden - API key does not have access to tenant {tenant_id}")
                    elif response.status != 200:
                        raise TenantConfigNotFoundError(f"Config service returned status {response.status} for tenant {tenant_id}")

                    data = await response.json()
                    if not data:
                        raise TenantConfigNotFoundError(f"Config service returned empty data for tenant {tenant_id}")

                    logger.info(f"Successfully fetched config for tenant: {tenant_id}")

                    # Return basic config with hostname only (other fields will be merged later)
                    config_data = {
                        'hostname': data.get('host'),
                        'tenant_id': tenant_id,
                        'store_type': self._tenant_default_store_type
                    }
                    print(f"=========={config_data}")
                    if not config_data.get('hostname'):
                        raise TenantConfigNotFoundError(f"No hostname received from config service for tenant {tenant_id}")

                    return TenantConfig(**{k: v for k, v in config_data.items() if v is not None})

        except TimeoutError as e:
            raise TenantConfigNotFoundError(f"Timeout while fetching config for tenant {tenant_id}") from e
        except aiohttp.ClientError as e:
            raise TenantConfigNotFoundError(f"Network error while fetching config for tenant {tenant_id}: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching config for tenant {tenant_id}: {e}")
            raise TenantConfigNotFoundError(f"Failed to fetch config for tenant {tenant_id}: {e}") from e


    async def get_tenant_config(self, tenant_id: str | None = None) -> TenantConfig:
        """
        Get tenant configuration from cache or fetch from remote service.
        """
        # Handle None tenant_id by using default tenant ID
        if tenant_id is None:
            if not self._default_tenant_id:
                raise TenantConfigNotFoundError("No default tenant ID configured")

            tenant_id = self._default_tenant_id
            if tenant_id in self._tenant_configs:
                return self._tenant_configs[tenant_id]
            else:
                raise TenantConfigNotFoundError(f"Default tenant '{tenant_id}' not found in cache")

        # Return cached config if found
        if tenant_id in self._tenant_configs:
            return self._tenant_configs[tenant_id]

        # If not in cache, try to fetch from remote service
        if self._tenant_config_url:
            if self._tenant_config_url == "DEFAULT":
                if self._default_tenant_id in self._tenant_configs:
                    tenant_config = self._tenant_configs[self._default_tenant_id].model_copy(
                        update={'tenant_id': tenant_id}
                    )
                    self._tenant_configs[tenant_id] = tenant_config
                    return tenant_config
                else:
                    raise TenantConfigNotFoundError(f"Default tenant for '{tenant_id}' not found in cache")

            logger.info(f"Tenant {tenant_id} not found in cache, fetching from remote service")
            remote_config = None
            try:
                remote_config = await self._fetch_config_from_service(tenant_id)
            except TenantConfigNotFoundError:
                if self._tenant_default_hostname:
                    logger.info(f"_fetch_config_from_service for {tenant_id} failed - but reverting to TENANT_DEFAULT_HOSTNAME")
                    config_data = {
                        'hostname': self._tenant_default_hostname,
                        'tenant_id': tenant_id,
                        'store_type': self._tenant_default_store_type
                    }
                    remote_config = TenantConfig(**{k: v for k, v in config_data.items() if v is not None})
                else:
                    logger.info(f"_fetch_config_from_service for {tenant_id} failed and there is no TENANT_DEFAULT_HOSTNAME - failing!")


            if remote_config is not None:
                # set_tenant_config for consistent merging and storage
                return self.set_tenant_config(tenant_id, remote_config.model_dump())
            else:
                raise TenantConfigNotFoundError(f"Tenant '{tenant_id}' not found in remote service")
        else:
            # No remote service configured, fail
            raise TenantConfigNotFoundError(f"Tenant '{tenant_id}' not found in cache and no remote service configured")

    def set_tenant_config(self, tenant_id: str, config_dict: dict[str, Any]) -> TenantConfig:
        """
        Set tenant configuration from a dictionary with environment defaults merging.
        Used for ALL config sources: YAML file, remote service, manual setting.

        Args:
            tenant_id: The tenant identifier
            config_dict: Raw configuration dictionary from any source

        Returns:
            TenantConfig object with merged configuration
        """
        merged_config = config_dict.copy()

        # Always set tenant_id
        merged_config['tenant_id'] = tenant_id

        # Merge authentication credentials
        if 'username' not in merged_config or merged_config['username'] is None:
            merged_config['username'] = self._tenant_default_username

        if 'password' not in merged_config or merged_config['password'] is None:
            merged_config['password'] = self._tenant_default_password

        # Merge Jaeger settings
        if 'jaeger_url' not in merged_config or merged_config['jaeger_url'] is None:
            merged_config['jaeger_url'] = self._default_settings.JAEGER_URL

        if 'jaeger_collect_url' not in merged_config or merged_config['jaeger_collect_url'] is None:
            merged_config['jaeger_collect_url'] = self._default_settings.JAEGER_COLLECT_URL

        # Merge database settings
        if 'database_name' not in merged_config or merged_config['database_name'] is None:
            merged_config['database_name'] = f"{self._default_settings.DATABASE_NAME}_{tenant_id}"

        if 'store_type' not in merged_config or merged_config['store_type'] is None:
            merged_config['store_type'] = StoreType(self._default_settings.STORE_TYPE.lower())

        # Merge connection string for MongoDB
        if 'connection_str' not in merged_config or merged_config['connection_str'] is None:
            # Only set connection_str if store_type is mongodb
            store_type = merged_config.get('store_type', self._default_settings.STORE_TYPE.lower())
            if store_type == StoreType.MONGODB:
                merged_config['connection_str'] = self._default_settings.CONNECTION_STR

        # Merge additional_config with collection names and other settings
        additional_config = merged_config.get('additional_config', {})

        # Add collection names if not present
        if 'analytics_collection' not in additional_config:
            additional_config['analytics_collection'] = self._default_settings.ANALYTICS_COLLECTION_NAME

        if 'executor_results_collection' not in additional_config:
            additional_config['executor_results_collection'] = self._default_settings.EXECUTOR_RESULTS_COLLECTION_NAME

        if 'data_artifacts_collection' not in additional_config:
            additional_config['data_artifacts_collection'] = self._default_settings.DATA_ARTIFACTS_COLLECTION_NAME

        merged_config['additional_config'] = additional_config

        # Create and store the tenant config
        try:
            tenant_config = TenantConfig(**merged_config)
            self._tenant_configs[tenant_id] = tenant_config
            logger.info(f"Successfully set configuration for tenant: {tenant_id}")
            return tenant_config
        except Exception as e:
            logger.error(f"Error creating tenant config for {tenant_id}: {e}")
            raise ValueError(f"Invalid configuration provided for tenant {tenant_id}: {e}") from e






    def _get_default_tenant_id(self) -> str:
        """Return the default tenant ID."""
        return self._default_settings.DEFAULT_TENANT_ID

    def list_tenant_configs(self) -> dict[str, dict[str, Any]]:
        """
        List all tenant configurations.

        Returns:
            Dictionary mapping tenant_id to configuration dict
        """
        return {
            tenant_id: config.model_dump()
            for tenant_id, config in self._tenant_configs.items()
        }

tenant_config_service = TenantConfigService()
