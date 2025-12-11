import requests
from typing import Dict, List, Optional
import json
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta

from agent_analytics.core.data.span_data import SpanContext, SpanKind,SpanStatus, Resource, ResourceAttributes 

# Set up logging
from agent_analytics.server.logger import logger

# Load environment variables from .env file
load_dotenv()

class InstanaClient:
    def __init__(self, base_url: str, api_token: str):
        """
        Initialize the Instana API client.
        """
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.headers = {
            'Authorization': f'apiToken {api_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def get_traces(
        self,
        service_name: str,
        window_size_ms: int = 604800000,  # 7 days in milliseconds
        limit: int = 100,
        tenant_id: str = "default"
    ) -> List[Dict]:
        """
        Fetch traces for a specific service within a time range.
        """
        # Construct the API endpoint
        endpoint = f"{self.base_url}/api/application-monitoring/analyze/traces"

        # Build the query based on the documentation
        query = {
            "timeFrame": {
                "windowSize": window_size_ms
            },
            "pagination": {
                "retrievalSize": limit
            },
            "tagFilters": [
                {
                    "name": "service.name",
                    "operator": "EQUALS",
                    "value": service_name,
                    "entity": "SOURCE"
                }
            ]
        }

        try:
            logger.debug("\nSending query to Instana:")
            logger.debug(json.dumps(query, indent=2))
            
            response = requests.post(
                endpoint,
                headers=self.headers,
                json=query
            )
            response.raise_for_status()
            
            response_data = response.json()
            
            logger.debug("\nAPI Response metadata:")
            logger.debug(f"Total hits: {response_data.get('totalHits', 0)}")
            logger.debug(f"Can load more: {response_data.get('canLoadMore', False)}")
            logger.debug(f"Adjusted timeframe: {json.dumps(response_data.get('adjustedTimeframe', {}), indent=2)}")
            
            # Get the snapshot ID from the first successful response
            self.snapshot_id = response_data.get('snapshotId')
            if self.snapshot_id:
                logger.debug(f"Got snapshot ID: {self.snapshot_id}")
            
            return response_data.get('items', [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching traces: {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response content: {e.response.text}")
            return []

    def get_trace_details(self, trace_id: str, tenant_id: str = "default") -> List:
        """
        Fetch detailed information for a specific trace.
        """
        try:
            # Now get the actual trace details
            # endpoint = f"{self.base_url}/api/application-monitoring/v2/analyze/traces/{trace_id}"
            endpoint = f"{self.base_url}/api/application-monitoring/analyze/traces/{trace_id}/raw"
            
            response = requests.get(
                endpoint,
                headers=self.headers
            )
            response.raise_for_status()
            
            spans = response.json()
            # calls_suffix = "/calls/{call_id}/details"
            # # TODO: Replace with call to group calls!!!
            # for i, call in enumerate(traces):
            #     if i < 5:
            #         call_endpoint = f"{endpoint}{calls_suffix}".format(call_id=call["id"])
            #         response = requests.get(
            #             call_endpoint,
            #             headers=self.headers
            #         )
            #         response.raise_for_status()
            #         call["call"] = response.json()
                
            return spans
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching trace details: {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response content: {e.response.text}")
            return []

    def convert_to_base_spans(self, spans: List) -> List[Dict]:
        spans_list = []
        for span in spans:
            trace_id = span.get("traceId", None)
            service_name = span.get("data", {}).get("service", {})

            operation_name = span["label"]
            span_id = span["spanId"]
            parent_id = span["parentSpanId"]

            start_time = datetime.fromtimestamp(span["timestamp"] / 1e3)
            end_time = start_time + timedelta(microseconds=span["duration"] * 1e3)
            kind = SpanKind.INTERNAL
            raw_attributes = {}

            # Extract span.kind from tags
            for key, value in span.get("data", {}).get("tags", {}).items():
                if key == "span.kind":
                    kind_value = "SpanKind." + value.upper()
                    kind = SpanKind(kind_value) if value.upper() in SpanKind.__members__ else SpanKind.INTERNAL
                else:
                    raw_attributes[key] = value

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
                'resource':Resource(attributes=ResourceAttributes(service_name=service_name, 
                                                                telemetry_sdk_language=None,
                                                                telemetry_sdk_name=None,
                                                                telemetry_sdk_version=None
                                                                )),
                'raw_attributes':raw_attributes,
                'events':[],
                'links':[],
            }

            spans_list.append(base_span)  
            
        return spans_list  


def main():
    # Load configuration from environment variables
    INSTANA_URL = os.getenv('INSTANA_URL')
    API_TOKEN = os.getenv('API_TOKEN')
    SERVICE_NAME = os.getenv('SERVICE_NAME')

    # Validate environment variables
    if not all([INSTANA_URL, API_TOKEN, SERVICE_NAME]):
        logger.error("Error: Missing required environment variables.")
        logger.error("Please ensure INSTANA_URL, API_TOKEN, and SERVICE_NAME are set in your .env file.")
        return

    logger.info(f"Using service name: {SERVICE_NAME}")

    # Initialize client
    client = InstanaClient(INSTANA_URL, API_TOKEN)

    # Get traces using 7-day window
    traces = client.get_traces(
        service_name=SERVICE_NAME,
        window_size_ms=604800000,  # 7 days
        limit=100
    )

    # Process and print traces
    logger.debug(f"\nFound {len(traces)} traces")
    for i,item in enumerate(traces):
        if i == 0:
            trace = item.get('trace', {})
            logger.debug(f"\nTrace ID: {trace.get('id', 'N/A')}")
            start_time = datetime.fromtimestamp(trace.get('startTime', 0)/1000)
            logger.debug(f"Start time: {start_time}")
            logger.debug(f"Duration: {trace.get('duration', 'N/A')}ms")
            logger.debug(f"Service: {trace.get('service', {}).get('label', 'N/A')}")
            
            details = client.get_trace_details(trace['id'])
            if details:
                logger.debug("Detailed call graph:")
                logger.debug(json.dumps(details, indent=2))

if __name__ == "__main__":
    main()