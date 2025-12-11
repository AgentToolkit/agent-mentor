from typing import cast

from elasticsearch import AsyncElasticsearch
from opensearchpy import AsyncOpenSearch

from agent_analytics.runtime.api.dependencies import get_default_db_client

# Mapping for user_actions index
USER_ACTIONS_MAPPING = {
    "mappings": {
        "properties": {
            "timestamp": {"type": "date"},
            "username": {"type": "keyword"},
            "action": {"type": "keyword"},
            "element": {"type": "keyword"},
            "response_time_ms": {"type": "float"},
            "status_code": {"type": "integer"},
            "success": {"type": "boolean"},
            "error_message": {"type": "text"},
            "payload_size": {"type": "integer"},
            "action_metadata": {"type": "object"},
            "ip_address": {"type": "ip"},
            "user_agent": {"type": "text"}
        }
    }
}

# Mapping for login_events index
LOGIN_EVENTS_MAPPING = {
    "mappings": {
        "properties": {
            "timestamp": {"type": "date"},
            "username": {"type": "keyword"},
            "email": {"type": "keyword"},
            "full_name": {"type": "text"},
            "ip_address": {"type": "ip"}
        }
    }
}

async def init_indices():
    """Initialize Elasticsearch indices with proper mappings"""
    indices = {
        'user_actions': USER_ACTIONS_MAPPING,
        'login_events': LOGIN_EVENTS_MAPPING
    }

    client = await get_default_db_client()
    if isinstance(client, AsyncOpenSearch):
        client = cast(AsyncOpenSearch, client)
    else:
        client = cast(AsyncElasticsearch, client)

    for index_name, mapping in indices.items():
        if not await client.indices.exists(index=index_name):
            await client.indices.create(
                index=index_name,
                body=mapping
            )

async def init_db():
    """Initialize database and required indices"""
    await init_indices()
