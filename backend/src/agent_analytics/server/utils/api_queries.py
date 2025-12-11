import base64
import json
import os
import uuid
from datetime import datetime
from typing import Any

from elasticsearch import AsyncElasticsearch
from opensearchpy import AsyncOpenSearch

from agent_analytics.runtime.api import TenantComponents

force_single_tenant = os.environ.get('FORCE_SINGLE_TENANT', "false").lower() == "true"

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

def _get_tenant_filter(tenant_id: str) -> dict | None:
    """Create tenant filter that matches tenant ID in either tags or process.tags"""
    if force_single_tenant:
        return None
    else:
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

def _encode_cursor(sort_values: list[Any]) -> str:
    """Encode sort values to create a cursor"""
    cursor_data = {"sort": sort_values}
    cursor_json = json.dumps(cursor_data, default=str)
    return base64.urlsafe_b64encode(cursor_json.encode()).decode()

def _decode_cursor(cursor: str | dict | list) -> list[Any] | None:
    """Decode cursor to get sort values for search_after"""
    if cursor is None:
        return None

    try:
        if isinstance(cursor, str):
            # Try to decode as base64 first
            try:
                decoded_bytes = base64.urlsafe_b64decode(cursor.encode())
                cursor_data = json.loads(decoded_bytes.decode())
            except:
                # If not base64, try to parse as JSON directly
                cursor_data = json.loads(cursor)
        elif isinstance(cursor, dict):
            cursor_data = cursor
        elif isinstance(cursor, list):
            # Direct sort values
            return cursor
        else:
            return None

        # Extract sort values
        if "sort" in cursor_data:
            return cursor_data["sort"]

        return None
    except (json.JSONDecodeError, ValueError, TypeError):
        return None

def _convert_value_to_otlp_attribute(value: Any) -> dict[str, Any]:
    """Convert a value to OTLP attribute value format"""
    value_type = type(value)

    if value_type is str:
        return {"stringValue": value}
    elif value_type is bool:
        return {"boolValue": value}
    elif value_type is int:
        return {"intValue": value}
    elif value_type is float:
        return {"doubleValue": value}
    elif value_type is list:
        array_values = [_convert_value_to_otlp_attribute(item) for item in value]
        return {"arrayValue": {"values": array_values}}
    else:
        return {"stringValue": str(value)}

def _map_span_kind_to_otlp(kind: str) -> str:
    """Map Jaeger span kind to OTLP format"""
    kind_map = {
        "server": "SPAN_KIND_SERVER",
        "client": "SPAN_KIND_CLIENT",
        "producer": "SPAN_KIND_PRODUCER",
        "consumer": "SPAN_KIND_CONSUMER"
    }
    return kind_map.get(kind.lower(), "SPAN_KIND_INTERNAL")

def _convert_span_to_otlp_format(hit: dict[str, Any]) -> dict[str, Any]:
    """Convert ES span document to OTLP JSON format"""
    source = hit["_source"]

    # Convert timestamps from microseconds to nanoseconds
    start_time_micros = source.get("startTime", 0)
    duration_micros = source.get("duration", 0)
    start_time_nanos = start_time_micros * 1000
    end_time_nanos = (start_time_micros + duration_micros) * 1000

    # Extract basic span information
    span = {
        "traceId": source.get("traceID", ""),
        "spanId": source.get("spanID", ""),
        "name": source.get("operationName", ""),
        "kind": _map_span_kind_to_otlp(source.get("kind", "")),
        "startTimeUnixNano": str(start_time_nanos),
        "endTimeUnixNano": str(end_time_nanos),
        "attributes": [],
        "events": [],
        "status": {
            "code": "STATUS_CODE_OK"
        }
    }

    # Extract parentSpanId from references
    references = source.get("references", [])
    for ref in references:
        if ref.get("refType") == "CHILD_OF":
            span["parentSpanId"] = ref.get("spanID")
            break

    # Convert tags to attributes
    tags = source.get("tags", [])
    for tag in tags:
        key = tag.get("key", "")
        value = tag.get("value")

        # Check for error status
        if key == "error" and value:
            span["status"]["code"] = "STATUS_CODE_ERROR"
        elif key == "http.status_code" and isinstance(value, (int, str)):
            status_code = int(value) if isinstance(value, str) and value.isdigit() else value
            if isinstance(status_code, int) and status_code >= 400:
                span["status"]["code"] = "STATUS_CODE_ERROR"

        # Add to attributes
        span["attributes"].append({
            "key": key,
            "value": _convert_value_to_otlp_attribute(value)
        })

    # Convert logs to events
    logs = source.get("logs", [])
    for log in logs:
        event = {
            "timeUnixNano": str(log.get("timestamp", 0) * 1000),  # Convert to nanos
            "name": "log",
            "attributes": []
        }

        # Extract fields from log
        fields = log.get("fields", [])
        for field in fields:
            key = field.get("key", "")
            value = field.get("value")

            event["attributes"].append({
                "key": key,
                "value": _convert_value_to_otlp_attribute(value)
            })

        span["events"].append(event)

    return span

