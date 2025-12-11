import json
import logging
import os
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import requests

from agent_analytics.core.data.span_data import (
    BaseSpanData,
    Resource,
    ResourceAttributes,
    SpanContext,
    SpanEvent,
    SpanKind,
    SpanStatus,
)

from .store_config import StoreConfig
from .store_interface import (
    BaseStore,
    M,
    QueryFilter,
    QueryOperator,
    SortOrder,
    StoreFactory,
)

logger = logging.getLogger('jaeger-store')
logger.setLevel(logging.WARN)
proxy_server_url = os.environ.get('PROXY_SERVER_URL', None)
jaeger_query_limit = int(os.environ.get('JAEGER_QUERY_LIMIT', "1000"))
force_single_tenant = os.environ.get('FORCE_SINGLE_TENANT', "false").lower() == "true"


def fetch_jaeger_spans(
    url: str,
    tenant_id: str,
    service_name: str | None = None,
    trace_id: str | None = None,
    start_time_min: int | None = None,
    start_time_max: int | None = None,
    limit: int | None = jaeger_query_limit,
) -> list[BaseSpanData]:
    """
    Fetches traces from the Jaeger API either by service or a specific trace ID.
    
    Args:
        url (str): The Jaeger API base URL.
        service_name (Optional[str]): The service name to filter spans (mutually exclusive with trace_id).
        trace_id (Optional[str]): The specific trace ID to fetch spans (mutually exclusive with service_name).
        start_time_min (Optional[int]): The minimum start time (in microseconds) for filtering (used with service_name).
        start_time_max (Optional[int]): The maximum start time (in microseconds) for filtering (used with service_name).

    Returns:
        List[BaseSpanData]: List of converted span objects.
    """
    if service_name and trace_id:
        raise ValueError("Cannot specify both service_name and trace_id. Choose one.")

    # flag to be used later - to know where we started
    is_fetch_by_service = True

    if trace_id:
        is_fetch_by_service = False
        # pre-flight call to store the trace-id in the tenant-proxy cache
        if proxy_server_url:
            payload = [{
                "trace_id": trace_id,
                "tenant_id": tenant_id
            }]
            print(f"PRE-FLIGHT: trace_id:{trace_id} tenant_id: {tenant_id}")
            response = requests.post(f'{proxy_server_url}/trace-tenant', json=payload)

        # Fetching a specific trace by ID
        api_url = f"{url}/api/traces/{trace_id}"
        params = {}
        if start_time_min:
            params["start_time"] = start_time_min
        if start_time_max:
            params["end_time"] = start_time_max
    else:
        # Fetching traces by service name
        api_url = f"{url}/api/traces"
        params = {"service": service_name, "raw_traces": "true"}
        if start_time_min:
            params["start"] = start_time_min
        if start_time_max:
            params["end"] = start_time_max
        if limit:
            params["limit"] = limit

        # This is critical for filtering and locating the service
        if not force_single_tenant:
            params["tags"] = json.dumps({
                "tenant.id": tenant_id
            })

    logger.info(f"URL:{api_url} PARAMS: {params}")
    print(f">>>>>>>>>>>>>>URL:{api_url} PARAMS: {params}")

    response = requests.get(api_url, params=params)

    if response.status_code != 200:
        raise Exception(f"Failed to fetch traces: {response.status_code}")

    data = response.json().get("data", [])
    spans_list = []
    tenants_payload = []

    for trace in data:
        trace_id = trace.get("traceID", None)
        tenants_payload.append({
            "trace_id": trace_id,
            "tenant_id": tenant_id
        })
        service_name = trace.get("processes", {}).get("p1", {}).get("serviceName", "unknown")

        for span in trace.get("spans", []):
            operation_name = span["operationName"]
            span_id = span["spanID"]
            references = span.get("references", [])
            parent_id = references[0].get("spanID", None) if references else None

            start_time = datetime.fromtimestamp(span["startTime"] / 1e6, tz=UTC)
            end_time = start_time + timedelta(microseconds=span["duration"])
            kind = SpanKind.INTERNAL
            raw_attributes = {}

            # Extract span.kind from tags
            for tag in span.get("tags", []):
                key, value = tag["key"], tag["value"]
                if key == "span.kind":
                    kind_value = "SpanKind." + value.upper()
                    kind = SpanKind(kind_value) if value.upper() in SpanKind.__members__ else SpanKind.INTERNAL
                else:
                    raw_attributes[key] = value

            events = []
            current_dict = {}
            name = ''
            timestamp = ''
            logs = span.get("logs", [])
            if logs:
                for log in logs:
                    for tag in log.get('fields', []):
                        key, type, value = tag["key"], tag['type'], tag["value"]
                        if key == 'name':
                            name = value
                        elif key == 'timestamp':
                            timestamp = value
                        else:
                            current_dict[key] = value

                    if timestamp == '':
                        timestamp = log.get('timestamp', '')

                    if current_dict:
                        events.append(SpanEvent(name=name, timestamp=timestamp,attributes=current_dict))

            # Convert SpanContext to a dictionary before passing to BaseSpan
            context_dict = SpanContext(trace_id=trace_id, span_id=span_id).model_dump()

            base_span = {
                'name':operation_name,
                'context':context_dict,  # Ensure dictionary format
                'parent_id':parent_id,
                'kind':kind,
                'start_time':start_time,
                'end_time':end_time,
                'status':SpanStatus(status_code='200'),
                'resource':Resource(attributes=ResourceAttributes(service_name=service_name)),
                'raw_attributes':raw_attributes,
                'events':events,
                'links':[],
            }

            spans_list.append(base_span)

    # This is double assurance for storing the traces in the proxy
    if proxy_server_url and is_fetch_by_service:
        print(f"POST-FLIGHT: {tenants_payload}")
        response = requests.post(f'{proxy_server_url}/trace-tenant', json=tenants_payload)

    return spans_list

