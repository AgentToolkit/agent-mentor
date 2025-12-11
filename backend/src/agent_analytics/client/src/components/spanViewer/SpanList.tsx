import React from "react";
import { ChevronRight, ChevronDown } from "lucide-react";
import type { SpanNode } from "../constants/jaeger";

interface SpanListProps {
  spans: SpanNode[];
  onToggleExpand: (spanId: string) => void;
  hoveredSpanId: string | null;
  onSpanHover: (spanId: string | null) => void;
  selectedSpanId: string | null;
  onSpanClick: (spanId: string | null) => void;
  detailsHeight: number;
}

interface SpanRowProps {
  span: SpanNode;
  onToggleExpand: (spanId: string) => void;
  isHovered: boolean;
  onSpanHover: (spanId: string | null) => void;
  isSelected: boolean;
  onSpanClick: (spanId: string | null) => void;
  detailsHeight: number;
}

const SpanRow: React.FC<SpanRowProps> = ({
  span,
  onToggleExpand,
  isHovered,
  onSpanHover,
  isSelected,
  onSpanClick,
  detailsHeight,
}) => {
  const indentSize = 20; // pixels per depth level

  const handleClick = (e: React.MouseEvent) => {
    // Don't trigger click when clicking the expand button
    if ((e.target as HTMLElement).closest("button[aria-label]")) {
      return;
    }
    // Toggle selection - clicking again closes the details
    onSpanClick(isSelected ? null : span.spanID);
  };

  // Calculate the position of the blue line for this span's depth
  const blueLinePosition = span.depth > 0 ? span.depth * indentSize - 2 : 0; // 10.5 = left-2.5 (10px) + half of w-px

  return (
    <>
      <div
        className={`flex items-center h-8 border-b border-slate-200 cursor-pointer transition-colors duration-150 relative ${
          isHovered && !isSelected ? "bg-blue-50" : "bg-white hover:bg-blue-50/50"
        }`}
        onMouseEnter={() => onSpanHover(span.spanID)}
        onMouseLeave={() => onSpanHover(null)}
        onClick={handleClick}
      >
        {/* Left border for selected span - aligned with blue hierarchy line */}
        {isSelected && (
          <div className="absolute top-0 bottom-0 w-px bg-blue-400 z-20" style={{ left: `${blueLinePosition}px` }} />
        )}

        {/* Blue background starting from the border */}
        {isSelected && (
          <div className="absolute top-0 bottom-0 right-0 bg-blue-100" style={{ left: `${blueLinePosition}px` }} />
        )}

        <div className="flex-1 flex items-center overflow-hidden relative pl-2.5 z-10">
          {/* Render hierarchy lines */}
          {span.depth > 0 && (
            <div className="absolute top-0 bottom-0 left-2.5 pointer-events-none">
              {Array.from({ length: span.depth }).map((_, index) => {
                const isLastLevel = index === span.depth - 1;
                return (
                  <div key={index} className="absolute top-0 bottom-0" style={{ left: `${index * indentSize + 8}px` }}>
                    {/* Vertical line */}
                    <div className={`absolute top-0 bottom-0 w-px ${!isLastLevel ? "bg-slate-300" : "bg-blue-500"}`} />
                    {/* Horizontal line to chevron */}
                    {/* {isLastLevel && (
                      <div
                        className="absolute top-4 w-2 h-px bg-slate-300"
                        style={{ left: '0px' }}
                      />
                    )} */}
                  </div>
                );
              })}
            </div>
          )}

          {/* Indent for depth */}
          <div style={{ width: `${span.depth * indentSize}px`, flexShrink: 0 }} />

          {span.hasChildren && (
            <button
              className="bg-transparent border-none cursor-pointer p-0 text-slate-600 w-4 h-4 flex items-center justify-center flex-shrink-0 hover:text-blue-600 transition-colors z-10"
              onClick={(e) => {
                e.stopPropagation();
                onToggleExpand(span.spanID);
              }}
              aria-label={span.isExpanded ? "Collapse" : "Expand"}
            >
              {span.isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
            </button>
          )}
          {!span.hasChildren && <span className="w-4 flex-shrink-0" />}

          <div
            className={`text-sm text-slate-900 whitespace-nowrap overflow-hidden text-ellipsis flex-1 ml-2 ${
              span.hasChildren && !span.isExpanded ? "font-semibold" : "font-normal"
            }`}
          >
            {span.operationName}
          </div>
        </div>
      </div>
      {isSelected && (
        <div
          className="border-b border-slate-200 relative"
          style={{ height: detailsHeight > 0 ? `${detailsHeight}px` : "400px" }}
        >
          {/* Left border continuing from selected row */}
          <div className="absolute top-0 bottom-0 w-px bg-blue-400" style={{ left: `${blueLinePosition}px` }} />
          {/* Blue background for details panel */}
          <div className="absolute top-0 bottom-0 right-0 bg-blue-50/70" style={{ left: `${blueLinePosition}px` }} />
          {/* Empty spacer to maintain alignment with the timeline details panel */}
          {/* The height should match the SpanDetails panel on the right */}
        </div>
      )}
    </>
  );
};

const SpanList: React.FC<SpanListProps> = ({
  spans,
  onToggleExpand,
  hoveredSpanId,
  onSpanHover,
  selectedSpanId,
  onSpanClick,
  detailsHeight,
}) => {
  return (
    <div className="flex flex-col">
      {spans.map((span) => (
        <SpanRow
          key={span.spanID}
          span={span}
          onToggleExpand={onToggleExpand}
          isHovered={hoveredSpanId === span.spanID}
          onSpanHover={onSpanHover}
          isSelected={selectedSpanId === span.spanID}
          onSpanClick={onSpanClick}
          detailsHeight={detailsHeight}
        />
      ))}
    </div>
  );
};

export default SpanList;
