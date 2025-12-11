import type { JaegerTrace, JaegerSpan } from '../constants/jaeger';

/**
 * Convert custom trace format to Jaeger format
 */
export function convertToJaegerFormat(customTrace: any): JaegerTrace {
  if (!customTrace.spans || customTrace.spans.length === 0) {
    throw new Error('No spans found in trace data');
  }

  // Deduplicate spans by span_id (keep the first occurrence)
  const seenSpanIds = new Set<string>();
  const uniqueSpans = customTrace.spans.filter((span: any) => {
    const spanId = span.context?.span_id || span.element_id || 'unknown';
    if (seenSpanIds.has(spanId)) {
      return false; // Skip duplicate
    }
    seenSpanIds.add(spanId);
    return true;
  });

  // Extract trace ID from first span
  const traceID = uniqueSpans[0].context?.trace_id || 'unknown';

  // Build processes map from unique service names
  const servicesMap = new Map<string, string>();
  const processes: Record<string, any> = {};

  uniqueSpans.forEach((span: any) => {
    const serviceName = span.resource?.attributes?.service_name || 'unknown';
    if (!servicesMap.has(serviceName)) {
      const processID = `p${servicesMap.size + 1}`;
      servicesMap.set(serviceName, processID);
      processes[processID] = {
        serviceName,
        tags: []
      };
    }
  });

  /**
   * Parse ISO timestamp with microsecond precision
   * Format: 2025-09-29T19:28:42.736944
   */
  const parseISOWithMicroseconds = (isoString: string): number => {
    if (!isoString) return 0;

    // Parse the ISO string manually to preserve microsecond precision
    const match = isoString.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})\.(\d+)/);
    if (!match) {
      // Fallback to Date parsing if format doesn't match
      return new Date(isoString).getTime() * 1000;
    }

    const [, year, month, day, hour, minute, second, fractional] = match;

    // Create date for the base timestamp (without fractional seconds)
    const baseDate = Date.UTC(
      parseInt(year),
      parseInt(month) - 1,
      parseInt(day),
      parseInt(hour),
      parseInt(minute),
      parseInt(second)
    );

    // Convert milliseconds to microseconds
    const baseMicroseconds = baseDate * 1000;

    // Parse fractional seconds to microseconds
    // Pad or truncate to 6 digits (microseconds)
    const fractionalStr = fractional.padEnd(6, '0').slice(0, 6);
    const microseconds = parseInt(fractionalStr);

    return baseMicroseconds + microseconds;
  };

  // Convert spans (use uniqueSpans instead of customTrace.spans)
  const jaegerSpans: JaegerSpan[] = uniqueSpans.map((span: any) => {
    const serviceName = span.resource?.attributes?.service_name || 'unknown';
    const processID = servicesMap.get(serviceName) || 'p1';

    // Convert ISO timestamp with microsecond precision to microseconds since epoch
    const startTime = parseISOWithMicroseconds(span.start_time);
    const endTime = parseISOWithMicroseconds(span.end_time);
    const duration = endTime - startTime;

    // Build references from parent_id
    const references = [];
    if (span.parent_id) {
      references.push({
        refType: 'CHILD_OF' as const,
        traceID: span.context?.trace_id || traceID,
        spanID: span.parent_id
      });
    }

    // Convert attributes to tags
    const tags = [];
    if (span.raw_attributes) {
      for (const [key, value] of Object.entries(span.raw_attributes)) {
        tags.push({
          key,
          type: 'string' as const,
          value: String(value)
        });
      }
    }

    return {
      traceID: span.context?.trace_id || traceID,
      spanID: span.context?.span_id || span.element_id || 'unknown',
      operationName: span.name || 'unknown',
      references,
      startTime,
      duration,
      tags,
      logs: [],
      processID,
      warnings: []
    };
  });

  return {
    traceID,
    spans: jaegerSpans,
    processes,
    warnings: []
  };
}
