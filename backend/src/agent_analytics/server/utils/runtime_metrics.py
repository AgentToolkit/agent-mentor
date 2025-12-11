
from datetime import datetime
from typing import Any

from elasticsearch import AsyncElasticsearch
from opensearchpy import AsyncOpenSearch
from pydantic import BaseModel

from agent_analytics.runtime.api import TenantComponents


class DurationStats(BaseModel):
    count: int
    min: float | None
    max: float | None
    avg: float | None
    sum: float | None


class UniqueTracesResponse(BaseModel):
    unique_traces: int


class FailedTracesResponse(BaseModel):
    failed_traces: int


class DurationStatsResponse(BaseModel):
    duration_stats: DurationStats


class OverallMetricsResponse(BaseModel):
    unique_traces: int
    failed_traces: int
    duration_stats: DurationStats


class AgentMetric(BaseModel):
    agent_id: str
    unique_traces: int | None = None
    failed_traces: int | None = None
    duration_stats: DurationStats | None = None


class AgentUniqueTracesResponse(BaseModel):
    agents: list[AgentMetric]


class AgentFailedTracesResponse(BaseModel):
    agents: list[AgentMetric]


class AgentDurationStatsResponse(BaseModel):
    agents: list[AgentMetric]


class TraceInfo(BaseModel):
    trace_id: str
    start_time: str


class TracesResponse(BaseModel):
    traces: list[TraceInfo]


def _convert_to_millis(timestamp: str | datetime | int) -> int:
    """Convert timestamp to milliseconds"""
    if isinstance(timestamp, str):
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return int(dt.timestamp() * 1000)
    elif isinstance(timestamp, datetime):
        return int(timestamp.timestamp() * 1000)
    return timestamp


async def _get_db_client(tenant_components: TenantComponents) -> Any:
    """Create Elasticsearch client from tenant config"""
    if tenant_components and tenant_components.db_client:
        if not isinstance(tenant_components.db_client, (AsyncElasticsearch, AsyncOpenSearch)):
            raise TypeError(
                f"Expected AsyncElasticsearch or AsyncOpenSearch, "
                f"but got {type(tenant_components.db_client).__name__}"
            )
        return tenant_components.db_client

    else:
        raise ValueError("Tenant db client is None")

def _get_failed_traces_filter() -> dict:
    """Create filter for failed traces using structured issue_type field"""
    return {
        "nested": {
            "path": "logs",
            "query": {
                "nested": {
                    "path": "logs.fields",
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"logs.fields.key": "issue_type"}},
                                {"term": {"logs.fields.value": "Issue"}}
                            ]
                        }
                    }
                }
            }
        }
    }

def _get_tenant_filter(tenant_id: str) -> dict:
    """Create tenant filter that matches tenant ID in either tags or process.tags"""
    return {
        "bool": {
            "should": [
                {
                    "nested": {
                        "path": "tags",
                        "query": {
                            "bool": {
                                "must": [
                                    {"term": {"tags.key": "tenant.id"}},
                                    {"term": {"tags.value": tenant_id}}
                                ]
                            }
                        }
                    }
                },
                {
                    "nested": {
                        "path": "process.tags",
                        "query": {
                            "bool": {
                                "must": [
                                    {"term": {"process.tags.key": "tenant.id"}},
                                    {"term": {"process.tags.value": tenant_id}}
                                ]
                            }
                        }
                    }
                }
            ]
        }
    }


### GLOBAL QUERIES
async def get_num_unique_traces(
    tenant_id: str,
    tenant_components: TenantComponents,
    service_name: str,
    start_time: str | datetime,
    end_time: str | datetime
) -> UniqueTracesResponse:
    """Count unique traces for a service within time range"""
    db_client = await _get_db_client(tenant_components)

    start_millis = _convert_to_millis(start_time)
    end_millis = _convert_to_millis(end_time)

    query = {
        "size": 0,
        "query": {
            "bool": {
                "must": [
                    {"term": {"process.serviceName": service_name}},
                    {"range": {"startTimeMillis": {"gte": start_millis, "lte": end_millis}}},
                    _get_tenant_filter(tenant_id)
                ]
            }
        },
        "aggs": {
            "unique_traces": {
                "cardinality": {"field": "traceID"}
            }
        }
    }

    response = await db_client.search(index="*jaeger-span*", body=query)

    return UniqueTracesResponse(unique_traces=response['aggregations']['unique_traces']['value'])


