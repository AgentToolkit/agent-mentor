import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';

const TreeNode = ({ name, value, depth = 0, 'data-testid': dataTestId }) => {
  const [isExpanded, setIsExpanded] = useState(depth < 2); // Auto-expand first 2 levels
  const isObject = typeof value === 'object' && value !== null;
  const hasChildren = isObject && Object.keys(value).length > 0;
  const defaultTestId = `tree-node-${name.toLowerCase()}-depth-${depth}`;

  // Limit maximum indentation to prevent excessive right-scrolling
  const maxDepth = 6;
  const effectiveDepth = Math.min(depth, maxDepth);
  const indentSize = effectiveDepth * 12; // Reduced from 15px to 12px

  const toggleExpand = () => setIsExpanded(!isExpanded);

  return (
    <div
      style={{ marginLeft: `${indentSize}px` }}
      className="max-w-full" // Changed from min-w-fit to max-w-full
      data-testid={dataTestId || defaultTestId}
    >
      {depth !== 0 && (
        <div className="flex items-start gap-2 mb-1">
          <div className="w-5 flex justify-start flex-shrink-0">
            {hasChildren && (
              <button
                onClick={toggleExpand}
                className="text-sm hover:bg-gray-200 rounded px-1"
                data-testid="tree-node-expand-button"
              >
                {isExpanded ? '▼' : '▶'}
              </button>
            )}
          </div>
          <span className="font-semibold text-gray-700 flex-shrink-0">{name}:</span>
          {!isObject && (
            <div className="flex-1 min-w-0">
              {' '}
              {/* min-w-0 allows flex item to shrink */}
              <div className="break-words overflow-wrap-anywhere">
                <ReactMarkdown
                  components={{
                    // Ensure markdown content wraps properly
                    p: ({ children }) => <span className="inline">{children}</span>,
                    code: ({ children }) => (
                      <code className="bg-gray-100 px-1 rounded text-xs break-all">{children}</code>
                    ),
                  }}
                >
                  {String(value)}
                </ReactMarkdown>
              </div>
            </div>
          )}
        </div>
      )}

      {hasChildren && (isExpanded || depth === 0) && (
        <div className="space-y-1">
          {Object.entries(value).map(([key, val]) => (
            <TreeNode key={key} name={key} value={val} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
};

export default TreeNode;
