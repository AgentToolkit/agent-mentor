import base64
import logging
import os

from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter as GRPCSpanExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Event, ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind
from opentelemetry.trace.span import SpanContext, TraceFlags, TraceState

from agent_analytics.core.data.span_data import BaseSpanData
from agent_analytics.runtime.utilities.file_loader import TraceLogParser

# Configure logger
logger = logging.getLogger(__name__)

PROXY_SERVER_URL = os.environ.get('PROXY_SERVER_URL', None)
DEFAULT_TENANT_ID = os.getenv('DEFAULT_TENANT_ID', 'default')

def get_collector_config(tenant_id: str, collector_service: str | None = None) -> tuple[str, dict[str, str]]:
    """
    Get OTLP collector endpoint and headers based on OTEL_COLLECTOR_SERVICE env var.

    Supported services:
    - 'jaeger': Uses JAEGER_COLLECT_URL, adds X-Tenant-Id header
    - 'langfuse': Uses LANGFUSE_COLLECT_URL, adds Basic Auth and X-Tenant-Id headers

    Args:
        tenant_id: Tenant identifier
        collector_service: Override for OTEL_COLLECTOR_SERVICE env var

    Returns:
        tuple: (endpoint_url, headers_dict)
    """
    service = (collector_service or os.getenv('OTEL_COLLECTOR_SERVICE', 'jaeger')).lower()

    if service == 'langfuse':
        endpoint = os.getenv('LANGFUSE_COLLECT_URL', 'http://localhost:3000/api/public/otel')
        public_key = os.getenv('LANGFUSE_PUBLIC_KEY')
        secret_key = os.getenv('LANGFUSE_SECRET_KEY')

        # headers: dict[str, str] = {"X-Tenant-Id": tenant_id}
        headers: dict[str, str] = {}

        if public_key and secret_key:
            auth_string = f"{public_key}:{secret_key}"
            auth_bytes = auth_string.encode()
            auth_b64 = base64.b64encode(auth_bytes).decode()
            headers["Authorization"] = f"Basic {auth_b64}"
            endpoint=f"{endpoint.rstrip('/')}/v1/traces"
            print(f"Configured Langfuse with Basic Auth (key: {public_key[:8]}...)")
        else:
            print("⚠️  Warning: Langfuse service selected but WATSONXAGENTOPS_PUBLIC_KEY or WATSONXAGENTOPS_SECRET_KEY not set!")

        return endpoint, headers

    elif service == 'jaeger':
        endpoint = os.getenv('JAEGER_COLLECT_URL', 'http://localhost:4318')

        # Ensure endpoint has the correct suffix - This now relates only to localhost testing
        if endpoint.startswith("http://localhost") and not endpoint.endswith(":4318/v1/traces"):
            endpoint = endpoint.rstrip("/")
            if not endpoint.endswith(":4318"):
                endpoint += ":4318"
            endpoint += "/v1/traces"

        headers: dict[str, str] = {"X-Tenant-Id": tenant_id}
        print("Configured Jaeger collector")
        return endpoint, headers

    else:
        raise ValueError(f"Unknown OTEL_COLLECTOR_SERVICE: {service}. Must be 'jaeger' or 'langfuse'")

def hex_to_bytes(hex_str: str) -> bytes:
    """Convert hex string (with or without 0x prefix) to bytes"""
    hex_str = hex_str.replace('0x', '')
    return int(hex_str, 16).to_bytes(16, byteorder='big')




