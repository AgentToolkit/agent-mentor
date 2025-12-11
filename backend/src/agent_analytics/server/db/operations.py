from datetime import UTC, datetime
from typing import Any, cast

from elasticsearch import AsyncElasticsearch
from opensearchpy import AsyncOpenSearch
from pydantic import BaseModel

from agent_analytics.runtime.api.dependencies import get_default_db_client
from agent_analytics.runtime.api.config import Settings




class UserActionRecord(BaseModel):
    timestamp: datetime
    username: str
    action: str
    element: str
    response_time_ms: float
    status_code: int
    success: bool
    error_message: str | None
    payload_size: int | None
    action_metadata: dict[str, Any] | None
    ip_address: str
    user_agent: str

    def to_es_doc(self) -> dict:
        return self.model_dump()

class LoginRecord(BaseModel):
    username: str
    email: str | None
    full_name: str | None
    ip_address: str | None
    timestamp: datetime

    def to_es_doc(self) -> dict:
        return self.model_dump()

class UsageTracker:
    @staticmethod
    async def log_action(
        username: str,
        action: str,
        element: str,
        response_time_ms: float,
        status_code: int,
        success: bool,
        ip_address: str,
        user_agent: str,
        error_message: str | None = None,
        payload_size: int | None = None,
        metadata: dict | None = None
    ):
        if not Settings().LOG_USER:
            return
        
        action_record = UserActionRecord(
            timestamp=datetime.now(UTC),
            username=username,
            action=action,
            element=element,
            response_time_ms=response_time_ms,
            status_code=status_code,
            success=success,
            error_message=error_message,
            payload_size=payload_size,
            action_metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent
        )

        client = await get_default_db_client()
        if isinstance(client, AsyncOpenSearch):
            client = cast(AsyncOpenSearch, client)
            await client.index(
                index='user_actions',
                body=action_record.to_es_doc()
            )
        else:
            client = cast(AsyncElasticsearch, client)
            await client.index(
                index='user_actions',
                document=action_record.to_es_doc()
            )

    @staticmethod
    async def get_user_usage(username: str, days: int = 30):
        """Get usage statistics for a specific user"""
        if not Settings().LOG_USER:
            return []
        
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"username": username}},
                        {"range": {
                            "timestamp": {
                                "gte": f"now-{days}d/d"
                            }
                        }}
                    ]
                }
            },
            "sort": [{"timestamp": "desc"}]
        }

        client = await get_default_db_client()
        if isinstance(client, AsyncOpenSearch):
            client = cast(AsyncOpenSearch, client)
        else:
            client = cast(AsyncElasticsearch, client)

        result = await client.search(
            index="user_actions",
            body=query,
            # size=1000  # Adjust based on needs
        )

        return [UserActionRecord(**hit['_source']) for hit in result['hits']['hits']]

    @staticmethod
    async def get_action_stats(days: int = 30):
        if not Settings().LOG_USER:
            return []
        
        """Get aggregated statistics for all actions"""

        query = {
            "size": 0,
            "query": {
                "range": {
                    "timestamp": {
                        "gte": f"now-{days}d/d"
                    }
                }
            },
            "aggs": {
                "by_action": {
                    "terms": {
                        "field": "action.keyword",
                        "size": 100
                    },
                    "aggs": {
                        "avg_response_time": {
                            "avg": {
                                "field": "response_time_ms"
                            }
                        },
                        "successful_calls": {
                            "filter": {
                                "term": {
                                    "success": True
                                }
                            }
                        },
                        "avg_payload_size": {
                            "avg": {
                                "field": "payload_size"
                            }
                        }
                    }
                }
            }
        }

        client = await get_default_db_client()
        if isinstance(client, AsyncOpenSearch):
            client = cast(AsyncOpenSearch, client)
        else:
            client = cast(AsyncElasticsearch, client)
        result = await client.search(index="user_actions", body=query)

        stats = []
        for bucket in result["aggregations"]["by_action"]["buckets"]:
            stats.append({
                'action': bucket['key'],
                'total_calls': bucket['doc_count'],
                'avg_response_time': bucket['avg_response_time']['value'] if bucket['avg_response_time']['value'] is not None else 0,
                'successful_calls': bucket['successful_calls']['doc_count'],
                'avg_payload_size': bucket['avg_payload_size']['value'] if bucket['avg_payload_size']['value'] is not None else 0
            })

        return stats

    @staticmethod
    async def dump_recent_actions(days: int = 7) -> list[UserActionRecord]:
        """Dump all user actions from the past X days"""
        if not Settings().LOG_USER:
            return []

        query = {
            "query": {
                "range": {
                    "timestamp": {
                        "gte": f"now-{days}d/d"
                    }
                }
            },
            "sort": [
                {"timestamp": {"order": "desc"}}
            ],
            "size": 10000
        }

        client = await get_default_db_client()
        if isinstance(client, AsyncOpenSearch):
            client = cast(AsyncOpenSearch, client)
        else:
            client = cast(AsyncElasticsearch, client)
        result = await client.search(
            index="user_actions",
            body=query
        )

        return [
            UserActionRecord(
                **{
                    **hit['_source'],
                    'timestamp': datetime.fromisoformat(hit['_source']['timestamp'])
                        if isinstance(hit['_source']['timestamp'], str)
                        else hit['_source']['timestamp']
                }
            )
            for hit in result['hits']['hits']
        ]

