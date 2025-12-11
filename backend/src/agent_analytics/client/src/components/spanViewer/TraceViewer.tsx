import React, { useState, useMemo, useRef, useCallback } from 'react';
import { ChevronRight, ChevronDown, ChevronsRight, ChevronsDown } from 'lucide-react';
import type { JaegerTrace, SpanNode } from '../constants/jaeger';
import { buildSpanTree, flattenSpanTree, getTraceBounds } from '../utils/traceUtils';
import TimelineRuler from './TimelineRuler';
import SpanList from './SpanList';
import SpanTimeline from './SpanTimeline';

interface TraceViewerProps {
  trace: JaegerTrace;
}

const TraceViewer: React.FC<TraceViewerProps> = ({ trace }) => {
  const [spanTree, setSpanTree] = useState<SpanNode[]>(() => buildSpanTree(trace));
  const [leftColumnWidth, setLeftColumnWidth] = useState(400);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const leftScrollRef = useRef<HTMLDivElement>(null);
  const rightScrollRef = useRef<HTMLDivElement>(null);
  const rulerScrollRef = useRef<HTMLDivElement>(null);

  // Rebuild span tree whenever trace data changes
  React.useEffect(() => {
    setSpanTree(buildSpanTree(trace));
    // Reset UI state when trace changes
    setSelectedSpanId(null);
    setHoveredSpanId(null);
  }, [trace]);

  const { startTime, duration } = useMemo(() => getTraceBounds(trace), [trace]);

  const visibleSpans = useMemo(() => flattenSpanTree(spanTree), [spanTree]);

  // Sync scrolling between left and right columns
  const handleLeftScroll = useCallback(() => {
    if (leftScrollRef.current && rightScrollRef.current) {
      rightScrollRef.current.scrollTop = leftScrollRef.current.scrollTop;
    }
  }, []);

  const handleRightScroll = useCallback(() => {
    if (leftScrollRef.current && rightScrollRef.current) {
      leftScrollRef.current.scrollTop = rightScrollRef.current.scrollTop;
    }
  }, []);

  const [hoveredSpanId, setHoveredSpanId] = useState<string | null>(null);
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(null);
  const [detailsHeight, setDetailsHeight] = useState<number>(0);

  const handleMouseDown = useCallback(() => {
    setIsDragging(true);
  }, []);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging || !containerRef.current) return;

    const rect = containerRef.current.getBoundingClientRect();
    const newWidth = e.clientX - rect.left;

    // Constrain width between 200px and 800px
    if (newWidth >= 200 && newWidth <= 800) {
      setLeftColumnWidth(newWidth);
    }
  }, [isDragging]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  React.useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging, handleMouseMove, handleMouseUp]);

  const handleToggleExpand = (spanId: string) => {
    const toggleNode = (nodes: SpanNode[]): SpanNode[] => {
      return nodes.map(node => {
        if (node.spanID === spanId) {
          return { ...node, isExpanded: !node.isExpanded };
        }
        if (node.children.length > 0) {
          return { ...node, children: toggleNode(node.children) };
        }
        return node;
      });
    };

    setSpanTree(toggleNode(spanTree));
  };

  const expandAll = useCallback(() => {
    const expandNodes = (nodes: SpanNode[]): SpanNode[] => {
      return nodes.map(node => ({
        ...node,
        isExpanded: true,
        children: expandNodes(node.children)
      }));
    };
    setSpanTree(expandNodes(spanTree));
  }, [spanTree]);

  const collapseAll = useCallback(() => {
    const collapseNodes = (nodes: SpanNode[]): SpanNode[] => {
      return nodes.map(node => ({
        ...node,
        isExpanded: false,
        children: collapseNodes(node.children)
      }));
    };
    setSpanTree(collapseNodes(spanTree));
  }, [spanTree]);

  const expandOneLevel = useCallback(() => {
    const expandLevel = (nodes: SpanNode[], currentDepth: number, targetDepth: number): SpanNode[] => {
      return nodes.map(node => {
        if (currentDepth === targetDepth && node.hasChildren && !node.isExpanded) {
          return {
            ...node,
            isExpanded: true,
            children: node.children
          };
        }
        if (node.children.length > 0) {
          return {
            ...node,
            children: expandLevel(node.children, currentDepth + 1, targetDepth)
          };
        }
        return node;
      });
    };

    // Find the shallowest collapsed depth
    const findMinCollapsedDepth = (nodes: SpanNode[], currentDepth: number): number => {
      let minDepth = Infinity;
      for (const node of nodes) {
        if (!node.isExpanded && node.hasChildren) {
          minDepth = Math.min(minDepth, currentDepth);
        }
        if (node.children.length > 0) {
          minDepth = Math.min(minDepth, findMinCollapsedDepth(node.children, currentDepth + 1));
        }
      }
      return minDepth;
    };

    const targetDepth = findMinCollapsedDepth(spanTree, 0);
    if (targetDepth !== Infinity) {
      setSpanTree(expandLevel(spanTree, 0, targetDepth));
    }
  }, [spanTree]);

  const collapseOneLevel = useCallback(() => {
    const collapseLevel = (nodes: SpanNode[], currentDepth: number, targetDepth: number): SpanNode[] => {
      return nodes.map(node => {
        if (currentDepth === targetDepth && node.hasChildren) {
          return {
            ...node,
            isExpanded: false,
            children: collapseLevel(node.children, currentDepth + 1, targetDepth)
          };
        }
        return {
          ...node,
          children: collapseLevel(node.children, currentDepth + 1, targetDepth)
        };
      });
    };

    // Find the max expanded depth
    const findMaxExpandedDepth = (nodes: SpanNode[], currentDepth: number): number => {
      let maxDepth = -1;
      for (const node of nodes) {
        if (node.isExpanded && node.hasChildren) {
          maxDepth = Math.max(maxDepth, currentDepth);
        }
        if (node.isExpanded && node.children.length > 0) {
          maxDepth = Math.max(maxDepth, findMaxExpandedDepth(node.children, currentDepth + 1));
        }
      }
      return maxDepth;
    };

    const targetDepth = findMaxExpandedDepth(spanTree, 0);
    if (targetDepth >= 0) {
      setSpanTree(collapseLevel(spanTree, 0, targetDepth));
    }
  }, [spanTree]);

  // Get unique service names
  const serviceNames = useMemo(() => {
    const services = new Set<string>();
    Object.values(trace.processes).forEach(p => services.add(p.serviceName));
    return Array.from(services).join(', ');
  }, [trace.processes]);

  return (
    <div className="bg-white rounded shadow-sm overflow-hidden border border-slate-200">
      <div className={`flex flex-col h-[calc(100vh-200px)] relative ${isDragging ? 'select-none' : ''}`} ref={containerRef}>
        <div className="flex relative h-auto border-b-2 border-slate-300">
          <div className="flex-shrink-0 bg-white overflow-hidden" style={{ width: `${leftColumnWidth}px` }}>
            <div className="flex py-2.5 pr-2.5 bg-slate-100 border-b border-slate-200 font-semibold text-xs text-slate-700 uppercase h-[50px] items-center gap-2.5">
              <div className="flex-1 pl-2.5">{trace.spans.length} spans</div>
              <div className="flex gap-1">
                <button
                  className="bg-transparent border-none cursor-pointer p-1 text-slate-600 flex items-center justify-center transition-all duration-150 rounded hover:bg-blue-100 hover:text-slate-900 active:bg-blue-200"
                  onClick={collapseOneLevel}
                  title="Collapse one level"
                  aria-label="Collapse one level"
                >
                  <ChevronRight size={16} />
                </button>
                <button
                  className="bg-transparent border-none cursor-pointer p-1 text-slate-600 flex items-center justify-center transition-all duration-150 rounded hover:bg-blue-100 hover:text-slate-900 active:bg-blue-200"
                  onClick={expandOneLevel}
                  title="Expand one level"
                  aria-label="Expand one level"
                >
                  <ChevronDown size={16} />
                </button>
                <button
                  className="bg-transparent border-none cursor-pointer p-1 text-slate-600 flex items-center justify-center transition-all duration-150 rounded hover:bg-blue-100 hover:text-slate-900 active:bg-blue-200"
                  onClick={collapseAll}
                  title="Collapse all"
                  aria-label="Collapse all"
                >
                  <ChevronsRight size={16} />
                </button>
                <button
                  className="bg-transparent border-none cursor-pointer p-1 text-slate-600 flex items-center justify-center transition-all duration-150 rounded hover:bg-blue-100 hover:text-slate-900 active:bg-blue-200"
                  onClick={expandAll}
                  title="Expand all"
                  aria-label="Expand all"
                >
                  <ChevronsDown size={16} />
                </button>
              </div>
            </div>
          </div>
          <div
            className="absolute top-0 bottom-0 w-1.5 -ml-[3px] cursor-col-resize z-40 bg-transparent select-none hover:bg-blue-200"
            onMouseDown={handleMouseDown}
            style={{ left: `${leftColumnWidth}px` }}
          />
          <div className="flex-1 relative h-[50px] overflow-hidden bg-gradient-to-b from-slate-50 to-slate-100" ref={rulerScrollRef}>
            <div className="w-full h-full">
              <TimelineRuler traceDuration={duration} traceStartTime={startTime} />
            </div>
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden relative">
          <div
            className="flex-shrink-0 overflow-y-auto bg-white"
            ref={leftScrollRef}
            style={{ width: `${leftColumnWidth}px` }}
            onScroll={handleLeftScroll}
          >
            <SpanList
              spans={visibleSpans}
              onToggleExpand={handleToggleExpand}
              hoveredSpanId={hoveredSpanId}
              onSpanHover={setHoveredSpanId}
              selectedSpanId={selectedSpanId}
              onSpanClick={setSelectedSpanId}
              detailsHeight={detailsHeight}
            />
          </div>
          <div
            className="absolute top-0 bottom-0 w-1.5 -ml-[3px] cursor-col-resize z-40 bg-transparent select-none hover:bg-blue-200"
            onMouseDown={handleMouseDown}
            style={{ left: `${leftColumnWidth}px` }}
          />
          <div
            className="flex-1 overflow-y-auto overflow-x-hidden bg-white [&::-webkit-scrollbar-track]:bg-slate-100"
            ref={rightScrollRef}
            onScroll={handleRightScroll}
          >
            <SpanTimeline
              spans={visibleSpans}
              traceStartTime={startTime}
              traceDuration={duration}
              hoveredSpanId={hoveredSpanId}
              onSpanHover={setHoveredSpanId}
              selectedSpanId={selectedSpanId}
              onSpanClick={setSelectedSpanId}
              onDetailsHeightChange={setDetailsHeight}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default TraceViewer;