def _group_spans_by_resource_and_scope(spans: list[dict[str, Any]], hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Group spans by resource and instrumentation scope for OTLP format"""

    # Group spans by resource (service) and scope
    resource_map = {}

    for i, span in enumerate(spans):
        hit = hits[i] if i < len(hits) else hits[0]  # Fallback to first hit
        source = hit["_source"]
        process = source.get("process", {})

        # Create resource key based on service name and process tags
        service_name = process.get("serviceName", "unknown-service")
        process_tags = process.get("tags", [])

        # Use service name as primary resource identifier
        resource_key = service_name

        if resource_key not in resource_map:
            # Create resource attributes
            resource_attributes = [
                {
                    "key": "service.name",
                    "value": {"stringValue": service_name}
                }
            ]

            # Add process tags as resource attributes
            for tag in process_tags:
                key = tag.get("key", "")
                value = tag.get("value")

                resource_attributes.append({
                    "key": key,
                    "value": _convert_value_to_otlp_attribute(value)
                })

            resource_map[resource_key] = {
                "resource": {
                    "attributes": resource_attributes
                },
                "scopeSpans": [
                    {
                        "scope": {
                            "name": "jaeger-import",
                            "version": "1.0.0"
                        },
                        "spans": []
                    }
                ]
            }

        # Add span to the resource's scope
        resource_map[resource_key]["scopeSpans"][0]["spans"].append(span)

    return {"resourceSpans": list(resource_map.values())}

def _microseconds_to_iso(microseconds: int) -> str:
    """Convert microseconds timestamp to ISO format"""
    if microseconds == 0:
        return datetime.utcnow().isoformat() + "Z"

    seconds = microseconds / 1_000_000
    dt = datetime.utcfromtimestamp(seconds)
    return dt.isoformat() + "Z"

def _convert_trace_summary_to_otlp_format(aggregation_bucket: dict[str, Any]) -> dict[str, Any]:
    """Convert ES aggregation bucket to OTLP-compliant trace summary format"""

    # Handle both terms and composite aggregation formats
    if "key" in aggregation_bucket and isinstance(aggregation_bucket["key"], str):
        # Terms aggregation format
        trace_id = aggregation_bucket["key"]
        doc_count = aggregation_bucket.get("doc_count", 0)
    else:
        # Composite aggregation format
        key_data = aggregation_bucket.get("key", {})
        trace_id = key_data.get("trace_id", "")
        doc_count = aggregation_bucket.get("doc_count", 0)

    # Extract timestamps from sub-aggregations
    start_time_agg = aggregation_bucket.get("start_time", {})
    end_time_agg = aggregation_bucket.get("end_time", {})

    start_time = None
    end_time = None

    if "value" in start_time_agg:
        start_millis = start_time_agg["value"]
        if start_millis:
            start_time = datetime.utcfromtimestamp(start_millis / 1000).isoformat() + "Z"

    if "value" in end_time_agg:
        end_millis = end_time_agg["value"]
        if end_millis:
            end_time = datetime.utcfromtimestamp(end_millis / 1000).isoformat() + "Z"

    # Fallback to current time if timestamps are missing
    if not start_time:
        start_time = datetime.utcnow().isoformat() + "Z"
    if not end_time:
        end_time = datetime.utcnow().isoformat() + "Z"

    # Calculate duration
    duration_ms = 0
    if start_time and end_time:
        try:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            duration_ms = (end_dt - start_dt).total_seconds() * 1000
        except:
            duration_ms = 0

    # Extract service names
    service_names = []
    services_agg = aggregation_bucket.get("services", {}).get("buckets", [])
    for service_bucket in services_agg:
        service_names.append(service_bucket["key"])

    # Extract agent information - handle nested structure
    agent_ids = []
    agent_names = []

    agents_agg = aggregation_bucket.get("agent_ids", {})
    if "filter" in agents_agg:
        agent_buckets = agents_agg["filter"].get("values", {}).get("buckets", [])
    else:
        agent_buckets = agents_agg.get("buckets", [])

    for agent_bucket in agent_buckets:
        agent_ids.append(agent_bucket["key"])

    agent_names_agg = aggregation_bucket.get("agent_names", {})
    if "filter" in agent_names_agg:
        agent_name_buckets = agent_names_agg["filter"].get("values", {}).get("buckets", [])
    else:
        agent_name_buckets = agent_names_agg.get("buckets", [])

    for agent_name_bucket in agent_name_buckets:
        agent_names.append(agent_name_bucket["key"])

    # Extract user and session IDs
    user_ids = []
    users_agg = aggregation_bucket.get("user_ids", {})
    if "filter" in users_agg:
        user_buckets = users_agg["filter"].get("values", {}).get("buckets", [])
    else:
        user_buckets = users_agg.get("buckets", [])

    for user_bucket in user_buckets:
        user_ids.append(user_bucket["key"])

    session_ids = []
    sessions_agg = aggregation_bucket.get("session_ids", {})
    if "filter" in sessions_agg:
        session_buckets = sessions_agg["filter"].get("values", {}).get("buckets", [])
    else:
        session_buckets = sessions_agg.get("buckets", [])

    for session_bucket in session_buckets:
        session_ids.append(session_bucket["key"])

    # Return OTLP-compliant trace summary with computed metadata
    return {
        "traceId": trace_id,
        "startTime": start_time,
        "endTime": end_time,
        "durationMs": max(0, duration_ms),
        "spanCount": doc_count,
        "serviceNames": service_names,
        "agentNames": agent_names,
        "agentIds": agent_ids,
        "userIds": user_ids,
        "sessionIds": session_ids
    }


class TraceSearchValidationError(Exception):
    """Raised when trace search query validation fails"""
    pass

def _validate_trace_search_query(
    query: Any,
    force_single_tenant: bool = False,
    max_page_size: int = 1000,
    max_time_range_days: int = 30
) -> None:
    """
    Comprehensive validation for trace search queries.
    
    Args:
        query: TraceSearchQuery object
        force_single_tenant: If True, requires at least one service_name
        max_page_size: Maximum allowed page size
        max_time_range_days: Maximum allowed time range in days
        
    Raises:
        TraceSearchValidationError: If validation fails
    """
    errors = []

    # 1. REQUIRED FIELDS VALIDATION

    # Always require filters object
    if not hasattr(query, 'filters') or query.filters is None:
        errors.append("filters object is required")
        # Early return since we can't validate filters if they don't exist
        if errors:
            raise TraceSearchValidationError(f"Validation failed: {'; '.join(errors)}")

    # Always require start_time
    if not hasattr(query.filters, 'start_time') or query.filters.start_time is None:
        errors.append("start_time is required in filters")

    # 2. SERVICE NAME VALIDATION (conditional)
    if force_single_tenant:
        if not hasattr(query.filters, 'service_names') or not query.filters.service_names:
            errors.append("At least one service_name is required when force_single_tenant is enabled")
        elif isinstance(query.filters.service_names, list):
            if len(query.filters.service_names) == 0:
                errors.append("service_names list cannot be empty when force_single_tenant is enabled")
            else:
                # Validate individual service names
                invalid_names = []
                for i, name in enumerate(query.filters.service_names):
                    if not isinstance(name, str):
                        invalid_names.append(f"Index {i}: must be string, got {type(name)}")
                    elif not name.strip():
                        invalid_names.append(f"Index {i}: cannot be empty or whitespace")
                    elif len(name.strip()) > 255:
                        invalid_names.append(f"Index {i}: too long (max 255 chars)")

                if invalid_names:
                    errors.append(f"Invalid service names: {'; '.join(invalid_names)}")

    # 3. TIME RANGE VALIDATION
    if hasattr(query.filters, 'start_time') and query.filters.start_time is not None:
        try:
            start_millis = _convert_to_millis(query.filters.start_time)
            current_time_millis = int(datetime.utcnow().timestamp() * 1000)

            # Check if start_time is not too far in the future
            if start_millis > current_time_millis + (24 * 60 * 60 * 1000):  # 1 day buffer
                errors.append("start_time cannot be more than 1 day in the future")

            # Check end_time if provided
            if hasattr(query.filters, 'end_time') and query.filters.end_time is not None:
                try:
                    end_millis = _convert_to_millis(query.filters.end_time)

                    # end_time must be after start_time
                    if end_millis <= start_millis:
                        errors.append("end_time must be after start_time")

                    # Check maximum time range
                    time_range_ms = end_millis - start_millis
                    max_range_ms = max_time_range_days * 24 * 60 * 60 * 1000
                    if time_range_ms > max_range_ms:
                        errors.append(f"Time range cannot exceed {max_time_range_days} days")

                except (ValueError, TypeError) as e:
                    errors.append(f"Invalid end_time format: {e}")

        except (ValueError, TypeError) as e:
            errors.append(f"Invalid start_time format: {e}")

    # 4. PAGINATION VALIDATION
    if hasattr(query, 'page_size'):
        if query.page_size is not None:
            if not isinstance(query.page_size, int):
                errors.append("page_size must be an integer")
            elif query.page_size < 1:
                errors.append("page_size must be at least 1")
            elif query.page_size > max_page_size:
                errors.append(f"page_size cannot exceed {max_page_size}")

    # Validate cursor format if provided
    if hasattr(query, 'cursor') and query.cursor is not None:
        if isinstance(query.cursor, str):
            # Try to decode cursor to validate format
            try:
                _decode_cursor(query.cursor)
            except Exception:
                errors.append("Invalid cursor format")

    # 5. ID FIELD VALIDATIONS
    id_fields = ['agent_ids', 'user_ids', 'session_ids', 'agent_names']
    for field_name in id_fields:
        if hasattr(query.filters, field_name):
            field_value = getattr(query.filters, field_name)
            if field_value is not None:
                if not isinstance(field_value, list):
                    errors.append(f"{field_name} must be a list")
                elif len(field_value) > 100:  # Reasonable limit
                    errors.append(f"{field_name} cannot have more than 100 items")
                else:
                    # Validate individual IDs
                    invalid_ids = []
                    for i, id_val in enumerate(field_value):
                        if not isinstance(id_val, str):
                            invalid_ids.append(f"Index {i}: must be string")
                        elif not id_val.strip():
                            invalid_ids.append(f"Index {i}: cannot be empty")
                        elif len(id_val.strip()) > 255:
                            invalid_ids.append(f"Index {i}: too long (max 255 chars)")
                        # Validate UUID format for agent_ids and user_ids
                        elif field_name in ['agent_ids', 'user_ids']:
                            try:
                                uuid.UUID(id_val.strip())
                            except ValueError:
                                invalid_ids.append(f"Index {i}: invalid UUID format")

                    if invalid_ids:
                        errors.append(f"Invalid {field_name}: {'; '.join(invalid_ids)}")

    # 6. SPAN COUNT RANGE VALIDATION
    if hasattr(query.filters, 'span_count_range') and query.filters.span_count_range is not None:
        span_range = query.filters.span_count_range
        if hasattr(span_range, 'min') and span_range.min is not None:
            if not isinstance(span_range.min, int) or span_range.min < 0:
                errors.append("span_count_range.min must be a non-negative integer")

        if hasattr(span_range, 'max') and span_range.max is not None:
            if not isinstance(span_range.max, int) or span_range.max < 1:
                errors.append("span_count_range.max must be a positive integer")
            elif span_range.max > 10000:  # Reasonable upper limit
                errors.append("span_count_range.max cannot exceed 10000")

        # Check min <= max
        if (hasattr(span_range, 'min') and span_range.min is not None and
            hasattr(span_range, 'max') and span_range.max is not None):
            if span_range.min > span_range.max:
                errors.append("span_count_range.min cannot be greater than max")

    # 7. SORT VALIDATION
    if hasattr(query, 'sort') and query.sort is not None:
        valid_sort_fields = ['start_time', 'end_time', 'duration', 'span_count']
        valid_directions = ['asc', 'desc']

        if hasattr(query.sort, 'field') and query.sort.field is not None:
            if query.sort.field not in valid_sort_fields:
                errors.append(f"Invalid sort field. Must be one of: {', '.join(valid_sort_fields)}")

        if hasattr(query.sort, 'direction') and query.sort.direction is not None:
            if query.sort.direction not in valid_directions:
                errors.append(f"Invalid sort direction. Must be one of: {', '.join(valid_directions)}")

    # 8. BOOLEAN FLAGS VALIDATION
    boolean_flags = ['include_root_spans']
    for flag_name in boolean_flags:
        if hasattr(query, flag_name):
            flag_value = getattr(query, flag_name)
            if flag_value is not None and not isinstance(flag_value, bool):
                errors.append(f"{flag_name} must be a boolean")

    # 9. STRING LENGTH LIMITS (for performance)
    if hasattr(query.filters, 'service_names') and query.filters.service_names:
        if isinstance(query.filters.service_names, list):
            for i, name in enumerate(query.filters.service_names):
                if isinstance(name, str) and len(name) > 255:
                    errors.append(f"service_names[{i}] exceeds 255 character limit")

    # Raise all validation errors at once
    if errors:
        raise TraceSearchValidationError(f"Validation failed: {'; '.join(errors)}")


async def get_spans_for_trace(
    tenant_components: TenantComponents,
    tenant_id: str,
    trace_id: str,
    page_size: int = 50,
    cursor: dict | list | str | None = None
) -> dict[str, Any]:
    """Get spans for a specific trace with cursor-based pagination, returning OTLP-compliant format"""
    db_client = await _get_db_client(tenant_components)

    # Build the base query
    query = {
        "size": page_size,
        "query": {
            "bool": {
                "must": [
                    {"term": {"traceID": trace_id}}
                ]
            }
        },
        "sort": [
            {"startTime": {"order": "asc"}},
            {"spanID": {"order": "asc"}}  # Use spanID instead of _id for stable pagination
        ]
    }

    tenant_filter = _get_tenant_filter(tenant_id)
    if tenant_filter:
        query["query"]["bool"]["must"].append(tenant_filter)

    # Add search_after for cursor-based pagination
    sort_values = _decode_cursor(cursor)
    if sort_values:
        query["search_after"] = sort_values

    # Execute the query
    response = await db_client.search(index="*jaeger-span*", body=query)

    # Get total count with a separate count query (for performance)
    count_query = {
        "query": query["query"]
    }
    count_response = await db_client.count(index="*jaeger-span*", body=count_query)
    total_count = count_response["count"]

    # Process results
    hits = response["hits"]["hits"]
    spans = [_convert_span_to_otlp_format(hit) for hit in hits]

    # Group spans by resource and scope for OTLP format
    trace_data = _group_spans_by_resource_and_scope(spans, hits)

    # Generate next cursor
    next_cursor = None
    if len(hits) == page_size and len(hits) > 0:
        last_hit = hits[-1]
        sort_values = last_hit["sort"]
        next_cursor = _encode_cursor(sort_values)

    return {
        "traceData": trace_data,
        "nextCursor": next_cursor,
        "totalCount": total_count
    }

async def search_traces_with_search_after(
    tenant_components: TenantComponents,
    tenant_id: str,
    query: Any  # TraceSearchQuery object
) -> dict[str, Any]:
    """Search traces using proper search_after pagination, returning OTLP-compliant summaries"""

    try:
        # Comprehensive query validation
        _validate_trace_search_query(
            query,
            force_single_tenant=force_single_tenant,
            max_page_size=1000,
            max_time_range_days=30
        )

    except TraceSearchValidationError as e:
        # Log the error and return structured error response
        print(f"Trace search validation failed: {e}")
        return {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": str(e)
            },
            "traceSummaries": [],
            "nextCursor": None,
            "totalCount": 0
        }

    db_client = await _get_db_client(tenant_components)

    # Convert datetime filters to milliseconds
    start_millis = _convert_to_millis(query.filters.start_time)
    end_millis = _convert_to_millis(query.filters.end_time)

    # Build the base query filters (same as before)
    must_conditions = [
        {"range": {"startTimeMillis": {"gte": start_millis, "lte": end_millis}}},
    ]

    tenant_filter = _get_tenant_filter(tenant_id)
    if tenant_filter:
        must_conditions.append(tenant_filter)

    # Add service name filter
    if query.filters.service_names:
        must_conditions.append({
            "terms": {"process.serviceName": query.filters.service_names}
        })

    # Add agent filters (same as before)
    if query.filters.agent_ids:
        must_conditions.append({
            "nested": {
                "path": "tags",
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"tags.key": "agent.id"}},
                            {"terms": {"tags.value": query.filters.agent_ids}}
                        ]
                    }
                }
            }
        })

    # Build sort configuration for search_after
    sort_config = [{"traceID": {"order": "asc"}}]
    if query.sort and query.sort.field == "start_time":
        sort_config.append({"startTimeMillis": {"order": query.sort.direction}})
    elif query.sort and query.sort.field == "end_time":
        sort_config.append({
            "script": {
                "type": "number",
                "script": "doc['startTimeMillis'].value.millis + doc['duration'].value",
                "order": query.sort.direction
            }
        })
    else:
        sort_config.append({"startTimeMillis": {"order": "desc"}})

    # Add secondary sorts for stable pagination
    sort_config.extend([
        {"spanID": {"order": "asc"}}  # Final tiebreaker
    ])

    # Calculate fetch size (we need more spans to get complete traces)
    estimated_spans_per_trace = 10  # Adjust based on your data
    fetch_size = query.page_size * estimated_spans_per_trace

    # Build the search query - fetch individual spans, not aggregations
    search_query = {
        "size": min(fetch_size, 10000),  # ES limit
        "query": {
            "bool": {
                "must": must_conditions
            }
        },
        "sort": sort_config,
        "_source": {
            "includes": [
                "traceID", "spanID", "startTime", "duration",
                "process.serviceName", "tags", "references", "operationName"
            ]
        }
    }

    # Add search_after for cursor pagination
    if query.cursor:
        sort_values = _decode_cursor(query.cursor)
        if sort_values:
            search_query["search_after"] = sort_values

    # Execute the search
    response = await db_client.search(index="*jaeger-span*", body=search_query)

    # Process spans and group by trace_id
    spans = response["hits"]["hits"]
    trace_data = {}

    for hit in spans:
        source = hit["_source"]
        trace_id = source.get("traceID")

        if trace_id not in trace_data:
            trace_data[trace_id] = {
                "traceId": trace_id,
                "spans": [],
                "startTime": None,
                "endTime": None,
                "serviceNames": set(),
                "agentIds": set(),
                "agentNames": set(),
                "userIds": set(),
                "sessionIds": set()
            }

        trace_info = trace_data[trace_id]
        trace_info["spans"].append(hit)

        # Update trace metadata
        span_start = source.get("startTime", 0)
        span_duration = source.get("duration", 0)
        span_end = span_start + span_duration

        if not trace_info["startTime"] or span_start < trace_info["startTime"]:
            trace_info["startTime"] = span_start
        if not trace_info["endTime"] or span_end > trace_info["endTime"]:
            trace_info["endTime"] = span_end

        # Extract service name
        service_name = source.get("process", {}).get("serviceName")
        if service_name:
            trace_info["serviceNames"].add(service_name)

        # Extract agent/user info from tags
        tags = source.get("tags", [])
        for tag in tags:
            key = tag.get("key", "")
            value = tag.get("value", "")

            if key == "agent.id" and value:
                trace_info["agentIds"].add(value)
            elif key == "agent.name" and value:
                trace_info["agentNames"].add(value)
            elif key == "user.id" and value:
                trace_info["userIds"].add(value)
            elif key == "session.id" and value:
                trace_info["sessionIds"].add(value)

    # Convert to trace summaries and apply span count filter
    trace_summaries = []
    for trace_id, trace_info in trace_data.items():
        span_count = len(trace_info["spans"])

        # Apply span count range filter if specified
        if query.filters.span_count_range:
            if query.filters.span_count_range.min and span_count < query.filters.span_count_range.min:
                continue
            if query.filters.span_count_range.max and span_count > query.filters.span_count_range.max:
                continue

        # Convert timestamps
        start_time = _microseconds_to_iso(trace_info["startTime"]) if trace_info["startTime"] else datetime.utcnow().isoformat() + "Z"
        end_time = _microseconds_to_iso(trace_info["endTime"]) if trace_info["endTime"] else datetime.utcnow().isoformat() + "Z"

        # Calculate duration
        duration_ms = 0
        if trace_info["startTime"] and trace_info["endTime"]:
            duration_ms = (trace_info["endTime"] - trace_info["startTime"]) / 1000  # Convert to ms

        trace_summary = {
            "traceId": trace_id,
            "startTime": start_time,
            "endTime": end_time,
            "durationMs": max(0, duration_ms),
            "spanCount": span_count,
            "serviceNames": list(trace_info["serviceNames"]),
            "agentNames": list(trace_info["agentNames"]),
            "agentIds": list(trace_info["agentIds"]),
            "userIds": list(trace_info["userIds"]),
            "sessionIds": list(trace_info["sessionIds"])
        }

        # Add root spans if requested (converted to OTLP format)
        if query.include_root_spans:
            root_spans = []
            for span_hit in trace_info["spans"]:
                source = span_hit["_source"]
                references = source.get("references", [])
                is_root = not any(ref.get("refType") == "CHILD_OF" for ref in references)
                if is_root:
                    root_spans.append(_convert_span_to_otlp_format(span_hit))
                if len(root_spans) >= 5:  # Limit root spans
                    break
            trace_summary["rootSpans"] = root_spans

        trace_summaries.append(trace_summary)

    # Sort trace summaries by the requested sort order
    if query.sort and query.sort.field == "end_time":
        trace_summaries.sort(
            key=lambda t: _convert_to_millis(t["endTime"]),
            reverse=(query.sort.direction == "desc")
        )
    else:
        trace_summaries.sort(
            key=lambda t: _convert_to_millis(t["startTime"]),
            reverse=(query.sort.direction == "desc" if query.sort else True)
        )

    # Apply page size limit
    has_more_traces = len(trace_summaries) > query.page_size
    if has_more_traces:
        trace_summaries = trace_summaries[:query.page_size]

    # Generate next cursor from the last span, not the last trace
    next_cursor = None
    if len(spans) >= fetch_size or has_more_traces:
        if spans:
            last_span = spans[-1]
            next_cursor = _encode_cursor(last_span["sort"])

    # Get approximate total count
    total_count = len(trace_data)
    if has_more_traces:
        total_count += query.page_size  # Rough estimate

    return {
        "traceSummaries": trace_summaries,
        "nextCursor": next_cursor,
        "totalCount": total_count
    }