async def get_num_failed_traces(
    tenant_id: str,
    tenant_components: TenantComponents,
    service_name: str,
    start_time: str | datetime,
    end_time: str | datetime,
    included_severities: list[str] | None = None
) -> FailedTracesResponse:
    """Count unique traces with issues (failed traces)"""
    db_client = await _get_db_client(tenant_components)

    start_millis = _convert_to_millis(start_time)
    end_millis = _convert_to_millis(end_time)

    query = {
        "size": 0,
        "query": {
            "bool": {
                "must": [
                    {"term": {"process.serviceName": service_name}},
                    {"range": {"startTimeMillis": {"gte": start_millis, "lte": end_millis}}},
                    _get_tenant_filter(tenant_id),
                    _get_failed_traces_filter()
                ]
            }
        },
        "aggs": {
            "failed_traces": {
                "cardinality": {"field": "traceID"}
            }
        }
    }

    response = await db_client.search(index="*jaeger-span*", body=query)

    return FailedTracesResponse(failed_traces=response['aggregations']['failed_traces']['value'])


async def get_duration_stats(
    tenant_id: str,
    tenant_components: TenantComponents,
    service_name: str,
    start_time: str | datetime,
    end_time: str | datetime
) -> DurationStatsResponse:
    """Compute average trace duration (root spans only)"""
    db_client = await _get_db_client(tenant_components)

    start_millis = _convert_to_millis(start_time)
    end_millis = _convert_to_millis(end_time)

    query = {
        "size": 0,
        "query": {
            "bool": {
                "must": [
                    {"term": {"process.serviceName": service_name}},
                    {"range": {"startTimeMillis": {"gte": start_millis, "lte": end_millis}}},
                    _get_tenant_filter(tenant_id)
                ]
            }
        },
        "aggs": {
            "traces": {
                "terms": {
                    "field": "traceID",
                    "size": 10000,
                    "execution_hint": "map"
                },
                "aggs": {
                    "min_start": {
                        "min": {"field": "startTimeMillis"}
                    },
                    "max_end": {
                        "max": {
                            "script": {
                                "source": "doc['startTimeMillis'].value.millis + doc['duration'].value"
                            }
                        }
                    },
                    "trace_duration": {
                        "bucket_script": {
                            "buckets_path": {"minStart": "min_start", "maxEnd": "max_end"},
                            "script": "params.maxEnd - params.minStart"
                        }
                    }
                }
            },
            "duration_stats": {
                "stats_bucket": {
                    "buckets_path": "traces>trace_duration"
                }
            }
        }
    }

    response = await db_client.search(index="*jaeger-span*", body=query)

    stats = response['aggregations']['duration_stats']
    return DurationStatsResponse(
        duration_stats=DurationStats(
            count=stats['count'] or 0,
            min=stats['min'] / 1000 if stats['min'] else 0,
            max=stats['max'] / 1000 if stats['max'] else 0,
            avg=stats['avg'] / 1000 if stats['avg'] else 0,
            sum=stats['sum'] / 1000 if stats['sum'] else 0
        )
    )