def send_spans(
    spans: list[BaseSpanData],
    tenant_id: str,
    endpoint: str | None = None,
    batch_size: int = 100,
    collector_service: str | None = None
):
    """Send spans using OTLPSpanExporter in batches

    Args:
        spans: List of spans to export
        tenant_id: Tenant identifier for multi-tenant setup
        endpoint: OTLP endpoint URL (optional, auto-configured based on OTEL_COLLECTOR_SERVICE)
        batch_size: Number of spans to send in each batch
        collector_service: Override OTEL_COLLECTOR_SERVICE ('jaeger' or 'langfuse')

    Environment Variables:
        OTEL_COLLECTOR_SERVICE: 'jaeger' or 'langfuse' (default: 'jaeger')
        JAEGER_COLLECT_URL: Jaeger collector endpoint (default: 'http://localhost:4318')
        LANGFUSE_COLLECT_URL: Langfuse OTLP endpoint (default: 'http://localhost:3000/api/public/otel')
        LANGFUSE_PUBLIC_KEY: Langfuse public key (required for Langfuse)
        LANGFUSE_SECRET_KEY: Langfuse secret key (required for Langfuse)
    """
    if len(spans) == 0:
        raise Exception("Trying to process a file with ZERO spans. Please check the file and try again.")

    service_name = spans[0].resource.attributes.service_name

    # Extract tenant_id from span if available
    candidate_tenant_id = str(spans[0].attributes["tenant.id"]) if len(spans) > 0 and "tenant.id" in spans[0].attributes else None
    if candidate_tenant_id:
        tenant_id = candidate_tenant_id

    # Get collector configuration (endpoint and headers)
    if endpoint is None:
        endpoint, headers = get_collector_config(tenant_id, collector_service)
        configured_via = "auto-configured"
    else:
        # Manual endpoint override - use basic headers
        headers = {"X-Tenant-Id": tenant_id}
        configured_via = "manually specified"

    total_spans = len(spans)
    logger.debug(f"\n{'='*80}")
    logger.debug("🚀 OTLP Span Export Configuration")
    logger.debug(f"{'='*80}")
    logger.debug(f"Collector service:    {collector_service or os.getenv('OTEL_COLLECTOR_SERVICE', 'jaeger')}")
    logger.debug(f"Endpoint ({configured_via}): {endpoint}")
    logger.debug(f"Total spans:          {total_spans}")
    logger.debug(f"Batch size:           {batch_size}")
    logger.debug(f"Tenant ID:            {tenant_id}")
    logger.debug(f"Sanitized service name: {service_name}")

    # Create and configure the TracerProvider once
    resource = Resource.create({
        "service.name": service_name,
        "tenant.id": tenant_id
    })
    provider = TracerProvider(resource=resource)

    # Create exporter and processor once, outside the batch loop
    if endpoint.startswith("http"):
        logger.debug("Exporter type:        HTTP")
        logger.debug("Headers:")
        for key, value in headers.items():
            if key == "Authorization":
                # Mask the auth token
                logger.debug(f"  {key}: {value[:20]}...***")
            else:
                logger.debug(f"  {key}: {value}")
        logger.debug("Timeout:              30s")
        logger.debug(f"{'='*80}\n")

        exporter = OTLPSpanExporter(
            endpoint=endpoint,
            headers=headers,
            timeout=30
        )
    else:
        logger.debug("Exporter type:        gRPC")
        logger.debug(f"Endpoint:             {endpoint}")
        logger.debug(f"Headers:              x-tenant-id: {tenant_id}")
        logger.debug("Insecure:             True")
        logger.debug("Timeout:              30s")
        logger.debug(f"{'='*80}\n")

        exporter = GRPCSpanExporter(
            endpoint=endpoint,
            headers=(("x-tenant-id", tenant_id),),  # ✅ Use actual tenant_id
            insecure=True,
            timeout=30
        )

    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    # Track earliest time across all spans
    earliest_time = None

    # Process spans in batches
    for batch_start in range(0, len(spans), batch_size):
        batch_end = min(batch_start + batch_size, len(spans))
        current_batch = spans[batch_start:batch_end]

        logger.debug(f"Processing batch {batch_start//batch_size + 1}/{(total_spans + batch_size - 1)//batch_size}: spans {batch_start+1}-{batch_end}")

        # Convert batch spans to OTLP spans
        otlp_spans = []
        for span in current_batch:
            # logger.debug(f"Processing span: {span.name} (ID: {span.context.span_id})")

            # Create span context
            trace_id = hex_to_bytes(span.context.trace_id)
            span_id = hex_to_bytes(span.context.span_id)

            context = SpanContext(
                trace_id=int.from_bytes(trace_id, byteorder='big'),
                span_id=int.from_bytes(span_id, byteorder='big'),
                is_remote=True,
                trace_flags=TraceFlags.SAMPLED,  # Explicitly set sampling
                trace_state=TraceState()
            )

            # Set parent if exists
            parent_context = None
            if span.parent_id:
                parent_id = hex_to_bytes(span.parent_id)
                parent_context = SpanContext(
                    trace_id=int.from_bytes(trace_id, byteorder='big'),
                    span_id=int.from_bytes(parent_id, byteorder='big'),
                    is_remote=True,
                    trace_flags=TraceFlags.SAMPLED,
                    trace_state=TraceState()
                )

            # Create span
            start_time = TraceLogParser.parse_timestamp(span.start_time)
            span_events = []
            for event in span.events:
                span_events.append(Event(event.name, event.attributes, int(event.timestamp.timestamp())))

            otlp_span = ReadableSpan(
                name=span.name,
                context=context,
                parent=parent_context,
                kind=getattr(SpanKind, span.kind.split('.')[-1]),
                resource=resource,
                attributes=span.raw_attributes,
                events=span_events,
                links=[],
                start_time=start_time,
                end_time=TraceLogParser.parse_timestamp(span.end_time)
            )

            otlp_spans.append(otlp_span)
            if earliest_time is None or earliest_time > start_time:
                earliest_time = start_time

        logger.debug(f"Attempting to export batch with {len(otlp_spans)} spans")
        # Export the batch
        try:
            result = exporter.export(otlp_spans)
            logger.debug(f"Export result for batch {batch_start//batch_size + 1}: {result}")

            # Check for failure and provide more details
            from opentelemetry.sdk.trace.export import SpanExportResult
            if result == SpanExportResult.FAILURE:
                logger.error("❌ EXPORT FAILED - Endpoint: {endpoint}")

        except Exception as e:
            logger.error(f"❌ Error exporting batch {batch_start//batch_size + 1}:")
            logger.error(f"   Exception type: {type(e).__name__}")
            logger.error(f"   Exception message: {e}")
            import traceback
            logger.error("   Stack trace:")
            traceback.print_exc()
            # Continue with the next batch instead of failing completely

        # Add a small delay between batches to avoid overwhelming the server
        import time
        time.sleep(1)

    # Shutdown exporter and processor once at the end
    processor.shutdown()
    exporter.shutdown()
    provider.shutdown()

    return service_name, earliest_time
