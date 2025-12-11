"""
Admin queries for tenant-level statistics using ES/OS aggregations.
"""
import asyncio
import os
from datetime import datetime
from typing import Any

from elasticsearch import AsyncElasticsearch
from opensearchpy import AsyncOpenSearch

from agent_analytics.runtime.api import TenantComponents
from agent_analytics.runtime.api.initialization import get_index_name_for_artifact_type
from agent_analytics.core.data.issue_data import IssueData
from agent_analytics.core.data.task_data import TaskData

force_single_tenant = os.environ.get('FORCE_SINGLE_TENANT', "false").lower() == "true"


def _get_jaeger_span_indices(start_date: datetime, end_date: datetime) -> str:
    """
    Generate comma-separated list of Jaeger span index names for the date range.

    Jaeger indices follow the pattern: jaeger-span-YYYY-MM-DD
    Always includes 'jaeger-span' (without date suffix) for custom Jaeger logic.
    """
    from datetime import timedelta

    indices = ["jaeger-span"]  # Always include base index without date suffix

    current_date = start_date.date()
    end_date_only = end_date.date()

    while current_date <= end_date_only:
        index_name = f"jaeger-span-{current_date.strftime('%Y-%m-%d')}"
        indices.append(index_name)
        current_date += timedelta(days=1)

    return ",".join(indices)


async def _get_db_client(tenant_components: TenantComponents) -> Any:
    """Get Elasticsearch/OpenSearch client from tenant components"""
    if tenant_components and tenant_components.db_client:
        if not isinstance(tenant_components.db_client, (AsyncElasticsearch, AsyncOpenSearch)):
            raise TypeError(
                f"Expected AsyncElasticsearch or AsyncOpenSearch, "
                f"but got {type(tenant_components.db_client).__name__}"
            )
        return tenant_components.db_client
    else:
        raise ValueError("Tenant db client is None")


def _build_jaeger_exclusion_filter() -> dict:
    """Build filter to exclude Jaeger's own internal spans"""
    return {
        "term": {"process.serviceName": "jaeger"}
    }


