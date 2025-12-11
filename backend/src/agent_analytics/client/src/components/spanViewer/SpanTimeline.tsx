import React, { useRef, useEffect } from "react";
import type { SpanNode } from "../constants/jaeger";
import { calculateSpanPosition, formatDuration } from "../utils/traceUtils";
import SpanDetails from "./SpanDetails";

interface SpanTimelineProps {
  spans: SpanNode[];
  traceStartTime: number;
  traceDuration: number;
  hoveredSpanId: string | null;
  onSpanHover: (spanId: string | null) => void;
  selectedSpanId: string | null;
  onSpanClick: (spanId: string | null) => void;
  onDetailsHeightChange: (height: number) => void;
}

// Map to store span kind to color index mapping (shared across all spans)
const spanKindColorMap = new Map<string, number>();
let nextColorIndex = 0;

const colors = [
  "#1890ff", // blue
  "#52c41a", // green
  "#13c2c2", // cyan
  "#fa8c16", // orange
  "#eb2f96", // magenta
  "#722ed1", // purple
];

interface SpanBarProps {
  span: SpanNode;
  traceStartTime: number;
  traceDuration: number;
  isHovered: boolean;
  onSpanHover: (spanId: string | null) => void;
  isSelected: boolean;
  onSpanClick: (spanId: string | null) => void;
  onDetailsHeightChange: (height: number) => void;
}

const SpanBar: React.FC<SpanBarProps> = ({
  span,
  traceStartTime,
  traceDuration,
  isHovered,
  onSpanHover,
  isSelected,
  onSpanClick,
  onDetailsHeightChange,
}) => {
  const detailsRef = useRef<HTMLDivElement>(null);
  const { left, width } = calculateSpanPosition(span, traceStartTime, traceDuration);

  // Extract span kind from tags
  const getSpanKind = (span: SpanNode): string => {
    const kindTag = span.tags.find((tag) => tag.key === "span.kind" || tag.key === "traceloop.span.kind");
    return kindTag?.value || "unknown";
  };

  // Get color for span kind (assigns colors in round-robin order)
  const getSpanKindColor = (spanKind: string): string => {
    if (!spanKindColorMap.has(spanKind)) {
      spanKindColorMap.set(spanKind, nextColorIndex);
      nextColorIndex = (nextColorIndex + 1) % colors.length;
    }

    const colorIndex = spanKindColorMap.get(spanKind)!;
    return colors[colorIndex];
  };

  const spanKind = getSpanKind(span);
  const barColor = getSpanKindColor(spanKind);
  const durationText = formatDuration(span.duration);

  // Determine duration placement
  // Show on right if bar doesn't extend too far right (< 85%)
  const showDurationRight = left + width < 85;
  // Show on left only if right isn't available and there's space on left
  const showDurationLeft = !showDurationRight && left > 8;

  const handleClick = () => {
    onSpanClick(isSelected ? null : span.spanID);
  };

  // Measure and report the height of the details panel
  useEffect(() => {
    if (isSelected && detailsRef.current) {
      const height = detailsRef.current.offsetHeight;
      onDetailsHeightChange(height);
    } else if (!isSelected) {
      onDetailsHeightChange(0);
    }
  }, [isSelected, onDetailsHeightChange]);

  // Use ResizeObserver to track dynamic height changes
  useEffect(() => {
    if (isSelected && detailsRef.current) {
      const resizeObserver = new ResizeObserver((entries) => {
        for (const entry of entries) {
          onDetailsHeightChange(entry.target.clientHeight);
        }
      });

      resizeObserver.observe(detailsRef.current);

      return () => {
        resizeObserver.disconnect();
      };
    }
  }, [isSelected, onDetailsHeightChange]);

  return (
    <>
      <div
        className={`h-8 border-b border-slate-200 relative transition-colors duration-150 cursor-pointer ${
          isSelected ? "bg-blue-50" : isHovered ? "bg-blue-50/50" : "bg-white hover:bg-blue-50/30"
        }`}
        onMouseEnter={() => onSpanHover(span.spanID)}
        onMouseLeave={() => onSpanHover(null)}
        onClick={handleClick}
      >
        {showDurationLeft && (
          <div
            className="absolute top-1/2 -translate-y-1/2 -translate-x-full pr-1 text-[10px] text-slate-600 font-['Courier_New',monospace] whitespace-nowrap font-medium pointer-events-none"
            style={{ left: `${left - 0.5}%` }}
          >
            {durationText}
          </div>
        )}
        <div
          className="absolute top-1/2 -translate-y-1/2 h-[12px] rounded-sm cursor-pointer transition-all duration-150 flex items-center px-1 shadow-[0_1px_3px_rgba(0,0,0,0.15)] min-w-[2px] hover:h-[22px] hover:shadow-[0_2px_5px_rgba(0,0,0,0.25)] hover:z-20 z-10 pointer-events-none"
          style={{
            left: `${left}%`,
            width: `${Math.max(width, 0.1)}%`,
            backgroundColor: barColor,
          }}
          title={`${span.operationName} (${span.service}) - ${durationText}`}
        />
        {showDurationRight && (
          <div
            className="absolute top-1/2 -translate-y-1/2 pl-1 text-[10px] text-slate-600 font-['Courier_New',monospace] whitespace-nowrap font-medium pointer-events-none"
            style={{ left: `${left + width + 0.5}%` }}
          >
            {durationText}
          </div>
        )}
      </div>
      {isSelected && (
        <div ref={detailsRef} className="border-b border-slate-200 bg-slate-100/50">
          <SpanDetails span={span} traceStartTime={traceStartTime} />
        </div>
      )}
    </>
  );
};

const SpanTimeline: React.FC<SpanTimelineProps> = ({
  spans,
  traceStartTime,
  traceDuration,
  hoveredSpanId,
  onSpanHover,
  selectedSpanId,
  onSpanClick,
  onDetailsHeightChange,
}) => {
  // Generate vertical guide lines matching the ruler markers
  const numMarkers = 10;
  const markers = Array.from({ length: numMarkers + 1 }, (_, i) => {
    const position = (i / numMarkers) * 100;
    return position;
  });

  return (
    <div className="flex flex-col relative min-w-full">
      {/* Vertical guide lines layer - above span backgrounds but below hover states */}
      <div className="absolute top-0 left-0 right-0 bottom-0 pointer-events-none z-[5]">
        {markers.map((position, index) => (
          <div
            key={index}
            className="absolute top-0 bottom-0 w-px bg-slate-100 -translate-x-1/2"
            style={{ left: `${position}%` }}
          />
        ))}
      </div>
      {/* Span rows layer */}
      <div className="flex flex-col relative">
        {spans.map((span) => (
          <SpanBar
            key={span.spanID}
            span={span}
            traceStartTime={traceStartTime}
            traceDuration={traceDuration}
            isHovered={hoveredSpanId === span.spanID}
            onSpanHover={onSpanHover}
            isSelected={selectedSpanId === span.spanID}
            onSpanClick={onSpanClick}
            onDetailsHeightChange={onDetailsHeightChange}
          />
        ))}
      </div>
    </div>
  );
};

export default SpanTimeline;