async def get_overall_metrics_with_agent_filter(
    tenant_id: str,
    tenant_components: TenantComponents,
    service_name: str,
    start_time: str | datetime | None = None,
    end_time: str | datetime | None = None,
    agent_ids: list[str] | None = None
) -> OverallMetricsResponse:
    """
    Get all three metrics (unique traces, failed traces, duration stats) in a single query.

    Args:
        agent_ids: If None or empty list, filters for traces that have the agent.id tag.
                   If provided, filters for traces with those specific agent IDs.
    """
    db_client = await _get_db_client(tenant_components)

    start_millis = _convert_to_millis(start_time)
    end_millis = _convert_to_millis(end_time)

    # Build the base query filters
    must_filters = [
        {"term": {"process.serviceName": service_name}},
        {"range": {"startTimeMillis": {"gte": start_millis, "lte": end_millis}}},
        _get_tenant_filter(tenant_id)
    ]

    # Add agent filtering
    if agent_ids is None or len(agent_ids) == 0:
        # Filter for traces that have the agent.id tag (any value)
        must_filters.append({
            "nested": {
                "path": "tags",
                "query": {
                    "term": {"tags.key": "agent.id"}
                }
            }
        })
    else:
        # Filter for traces with specific agent IDs
        must_filters.append({
            "nested": {
                "path": "tags",
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"tags.key": "agent.id"}},
                            {"terms": {"tags.value": agent_ids}}
                        ]
                    }
                }
            }
        })

    query = {
        "size": 0,
        "query": {
            "bool": {
                "must": must_filters
            }
        },
        "aggs": {
            # Aggregation 1: Count unique traces
            "unique_traces": {
                "cardinality": {"field": "traceID"}
            },
            # Aggregation 2: Count failed traces
            "failed_traces_filter": {
                "filter": _get_failed_traces_filter(),
                "aggs": {
                    "failed_traces": {
                        "cardinality": {"field": "traceID"}
                    }
                }
            },
            # Aggregation 3: Duration stats
            "traces": {
                "terms": {
                    "field": "traceID",
                    "size": 10000,
                    "execution_hint": "map"
                },
                "aggs": {
                    "min_start": {
                        "min": {"field": "startTimeMillis"}
                    },
                    "max_end": {
                        "max": {
                            "script": {
                                "source": "doc['startTimeMillis'].value.millis + doc['duration'].value"
                            }
                        }
                    },
                    "trace_duration": {
                        "bucket_script": {
                            "buckets_path": {"minStart": "min_start", "maxEnd": "max_end"},
                            "script": "params.maxEnd - params.minStart"
                        }
                    }
                }
            },
            "duration_stats": {
                "stats_bucket": {
                    "buckets_path": "traces>trace_duration"
                }
            }
        }
    }

    response = await db_client.search(index="*jaeger-span*", body=query)

    # Extract results
    unique_traces_count = response['aggregations']['unique_traces']['value']
    failed_traces_count = response['aggregations']['failed_traces_filter']['failed_traces']['value']
    stats = response['aggregations']['duration_stats']

    return OverallMetricsResponse(
        unique_traces=unique_traces_count,
        failed_traces=failed_traces_count,
        duration_stats=DurationStats(
            count=stats['count'] or 0,
            min=stats['min'] / 1000 if stats['min'] else 0,
            max=stats['max'] / 1000 if stats['max'] else 0,
            avg=stats['avg'] / 1000 if stats['avg'] else 0,
            sum=stats['sum'] / 1000 if stats['sum'] else 0
        )
    )


