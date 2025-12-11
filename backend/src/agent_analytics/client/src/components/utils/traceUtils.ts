import type { JaegerTrace, JaegerSpan, SpanNode } from '../constants/jaeger';

/**
 * Build a hierarchical tree of spans from a flat list
 */
export function buildSpanTree(trace: JaegerTrace): SpanNode[] {
  const spanMap = new Map<string, SpanNode>();
  const rootSpans: SpanNode[] = [];

  // First pass: create SpanNode objects
  trace.spans.forEach(span => {
    const service = trace.processes[span.processID]?.serviceName || 'unknown';
    const node: SpanNode = {
      ...span,
      depth: 0,
      children: [],
      hasChildren: false,
      isExpanded: true,
      service
    };
    spanMap.set(span.spanID, node);
  });

  // Second pass: build parent-child relationships
  trace.spans.forEach(span => {
    const node = spanMap.get(span.spanID)!;

    // Find parent reference
    const parentRef = span.references.find(ref => ref.refType === 'CHILD_OF');

    if (parentRef) {
      const parent = spanMap.get(parentRef.spanID);
      if (parent) {
        parent.children.push(node);
        parent.hasChildren = true;
      } else {
        rootSpans.push(node);
      }
    } else {
      rootSpans.push(node);
    }
  });

  // Third pass: calculate depths
  const calculateDepth = (node: SpanNode, depth: number) => {
    node.depth = depth;
    node.children.forEach(child => calculateDepth(child, depth + 1));
  };

  rootSpans.forEach(root => calculateDepth(root, 0));

  // Sort children by start time
  const sortChildren = (node: SpanNode) => {
    node.children.sort((a, b) => a.startTime - b.startTime);
    node.children.forEach(sortChildren);
  };

  rootSpans.forEach(sortChildren);
  rootSpans.sort((a, b) => a.startTime - b.startTime);

  return rootSpans;
}

/**
 * Flatten the tree into a list respecting expand/collapse state
 */
export function flattenSpanTree(roots: SpanNode[]): SpanNode[] {
  const result: SpanNode[] = [];

  const traverse = (node: SpanNode) => {
    result.push(node);
    if (node.isExpanded) {
      node.children.forEach(traverse);
    }
  };

  roots.forEach(traverse);
  return result;
}

/**
 * Get trace time bounds
 */
export function getTraceBounds(trace: JaegerTrace): { startTime: number; endTime: number; duration: number } {
  if (trace.spans.length === 0) {
    return { startTime: 0, endTime: 0, duration: 0 };
  }

  const startTime = Math.min(...trace.spans.map(s => s.startTime));
  const endTime = Math.max(...trace.spans.map(s => s.startTime + s.duration));
  const duration = endTime - startTime;

  return { startTime, endTime, duration };
}

/**
 * Format microseconds to human-readable duration with accurate values
 */
export function formatDuration(microseconds: number): string {
  if (microseconds === 0) {
    return '0μs';
  }

  const ms = microseconds / 1000;
  const seconds = ms / 1000;
  const minutes = seconds / 60;
  const hours = minutes / 60;

  if (hours >= 1) {
    // Show hours with appropriate precision
    return hours >= 10 ? `${hours.toFixed(1)}h` : `${hours.toFixed(2)}h`;
  } else if (minutes >= 1) {
    // Show minutes with appropriate precision
    return minutes >= 10 ? `${minutes.toFixed(1)}m` : `${minutes.toFixed(2)}m`;
  } else if (seconds >= 1) {
    // Show seconds with appropriate precision
    return seconds >= 10 ? `${seconds.toFixed(1)}s` : `${seconds.toFixed(2)}s`;
  } else if (ms >= 1) {
    // Show milliseconds with appropriate precision
    return ms >= 10 ? `${ms.toFixed(1)}ms` : `${ms.toFixed(2)}ms`;
  } else if (microseconds >= 1) {
    // Show microseconds as integer
    return `${Math.round(microseconds)}μs`;
  } else {
    // Sub-microsecond (very rare, but handle it)
    return `${microseconds.toFixed(3)}μs`;
  }
}

/**
 * Calculate the position and width of a span in the timeline (as percentages)
 */
export function calculateSpanPosition(
  span: JaegerSpan,
  traceStartTime: number,
  traceDuration: number
): { left: number; width: number } {
  const relativeStart = span.startTime - traceStartTime;
  const left = (relativeStart / traceDuration) * 100;
  const width = (span.duration / traceDuration) * 100;

  return { left, width };
}