#root_id, resource.attributes.service_name
class JaegerStoreConfig(StoreConfig):
    """JaegerAPI-specific configuration"""
    url: str
    tenant_id: str

class JaegerStore(BaseStore[M]):
    def __init__(
        self,
        model_class: type[M],
        url: str,
        tenant_id: str,
    ):
        self.model_class = model_class
        self.url = url
        self.tenant_id = tenant_id

    async def initialize(self, mappings: dict[str, Any] | None = None, settings: dict[str, Any] | None = None) -> None:
        pass

    def _construct_model(self, data: dict[str, Any], model_class: type[M]) -> M:
        """Construct a model instance from dictionary data"""
        if 'type' in data:
            del data['type']
        return model_class(**data)


    def _translate_query_filter(self, field:str, value: QueryFilter) -> Any:
        if value.operator == QueryOperator.EQUAL:
            return value.value
        elif value.operator == QueryOperator.GREATER_EQUAL:
            return {"$gte": value.value}
        elif value.operator == QueryOperator.LESS_EQUAL:
            return {"$lte": value.value}
        raise ValueError(f"Unsupported operator: {value.operator}")

    async def store(self, data: M, type_info: type[M] | None = None) -> str:
        raise NotImplementedError(f"store not implemeneted in {self.__class__}")


    async def retrieve(
        self,
        id_field: str,
        id_value: Any,
        type_info: type[M] | None = None
    ) -> M | None:
        raise NotImplementedError(f"retrieve not implemeneted in {self.__class__}")

    async def search(
            self,
            query: dict[str, QueryFilter],
            type_info: type[M] | None = None,
            sort_by: dict[str, SortOrder] | None = None,
            skip: int = 0,
            limit: int | None = jaeger_query_limit,
        ) -> list[M]:
        """Search for documents"""
        # Validate query is a dictionary
        if not isinstance(query, dict):
            raise ValueError("The `query` parameter must be a dictionary of key-value pairs.")
        if type_info is not BaseSpanData:
            raise ValueError(f"The only supported type is {BaseSpanData.__class__}")
        # Extract parameters from the query
        service_name = query.get("resource.attributes.service_name")
        trace_id = query.get("root_id")
        if trace_id:
            trace_id = trace_id.value
        # Extract time filters if they exist
        start_time_min = None
        if "start_time" in query:
            start_time_filter = query["start_time"]
            start_time_filter = self._translate_query_filter("start_time_filter", start_time_filter)
            if isinstance(start_time_filter, dict) and "$gte" in start_time_filter:
                start_time_min = int(start_time_filter["$gte"].timestamp() * 1e6)

        start_time_max=None
        if "end_time" in query:
            end_time_filter = query["end_time"]
            end_time_filter = self._translate_query_filter("end_time_filter", end_time_filter)
            if isinstance(end_time_filter, dict) and "$lte" in end_time_filter:
                start_time_max = int(end_time_filter["$lte"].timestamp() * 1e6)

        # Call fetch_jaeger_spans based on extracted parameters
        if service_name and trace_id:
            raise ValueError("Cannot specify both service_name and trace_id. Choose one.")
        if trace_id:
            spans = fetch_jaeger_spans(self.url, self.tenant_id, trace_id=trace_id, start_time_min=start_time_min, start_time_max=start_time_max)
        elif service_name:
            service_name = self._translate_query_filter("service_name", service_name)
            spans = fetch_jaeger_spans(self.url, self.tenant_id, service_name=service_name, start_time_min=start_time_min, start_time_max=start_time_max)
        else:
            raise ValueError("Query must include either `resource.attributes.service_name` or `root_id`")

        # Convert spans to the expected model format
        #return [self._construct_model(span.model_dump(), type_info or self.model_class) for span in spans]
        return [self._construct_model(result, type_info or self.model_class) for result in spans]



    async def update(
        self,
        id_field: str,
        id_value: Any,
        data: dict[str, Any],
        type_info: type[M] | None = None,
        upsert: bool = False
    ) -> bool:
        raise NotImplementedError(f"update not implemeneted in {self.__class__}")

    async def delete(
        self,
        id_field: str,
        id_value: Any,
        type_info: type[M] | None = None
    ) -> bool:
        raise NotImplementedError(f"delete not implemeneted in {self.__class__}")

    async def bulk_store(
        self,
        items: Sequence[M],
        type_info: type[M] | None = None
    ) -> list[str]:
        raise NotImplementedError(f"bulk_store not implemeneted in {self.__class__}")

    async def bulk_update(
        self,
        updates: list[tuple[dict[str, Any], dict[str, Any]]],
        type_info: type[M] | None = None,
        ordered: bool = True
    ) -> int:
        raise NotImplementedError(f"bulk_update not implemeneted in {self.__class__}")

class JaegerStoreFactory(StoreFactory):
    async def create_store(
        self,
        model_class: type[M],
        config: StoreConfig,
    ) -> BaseStore[M]:
        if not isinstance(config, JaegerStoreConfig):
            raise ValueError("Jaeger store requires JaegerStoreConfig")

        store = JaegerStore(
            model_class=model_class,
            url=config.url,
            tenant_id=config.tenant_id
        )

        return store