### AGENT SPECIFIC QUERIES
async def get_num_unique_traces_for_agents(
    tenant_id: str,
    tenant_components: TenantComponents,
    agent_ids: list[str],
    service_name: str,
    start_time: str | datetime,
    end_time: str | datetime
) -> AgentUniqueTracesResponse:
    """Count unique traces per agent"""
    db_client = await _get_db_client(tenant_components)

    start_millis = _convert_to_millis(start_time)
    end_millis = _convert_to_millis(end_time)

    query = {
        "size": 0,
        "query": {
            "bool": {
                "must": [
                    {"term": {"process.serviceName": service_name}},
                    {"range": {"startTimeMillis": {"gte": start_millis, "lte": end_millis}}},
                    _get_tenant_filter(tenant_id),
                    {
                        "nested": {
                            "path": "tags",
                            "query": {
                                "bool": {
                                    "must": [
                                        {"term": {"tags.key": "agent.id"}},
                                        {"terms": {"tags.value": agent_ids}}
                                    ]
                                }
                            }
                        }
                    }
                ]
            }
        },
        "aggs": {
            "agents": {
                "nested": {"path": "tags"},
                "aggs": {
                    "agent_filter": {
                        "filter": {"term": {"tags.key": "agent.id"}},
                        "aggs": {
                            "agent_values": {
                                "terms": {"field": "tags.value", "include": agent_ids},
                                "aggs": {
                                    "unique_traces": {
                                        "reverse_nested": {},
                                        "aggs": {
                                            "trace_count": {"cardinality": {"field": "traceID"}}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    response = await db_client.search(index="*jaeger-span*", body=query)

    agents = []
    agent_buckets = response['aggregations']['agents']['agent_filter']['agent_values']['buckets']

    for bucket in agent_buckets:
        agents.append(AgentMetric(
            agent_id=bucket['key'],
            unique_traces=bucket['unique_traces']['trace_count']['value']
        ))

    return AgentUniqueTracesResponse(agents=agents)


async def get_num_failed_traces_for_agents(
    tenant_id: str,
    tenant_components: TenantComponents,
    agent_ids: list[str],
    service_name: str,
    start_time: str | datetime,
    end_time: str | datetime,
    included_severities: list[str] | None = None
) -> AgentFailedTracesResponse:
    """Count failed traces per agent"""
    db_client = await _get_db_client(tenant_components)

    start_millis = _convert_to_millis(start_time)
    end_millis = _convert_to_millis(end_time)

    query = {
        "size": 0,
        "query": {
            "bool": {
                "must": [
                    {"term": {"process.serviceName": service_name}},
                    {"range": {"startTimeMillis": {"gte": start_millis, "lte": end_millis}}},
                    _get_tenant_filter(tenant_id),
                    {
                        "nested": {
                            "path": "tags",
                            "query": {
                                "bool": {
                                    "must": [
                                        {"term": {"tags.key": "agent.id"}},
                                        {"terms": {"tags.value": agent_ids}}
                                    ]
                                }
                            }
                        }
                    },
                    _get_failed_traces_filter()
                ]
            }
        },
        "aggs": {
            "agents": {
                "nested": {"path": "tags"},
                "aggs": {
                    "agent_filter": {
                        "filter": {"term": {"tags.key": "agent.id"}},
                        "aggs": {
                            "agent_values": {
                                "terms": {"field": "tags.value", "include": agent_ids},
                                "aggs": {
                                    "failed_traces": {
                                        "reverse_nested": {},
                                        "aggs": {
                                            "trace_count": {"cardinality": {"field": "traceID"}}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    response = await db_client.search(index="*jaeger-span*", body=query)


    agents = []
    agent_buckets = response['aggregations']['agents']['agent_filter']['agent_values']['buckets']

    for bucket in agent_buckets:
        agents.append(AgentMetric(
            agent_id=bucket['key'],
            failed_traces=bucket['failed_traces']['trace_count']['value']
        ))

    return AgentFailedTracesResponse(agents=agents)


async def get_duration_stats_for_agents(
    tenant_id: str,
    tenant_components: TenantComponents,
    agent_ids: list[str],
    service_name: str,
    start_time: str | datetime,
    end_time: str | datetime
) -> AgentDurationStatsResponse:
    """Calculate average trace duration per agent (two-step process)"""
    db_client = await _get_db_client(tenant_components)

    start_millis = _convert_to_millis(start_time)
    end_millis = _convert_to_millis(end_time)

    agents = []

    # Process each agent separately (following the shell script's approach)
    for agent_id in agent_ids:
        # Step 1: Get trace IDs for this agent
        trace_query = {
            "size": 0,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"process.serviceName": service_name}},
                        {"range": {"startTimeMillis": {"gte": start_millis, "lte": end_millis}}},
                        _get_tenant_filter(tenant_id),
                        {
                            "nested": {
                                "path": "tags",
                                "query": {
                                    "bool": {
                                        "must": [
                                            {"term": {"tags.key": "agent.id"}},
                                            {"term": {"tags.value": agent_id}}
                                        ]
                                    }
                                }
                            }
                        }
                    ]
                }
            },
            "aggs": {
                "trace_ids": {
                    "terms": {"field": "traceID", "size": 10000}
                }
            }
        }

        trace_response = await db_client.search(index="*jaeger-span*", body=trace_query)
        trace_buckets = trace_response['aggregations']['trace_ids']['buckets']

        if not trace_buckets:
            agents.append(AgentMetric(
                agent_id=agent_id,
                duration_stats=DurationStats(count=0, min=None, max=None, avg=None, sum=None)
            ))
            continue

        trace_ids = [bucket['key'] for bucket in trace_buckets]

        # Step 2: Get duration stats for root spans of these traces
        duration_query = {
            "size": 0,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"process.serviceName": service_name}},
                        {"range": {"startTimeMillis": {"gte": start_millis, "lte": end_millis}}},
                        _get_tenant_filter(tenant_id),
                        {"terms": {"traceID": trace_ids}}
                    ]
                }
            },
            "aggs": {
                "traces": {
                    "terms": {
                        "field": "traceID",
                        "size": 1000,
                        "execution_hint": "map"
                    },
                    "aggs": {
                        "min_start": {
                            "min": {"field": "startTimeMillis"}
                        },
                        "max_end": {
                            "max": {
                                "script": {
                                    "source": "doc['startTimeMillis'].value.millis + doc['duration'].value"
                                }
                            }
                        },
                        "trace_duration": {
                            "bucket_script": {
                                "buckets_path": {"minStart": "min_start", "maxEnd": "max_end"},
                                "script": "params.maxEnd - params.minStart"
                            }
                        }
                    }
                },
                "duration_stats": {
                    "stats_bucket": {
                        "buckets_path": "traces>trace_duration"
                    }
                }
            }
        }

        duration_response = await db_client.search(index="*jaeger-span*", body=duration_query)
        stats = duration_response['aggregations']['duration_stats']

        agents.append(AgentMetric(
            agent_id=agent_id,
            duration_stats=DurationStats(
                count=stats['count'],
                min=stats['min'] / 1000 if stats['min'] else 0,
                max=stats['max'] / 1000 if stats['max'] else 0,
                avg=stats['avg'] / 1000 if stats['avg'] else 0,
                sum=stats['sum'] / 1000 if stats['sum'] else 0
            )
        ))


    return AgentDurationStatsResponse(agents=agents)


############################

### FETCH TRACES
async def get_traces_for_agent(
    tenant_id: str,
    tenant_components: TenantComponents,
    agent_id: str,
    service_name: str,
    start_time: str | datetime,
    end_time: str | datetime
) -> TracesResponse:
    """Fetch traces for a specific agent"""
    db_client = await _get_db_client(tenant_components)

    start_millis = _convert_to_millis(start_time)
    end_millis = _convert_to_millis(end_time)

    # First, get unique trace IDs for this agent
    trace_ids_query = {
        "size": 0,
        "query": {
            "bool": {
                "must": [
                    {"term": {"process.serviceName": service_name}},
                    {"range": {"startTimeMillis": {"gte": start_millis, "lte": end_millis}}},
                    _get_tenant_filter(tenant_id),
                    {
                        "nested": {
                            "path": "tags",
                            "query": {
                                "bool": {
                                    "must": [
                                        {"term": {"tags.key": "agent.id"}},
                                        {"term": {"tags.value": agent_id}}
                                    ]
                                }
                            }
                        }
                    }
                ]
            }
        },
        "aggs": {
            "unique_traces": {
                "terms": {
                    "field": "traceID",
                    "size": 10000
                },
                "aggs": {
                    "earliest_span": {
                        "top_hits": {
                            "sort": [{"startTime": {"order": "asc"}}],
                            "size": 1,
                            "_source": ["traceID", "startTime"]
                        }
                    }
                }
            }
        }
    }

    response = await db_client.search(index="*jaeger-span*", body=trace_ids_query)


    traces = []
    trace_buckets = response['aggregations']['unique_traces']['buckets']

    for bucket in trace_buckets:
        trace_id = bucket['key']
        earliest_span = bucket['earliest_span']['hits']['hits'][0]['_source']

        # Convert startTime from microseconds to ISO format
        start_time_micros = earliest_span['startTime']
        start_time_seconds = start_time_micros / 1_000_000
        start_time_dt = datetime.fromtimestamp(start_time_seconds)
        start_time_iso = start_time_dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

        traces.append(TraceInfo(
            trace_id=trace_id,
            start_time=start_time_iso
        ))

    # Sort traces by start time (most recent first)
    traces.sort(key=lambda x: x.start_time, reverse=True)

    return TracesResponse(traces=traces)