def _build_span_tenant_filter(tenant_id: str | None) -> dict | None:
    """Build tenant filter for Jaeger spans (nested process.tags structure)"""
    if force_single_tenant or tenant_id is None:
        return None

    # Special case: "no tenant" means spans WITHOUT tenant.id tag
    if tenant_id == "no tenant":
        return {
            "bool": {
                "must_not": [
                    {
                        "nested": {
                            "path": "process.tags",
                            "query": {
                                "term": {"process.tags.key": "tenant.id"}
                            }
                        }
                    }
                ]
            }
        }

    return {
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


async def _get_all_tenant_ids(
    db_client: Any,
    start_date: datetime,
    end_date: datetime
) -> list[str]:
    """Get all unique tenant IDs from spans within the date range, excluding Jaeger internal spans"""
    start_millis = int(start_date.timestamp() * 1000)
    end_millis = int(end_date.timestamp() * 1000)

    query = {
        "size": 0,
        "query": {
            "bool": {
                "must": [
                    {
                        "range": {
                            "startTimeMillis": {
                                "gte": start_millis,
                                "lte": end_millis
                            }
                        }
                    }
                ],
                "must_not": [
                    _build_jaeger_exclusion_filter()
                ]
            }
        },
        "aggs": {
            "tenant_ids": {
                "nested": {
                    "path": "process.tags"
                },
                "aggs": {
                    "tenant_filter": {
                        "filter": {
                            "term": {"process.tags.key": "tenant.id"}
                        },
                        "aggs": {
                            "tenant_values": {
                                "terms": {
                                    "field": "process.tags.value",
                                    "size": 1000
                                }
                            }
                        }
                    }
                }
            },
            "spans_without_tenant": {
                "filter": {
                    "bool": {
                        "must_not": [
                            {
                                "nested": {
                                    "path": "process.tags",
                                    "query": {
                                        "term": {"process.tags.key": "tenant.id"}
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
    }

    # Use date-bounded indices instead of wildcard
    index_pattern = _get_jaeger_span_indices(start_date, end_date)
    response = await db_client.search(index=index_pattern, body=query, ignore_unavailable=True)

    tenant_ids = []
    tenant_agg = response["aggregations"]["tenant_ids"]["tenant_filter"]["tenant_values"]
    for bucket in tenant_agg.get("buckets", []):
        tenant_ids.append(bucket["key"])

    # Check if there are spans without tenant.id tag
    spans_without_tenant_count = response["aggregations"]["spans_without_tenant"]["doc_count"]
    if spans_without_tenant_count > 0:
        tenant_ids.append("no tenant")

    return sorted(tenant_ids) if tenant_ids else []


async def get_trace_stats_for_tenant(
    db_client: Any,
    tenant_id: str | None,
    start_date: datetime,
    end_date: datetime
) -> dict[str, Any]:
    """Get daily trace counts derived from spans (unique traceIDs) for a single tenant"""
    start_millis = int(start_date.timestamp() * 1000)
    end_millis = int(end_date.timestamp() * 1000)

    must_conditions = [
        {
            "range": {
                "startTimeMillis": {
                    "gte": start_millis,
                    "lte": end_millis
                }
            }
        }
    ]

    tenant_filter = _build_span_tenant_filter(tenant_id)
    if tenant_filter:
        must_conditions.append(tenant_filter)

    query = {
        "size": 0,
        "query": {
            "bool": {
                "must": must_conditions,
                "must_not": [
                    _build_jaeger_exclusion_filter()
                ]
            }
        },
        "aggs": {
            "daily_traces": {
                "date_histogram": {
                    "field": "startTimeMillis",
                    "calendar_interval": "day",
                    "format": "yyyy-MM-dd"
                },
                "aggs": {
                    "unique_traces": {
                        "cardinality": {
                            "field": "traceID"
                        }
                    }
                }
            },
            "total_unique_traces": {
                "cardinality": {
                    "field": "traceID"
                }
            }
        }
    }

    # Use optimized index pattern for the date range
    index_pattern = _get_jaeger_span_indices(start_date, end_date)
    response = await db_client.search(index=index_pattern, body=query, ignore_unavailable=True)

    daily_breakdown = {}
    for bucket in response["aggregations"]["daily_traces"]["buckets"]:
        daily_breakdown[bucket["key_as_string"]] = bucket["unique_traces"]["value"]

    return {
        "total": int(response["aggregations"]["total_unique_traces"]["value"]),
        "daily": daily_breakdown
    }


async def get_issue_stats_for_tenant(
    db_client: Any,
    tenant_id: str | None,
    start_date: datetime,
    end_date: datetime
) -> dict[str, Any]:
    """Get daily issue counts with breakdowns by plugin_metadata_id and level"""
    index_name = get_index_name_for_artifact_type(IssueData)

    must_conditions = [
        {
            "range": {
                "timestamp": {
                    "gte": start_date.isoformat(),
                    "lte": end_date.isoformat()
                }
            }
        }
    ]

    # Filter by tenant_id if specified
    if tenant_id and not force_single_tenant:
        must_conditions.append({"term": {"tenant_id": tenant_id}})

    query = {
        "size": 0,
        "query": {
            "bool": {
                "must": must_conditions
            }
        },
        "aggs": {
            "daily_counts": {
                "date_histogram": {
                    "field": "timestamp",
                    "calendar_interval": "day",
                    "format": "yyyy-MM-dd"
                }
            },
            "total_count": {
                "value_count": {
                    "field": "element_id"
                }
            },
            "by_plugin": {
                "terms": {
                    "field": "plugin_metadata_id",
                    "size": 100
                }
            },
            "by_level": {
                "terms": {
                    "field": "level",
                    "size": 10
                }
            }
        }
    }

    response = await db_client.search(index=index_name, body=query)

    daily_breakdown = {}
    for bucket in response["aggregations"]["daily_counts"]["buckets"]:
        daily_breakdown[bucket["key_as_string"]] = bucket["doc_count"]

    plugin_breakdown = {}
    for bucket in response["aggregations"]["by_plugin"]["buckets"]:
        plugin_breakdown[bucket["key"]] = bucket["doc_count"]

    level_breakdown = {}
    for bucket in response["aggregations"]["by_level"]["buckets"]:
        level_breakdown[bucket["key"]] = bucket["doc_count"]

    return {
        "total": int(response["aggregations"]["total_count"]["value"]),
        "daily": daily_breakdown,
        "by_plugin_metadata_id": plugin_breakdown,
        "by_level": level_breakdown
    }


async def get_traces_with_issues_count(
    db_client: Any,
    tenant_id: str | None,
    start_date: datetime,
    end_date: datetime
) -> dict[str, int]:
    """
    Get count of unique traces that have issues (fast single-query approach).

    Returns total count of traces with at least one issue.
    Use alongside total trace count to calculate success/failure rates.
    """
    index_name = get_index_name_for_artifact_type(IssueData)

    must_conditions = [
        {
            "range": {
                "timestamp": {
                    "gte": start_date.isoformat(),
                    "lte": end_date.isoformat()
                }
            }
        }
    ]

    if tenant_id and not force_single_tenant:
        must_conditions.append({"term": {"tenant_id": tenant_id}})

    query = {
        "size": 0,
        "query": {
            "bool": {
                "must": must_conditions
            }
        },
        "aggs": {
            "unique_traces_with_issues": {
                "cardinality": {
                    "field": "root_id"
                }
            }
        }
    }

    response = await db_client.search(index=index_name, body=query)

    traces_with_issues = int(response["aggregations"]["unique_traces_with_issues"]["value"])

    return {
        "traces_with_issues": traces_with_issues
    }


async def get_span_stats_for_tenant(
    db_client: Any,
    tenant_id: str | None,
    start_date: datetime,
    end_date: datetime
) -> dict[str, Any]:
    """Get daily span counts and average spans per trace (including daily breakdown)"""
    start_millis = int(start_date.timestamp() * 1000)
    end_millis = int(end_date.timestamp() * 1000)

    must_conditions = [
        {
            "range": {
                "startTimeMillis": {
                    "gte": start_millis,
                    "lte": end_millis
                }
            }
        }
    ]

    tenant_filter = _build_span_tenant_filter(tenant_id)
    if tenant_filter:
        must_conditions.append(tenant_filter)

    query = {
        "size": 0,
        "query": {
            "bool": {
                "must": must_conditions,
                "must_not": [
                    _build_jaeger_exclusion_filter()
                ]
            }
        },
        "aggs": {
            "daily_counts": {
                "date_histogram": {
                    "field": "startTimeMillis",
                    "calendar_interval": "day",
                    "format": "yyyy-MM-dd"
                },
                "aggs": {
                    "unique_traces": {
                        "cardinality": {
                            "field": "traceID"
                        }
                    }
                }
            },
            "total_spans": {
                "value_count": {
                    "field": "spanID"
                }
            },
            "unique_traces": {
                "cardinality": {
                    "field": "traceID"
                }
            }
        }
    }

    # Use optimized index pattern for the date range
    index_pattern = _get_jaeger_span_indices(start_date, end_date)
    response = await db_client.search(index=index_pattern, body=query, ignore_unavailable=True)

    daily_breakdown = {}
    daily_avg_spans_per_trace = {}
    for bucket in response["aggregations"]["daily_counts"]["buckets"]:
        date_key = bucket["key_as_string"]
        span_count = bucket["doc_count"]
        trace_count = bucket["unique_traces"]["value"]

        daily_breakdown[date_key] = span_count

        if trace_count > 0:
            daily_avg_spans_per_trace[date_key] = round(span_count / trace_count, 2)
        else:
            daily_avg_spans_per_trace[date_key] = 0.0

    total_spans = int(response["aggregations"]["total_spans"]["value"])
    unique_traces = int(response["aggregations"]["unique_traces"]["value"])

    avg_spans_per_trace = 0.0
    if unique_traces > 0:
        avg_spans_per_trace = total_spans / unique_traces

    return {
        "total": total_spans,
        "daily": daily_breakdown,
        "unique_traces": unique_traces,
        "avg_spans_per_trace": round(avg_spans_per_trace, 2),
        "daily_avg_spans_per_trace": daily_avg_spans_per_trace
    }


async def get_task_stats_for_tenant(
    db_client: Any,
    tenant_id: str | None,
    start_date: datetime,
    end_date: datetime
) -> dict[str, Any]:
    """Get daily task counts for a tenant"""
    index_name = get_index_name_for_artifact_type(TaskData)

    must_conditions = [
        {
            "range": {
                "start_time": {
                    "gte": start_date.isoformat(),
                    "lte": end_date.isoformat()
                }
            }
        }
    ]

    if tenant_id and not force_single_tenant:
        must_conditions.append({"term": {"tenant_id": tenant_id}})

    query = {
        "size": 0,
        "query": {
            "bool": {
                "must": must_conditions
            }
        },
        "aggs": {
            "daily_counts": {
                "date_histogram": {
                    "field": "start_time",
                    "calendar_interval": "day",
                    "format": "yyyy-MM-dd"
                }
            },
            "total_count": {
                "value_count": {
                    "field": "element_id"
                }
            }
        }
    }

    response = await db_client.search(index=index_name, body=query)

    daily_breakdown = {}
    for bucket in response["aggregations"]["daily_counts"]["buckets"]:
        daily_breakdown[bucket["key_as_string"]] = bucket["doc_count"]

    return {
        "total": int(response["aggregations"]["total_count"]["value"]),
        "daily": daily_breakdown
    }


def _aggregate_stats(tenant_stats: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Aggregate stats from multiple tenants into a total"""
    total_traces = 0
    total_traces_daily = {}
    total_issues = 0
    total_issues_daily = {}
    total_issues_by_plugin = {}
    total_issues_by_level = {}
    total_traces_with_issues = 0
    total_traces_without_issues = 0
    total_spans = 0
    total_spans_daily = {}
    total_unique_traces = 0
    total_daily_avg_spans = {}
    total_tasks = 0
    total_tasks_daily = {}

    for stats in tenant_stats.values():
        # Aggregate traces
        total_traces += stats["traces"]["total"]
        for date, count in stats["traces"]["daily"].items():
            total_traces_daily[date] = total_traces_daily.get(date, 0) + count

        # Aggregate issues
        total_issues += stats["issues"]["total"]
        for date, count in stats["issues"]["daily"].items():
            total_issues_daily[date] = total_issues_daily.get(date, 0) + count
        for plugin, count in stats["issues"]["by_plugin_metadata_id"].items():
            total_issues_by_plugin[plugin] = total_issues_by_plugin.get(plugin, 0) + count
        for level, count in stats["issues"]["by_level"].items():
            total_issues_by_level[level] = total_issues_by_level.get(level, 0) + count

        # Aggregate trace success metrics
        total_traces_with_issues += stats["trace_success_metrics"]["traces_with_issues"]
        total_traces_without_issues += stats["trace_success_metrics"]["traces_without_issues"]

        # Aggregate spans
        total_spans += stats["spans"]["total"]
        total_unique_traces += stats["spans"]["unique_traces"]
        for date, count in stats["spans"]["daily"].items():
            total_spans_daily[date] = total_spans_daily.get(date, 0) + count

        # For daily avg spans per trace, we need the raw data to recalculate properly
        # We'll sum up spans and traces per day
        for date, count in stats["spans"]["daily"].items():
            if date not in total_daily_avg_spans:
                total_daily_avg_spans[date] = {"spans": 0, "traces": 0}
            total_daily_avg_spans[date]["spans"] += count

        # Get trace counts from traces stats
        for date, count in stats["traces"]["daily"].items():
            if date not in total_daily_avg_spans:
                total_daily_avg_spans[date] = {"spans": 0, "traces": 0}
            total_daily_avg_spans[date]["traces"] += count

        # Aggregate tasks
        total_tasks += stats["tasks"]["total"]
        for date, count in stats["tasks"]["daily"].items():
            total_tasks_daily[date] = total_tasks_daily.get(date, 0) + count

    # Calculate total avg spans per trace
    total_avg_spans_per_trace = 0.0
    if total_unique_traces > 0:
        total_avg_spans_per_trace = total_spans / total_unique_traces

    # Calculate daily avg spans per trace from aggregated data
    daily_avg_spans_final = {}
    for date, data in total_daily_avg_spans.items():
        if data["traces"] > 0:
            daily_avg_spans_final[date] = round(data["spans"] / data["traces"], 2)
        else:
            daily_avg_spans_final[date] = 0.0

    # Calculate overall success rate
    total_success_rate = 0.0
    if total_traces > 0:
        total_success_rate = round((total_traces_without_issues / total_traces * 100), 2)

    return {
        "traces": {
            "total": total_traces,
            "daily": total_traces_daily
        },
        "issues": {
            "total": total_issues,
            "daily": total_issues_daily,
            "by_plugin_metadata_id": total_issues_by_plugin,
            "by_level": total_issues_by_level
        },
        "trace_success_metrics": {
            "total_traces": total_traces,
            "traces_with_issues": total_traces_with_issues,
            "traces_without_issues": total_traces_without_issues,
            "success_rate": total_success_rate
        },
        "spans": {
            "total": total_spans,
            "daily": total_spans_daily,
            "unique_traces": total_unique_traces,
            "avg_spans_per_trace": round(total_avg_spans_per_trace, 2),
            "daily_avg_spans_per_trace": daily_avg_spans_final
        },
        "tasks": {
            "total": total_tasks,
            "daily": total_tasks_daily
        }
    }


async def _fetch_tenant_stats(
    db_client: Any,
    tenant_id: str,
    start_date: datetime,
    end_date: datetime
) -> tuple[str, dict[str, Any]]:
    """Fetch all stats for a single tenant in parallel."""
    # Run all stats queries for this tenant concurrently
    trace_stats, issue_stats, traces_with_issues, span_stats, task_stats = await asyncio.gather(
        get_trace_stats_for_tenant(db_client, tenant_id, start_date, end_date),
        get_issue_stats_for_tenant(db_client, tenant_id, start_date, end_date),
        get_traces_with_issues_count(db_client, tenant_id, start_date, end_date),
        get_span_stats_for_tenant(db_client, tenant_id, start_date, end_date),
        get_task_stats_for_tenant(db_client, tenant_id, start_date, end_date)
    )

    # Calculate success/failure metrics
    total_traces = trace_stats["total"]
    failed_traces = traces_with_issues["traces_with_issues"]
    successful_traces = max(0, total_traces - failed_traces)

    return tenant_id, {
        "traces": trace_stats,
        "issues": issue_stats,
        "trace_success_metrics": {
            "total_traces": total_traces,
            "traces_with_issues": failed_traces,
            "traces_without_issues": successful_traces,
            "success_rate": round((successful_traces / total_traces * 100), 2) if total_traces > 0 else 0.0
        },
        "spans": span_stats,
        "tasks": task_stats
    }


async def get_tenant_statistics(
    tenant_components: TenantComponents,
    tenant_id: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None
) -> dict[str, Any]:
    """
    Get comprehensive tenant statistics with daily breakdown, per tenant.

    Args:
        tenant_components: The tenant's initialized components with DB client
        tenant_id: Optional tenant ID filter. If None, queries all tenants separately
        start_date: Start of date range (default: 7 days ago)
        end_date: End of date range (default: now)

    Returns:
        Dictionary with per-tenant stats and aggregated totals
    """
    from datetime import timedelta

    # Default to 7 days if not specified
    if end_date is None:
        end_date = datetime.utcnow()
    if start_date is None:
        start_date = end_date - timedelta(days=7)

    db_client = await _get_db_client(tenant_components)

    # Determine which tenants to query
    if tenant_id:
        tenant_ids = [tenant_id]
    else:
        # Get all tenant IDs from the data within the date range
        tenant_ids = await _get_all_tenant_ids(db_client, start_date, end_date)

    # Fetch stats for all tenants in parallel
    tenant_stats_tasks = [
        _fetch_tenant_stats(db_client, tid, start_date, end_date)
        for tid in tenant_ids
    ]
    tenant_results = await asyncio.gather(*tenant_stats_tasks)

    # Convert results to dictionary
    per_tenant_stats = dict(tenant_results)

    # Aggregate totals across all queried tenants
    aggregated_totals = _aggregate_stats(per_tenant_stats)

    return {
        "period": {
            "start": start_date.isoformat() + "Z",
            "end": end_date.isoformat() + "Z"
        },
        "tenants": per_tenant_stats,
        "totals": aggregated_totals
    }
