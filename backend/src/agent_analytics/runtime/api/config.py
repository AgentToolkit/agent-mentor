# api/config.py
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional

import os
from dotenv import load_dotenv
load_dotenv()

class Settings(BaseSettings):
    # Default database settings (used as fallback)
    CONNECTION_STR: str = Field(default="mongodb://localhost:27017", env="CONNECTION_STR")
    DATABASE_NAME: str = "analytics_db"
    ANALYTICS_COLLECTION_NAME: str = "analytics_metadata"
    EXECUTOR_RESULTS_COLLECTION_NAME: str = "execution_results"
    DATA_ARTIFACTS_COLLECTION_NAME: str = "analytics_artifacts"
    ENV_NAME: str = "dev"
    
    #Tenant config service
    TENANT_CONFIG_URL: Optional[str] = Field(default=None, env="TENANT_CONFIG_URL")
    TENANT_API_KEY: Optional[str] = Field(default=None, env="TENANT_API_KEY")
    TENANT_CONFIG_FILE: Optional[str] = Field(default=None, env="TENANT_CONFIG_FILE")
    TENANT_DEFAULT_USERNAME: Optional[str] = Field(default=None, env="TENANT_DEFAULT_USERNAME")
    TENANT_DEFAULT_PASSWORD: Optional[str] = Field(default=None, env="TENANT_DEFAULT_PASSWORD")
    TENANT_DEFAULT_HOSTNAME: Optional[str] = Field(default=None, env="TENANT_DEFAULT_HOSTNAME")

    # Jaeger settings
    JAEGER_URL: str = Field(
        default="https://jaeger-query-ui-agent-analytics-jaeger.agent-analytics-9ca4d14d48413d18ce61b80811ba4308-0000.us-south.containers.appdomain.cloud",
        env="JAEGER_URL"
    )

    JAEGER_COLLECT_URL: str = Field(
        default="http://jaeger-collector.agent-analytics-jaeger.svc.cluster.local:4318/v1/traces",
        env="JAEGER_COLLECT_URL"
    )
    
    DEFAULT_TENANT_ID: str = Field(
        default=None,
        env="DEFAULT_TENANT_ID",
        description="Default tenant ID to use when no tenant is specified"
    )
    
    # Store type configuration
    STORE_TYPE: str = Field(
        default="elasticsearch",
        env="STORE_TYPE",
        description="Type of data store: mongodb, elasticsearch, or opensearch"
    )
    
    # Elasticsearch settings
    ES_HOST: str = Field(default="localhost:9200", env="ES_HOST")
    ES_USERNAME: str = Field(default="elastic", env="ES_USERNAME")
    ES_PASSWORD: str = Field(default="password", env="ES_PASSWORD")
    
    # OpenSearch settings
    OS_HOST: str = Field(default="localhost:9200", env="OS_HOST")
    OS_USERNAME: str = Field(default="admin", env="OS_USERNAME")
    OS_PASSWORD: str = Field(default="admin", env="OS_PASSWORD")

    #Logging settings
    LOG_USER: bool = Field(default=False, env="LOG_USER")
    
    class Config:
        extra = "allow"
        env_file = ".env"
    
        
settings = Settings()