class LoginTracker:
    @staticmethod
    async def log_login(
        username: str,
        email: str | None,
        full_name: str | None,
        ip_address: str | None
    ):
        """Log a new login event"""
        if not Settings().LOG_USER:
            return 
        
        login_record = LoginRecord(
            username=username,
            email=email,
            full_name=full_name,
            ip_address=ip_address,
            timestamp=datetime.now(UTC)
        )

        client = await get_default_db_client()
        if isinstance(client, AsyncOpenSearch):
            client = cast(AsyncOpenSearch, client)
            await client.index(
                index='login_events',
                body=login_record.to_es_doc()
            )
        else:
            client = cast(AsyncElasticsearch, client)
            await client.index(
                index='login_events',
                document=login_record.to_es_doc()
            )



    @staticmethod
    async def get_login_history(days: int = 7) -> list[LoginRecord]:
        if not Settings().LOG_USER:
            return []
        
        """Get login history for the past X days"""

        query = {
            "query": {
                "range": {
                    "timestamp": {
                        "gte": f"now-{days}d/d"
                    }
                }
            },
            "sort": [{"timestamp": "desc"}],
            "size": 1000
        }

        client = await get_default_db_client()
        if isinstance(client, AsyncOpenSearch):
            client = cast(AsyncOpenSearch, client)
        else:
            client = cast(AsyncElasticsearch, client)

        result = await client.search(
            index="login_events",
            body=query
        )

        return [
            LoginRecord(
                **{
                    **hit['_source'],
                    'timestamp': datetime.fromisoformat(hit['_source']['timestamp'])
                        if isinstance(hit['_source']['timestamp'], str)
                        else hit['_source']['timestamp']
                }
            )
            for hit in result['hits']['hits']
        ]

    @staticmethod
    async def get_user_logins(username: str) -> list[LoginRecord]:
        if not Settings().LOG_USER:
            return []
        
        """Get login history for a specific user"""

        query = {
            "query": {
                "match": {
                    "username": username
                }
            },
            "sort": [{"timestamp": "desc"}],
            "size": 1000
        }

        client = await get_default_db_client()
        if isinstance(client, AsyncOpenSearch):
            client = cast(AsyncOpenSearch, client)
        else:
            client = cast(AsyncElasticsearch, client)
        result = await client.search(
            index="login_events",
            body=query
        )

        return [
            LoginRecord(
                **{
                    **hit['_source'],
                    'timestamp': datetime.fromisoformat(hit['_source']['timestamp'])
                        if isinstance(hit['_source']['timestamp'], str)
                        else hit['_source']['timestamp']
                }
            )
            for hit in result['hits']['hits']
        ]
