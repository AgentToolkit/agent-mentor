import React, { useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";
import type { SpanNode } from "../constants/jaeger";
import { formatDuration } from "../utils/traceUtils";

interface SpanDetailsProps {
  span: SpanNode;
  traceStartTime: number;
}

interface JsonViewerProps {
  data: any;
  label: string;
}

const JsonViewer: React.FC<JsonViewerProps> = ({ data, label }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  // Try to parse if it's a string that looks like JSON
  const parseValue = (value: any): any => {
    if (typeof value === "string") {
      try {
        return JSON.parse(value);
      } catch {
        return value;
      }
    }
    return value;
  };

  const renderValue = (value: any, depth: number = 0): React.ReactNode => {
    const parsedValue = parseValue(value);

    if (parsedValue === null || parsedValue === undefined) {
      return <span className="text-gray-500 italic">null</span>;
    }

    if (typeof parsedValue === "boolean") {
      return <span className="text-purple-600 font-medium">{String(parsedValue)}</span>;
    }

    if (typeof parsedValue === "number") {
      return <span className="text-blue-600 font-medium">{parsedValue}</span>;
    }

    if (typeof parsedValue === "string") {
      // Don't show quotes for simple strings
      if (parsedValue.length < 100) {
        return <span className="text-green-700">{parsedValue}</span>;
      }
      // For long strings, show them in a scrollable area
      return (
        <div className="text-green-700 max-h-32 overflow-y-auto text-sm font-mono bg-gray-50 p-2 rounded border border-gray-200 mt-1">
          {parsedValue}
        </div>
      );
    }

    if (Array.isArray(parsedValue)) {
      return <ExpandableJson data={parsedValue} isArray={true} depth={depth} />;
    }

    if (typeof parsedValue === "object") {
      return <ExpandableJson data={parsedValue} isArray={false} depth={depth} />;
    }

    return <span>{String(parsedValue)}</span>;
  };

  const ExpandableJson: React.FC<{ data: any; isArray: boolean; depth: number }> = ({ data, isArray, depth }) => {
    const [expanded, setExpanded] = useState(depth === 0);
    const entries = isArray ? data : Object.entries(data);
    const preview = isArray ? `Array(${data.length})` : `Object(${Object.keys(data).length})`;

    return (
      <div className="font-mono text-sm">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 hover:bg-blue-50/50 px-1 rounded text-slate-700 transition-colors"
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          <span className="text-slate-600">{preview}</span>
        </button>
        {expanded && (
          <div className="ml-4 border-l-2 border-slate-200 pl-3 mt-1 space-y-1">
            {isArray
              ? data.map((item: any, index: number) => (
                  <div key={index} className="py-0.5">
                    <span className="text-slate-500">[{index}]: </span>
                    {renderValue(item, depth + 1)}
                  </div>
                ))
              : entries.map(([key, value]: [string, any]) => (
                  <div key={key} className="py-0.5">
                    <span className="text-blue-700 font-medium">{key}: </span>
                    {renderValue(value, depth + 1)}
                  </div>
                ))}
          </div>
        )}
      </div>
    );
  };

  if (!data || (typeof data === "object" && Object.keys(data).length === 0)) {
    return null;
  }

  return (
    <div className="border-t border-slate-200 py-3">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 w-full text-left hover:bg-blue-50/50 px-2 py-1 rounded transition-colors"
      >
        {isExpanded ? (
          <ChevronDown size={16} className="text-slate-700" />
        ) : (
          <ChevronRight size={16} className="text-slate-700" />
        )}
        <span className="font-semibold text-sm text-slate-800">{label}</span>
      </button>
      {isExpanded && <div className="mt-2 px-2">{renderValue(data, 0)}</div>}
    </div>
  );
};

const SpanDetails: React.FC<SpanDetailsProps> = ({ span, traceStartTime }) => {
  const relativeStartTime = span.startTime - traceStartTime;

  // Filter out tags that are already shown in the main attributes
  const mainTags = span.tags.filter(
    (tag) =>
      !tag.key.startsWith("traceloop.entity.") &&
      !tag.key.startsWith("traceloop.association.") &&
      !tag.key.startsWith("traceloop.span.") &&
      !tag.key.startsWith("traceloop.workflow.")
  );

  return (
    <div className="bg-white border-t-2 border-blue-600 shadow-sm">
      {/* Header Section */}
      <div className="px-4 py-3 bg-blue-50/50 border-b border-slate-200">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-base text-slate-900">{span.operationName}</h3>
          <div className="flex items-center gap-6 text-sm">
            <div>
              <span className="text-slate-600">Service: </span>
              <span className="font-medium text-blue-700">{span.service}</span>
            </div>
            <div>
              <span className="text-slate-600">Duration: </span>
              <span className="font-medium text-blue-700">{formatDuration(span.duration)}</span>
            </div>
            <div>
              <span className="text-slate-600">Start Time: </span>
              <span className="font-medium text-blue-700">{formatDuration(relativeStartTime)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Content Section */}
      <div className="px-4 py-3 max-h-96 overflow-y-auto bg-slate-50">
        {/* Top-level Attributes */}
        <div className="space-y-2">
          <div className="grid grid-cols-[150px_1fr] gap-2 text-sm">
            <span className="text-slate-600 font-medium">Span ID:</span>
            <span className="font-mono text-blue-700">{span.spanID}</span>
          </div>
          <div className="grid grid-cols-[150px_1fr] gap-2 text-sm">
            <span className="text-slate-600 font-medium">Trace ID:</span>
            <span className="font-mono text-blue-700">{span.traceID}</span>
          </div>
          {span.processID && (
            <div className="grid grid-cols-[150px_1fr] gap-2 text-sm">
              <span className="text-slate-600 font-medium">Process ID:</span>
              <span className="font-mono text-blue-700">{span.processID}</span>
            </div>
          )}
        </div>

        {/* References */}
        {span.references && span.references.length > 0 && (
          <div className="mt-4 pt-3 border-t border-slate-200">
            <h4 className="font-semibold text-sm text-slate-800 mb-2">References</h4>
            <div className="space-y-2">
              {span.references.map((ref, index) => (
                <div key={index} className="text-sm pl-2">
                  <span className="text-slate-600">{ref.refType}: </span>
                  <span className="font-mono text-blue-700">{ref.spanID}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tags (filtered) */}
        {mainTags.length > 0 && (
          <div className="mt-4 pt-3 border-t border-slate-200">
            <h4 className="font-semibold text-sm text-slate-800 mb-2">Tags</h4>
            <div className="space-y-2">
              {mainTags.map((tag, index) => (
                <div key={index} className="grid grid-cols-[200px_1fr] gap-2 text-sm">
                  <span className="text-slate-600 font-mono text-xs truncate" title={tag.key}>
                    {tag.key}
                  </span>
                  <span className="text-blue-700 font-mono text-xs break-all">
                    {typeof tag.value === "string" ? tag.value : JSON.stringify(tag.value)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Logs */}
        {span.logs && span.logs.length > 0 && <JsonViewer data={span.logs} label="Logs" />}

        {/* Process/Resource Information */}
        <JsonViewer data={span.tags.find((t) => t.key === "resource")?.value} label="Resource" />

        {/* Raw Attributes - try to find from tags */}
        {(() => {
          const rawAttrsTag = span.tags.find((t) => t.key === "raw_attributes");
          const rawAttrs = rawAttrsTag?.value;

          // Build raw attributes from traceloop tags
          const traceloopAttrs: Record<string, any> = {};
          span.tags.forEach((tag) => {
            if (tag.key.startsWith("traceloop.")) {
              traceloopAttrs[tag.key] = tag.value;
            }
          });

          const attributesToShow = rawAttrs || (Object.keys(traceloopAttrs).length > 0 ? traceloopAttrs : null);

          return attributesToShow ? <JsonViewer data={attributesToShow} label="Attributes" /> : null;
        })()}
      </div>
    </div>
  );
};

export default SpanDetails;
