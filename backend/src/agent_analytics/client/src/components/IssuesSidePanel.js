import React, { useState } from 'react';
import { AlertTriangle, AlertCircle, Info, FileText, ChevronRight, Clock, Tag } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

const IssuesSidePanel = ({ issue, onTaskSelect, OverlayModal }) => {
  const [isDescriptionModalOpen, setIsDescriptionModalOpen] = useState(false);

  if (!issue) {
    return (
      <div className="bg-white p-6 mb-4 border-t-4 border-solid border-gray-300 min-h-screen">
        Select an issue to view details
      </div>
    );
  }

  // Get issue level icon and color
  const getLevelInfo = (level) => {
    switch (level) {
      case 'CRITICAL':
        return {
          icon: <AlertCircle className="w-5 h-5 text-red-600" />,
          colorClass: 'border-red-600',
          badgeClass: 'bg-red-100 text-red-800',
        };
      case 'ERROR':
        return {
          icon: <AlertCircle className="w-5 h-5 text-red-500" />,
          colorClass: 'border-red-500',
          badgeClass: 'bg-red-50 text-red-700',
        };
      case 'WARNING':
        return {
          icon: <AlertTriangle className="w-5 h-5 text-amber-500" />,
          colorClass: 'border-amber-500',
          badgeClass: 'bg-amber-50 text-amber-700',
        };
      case 'INFO':
        return {
          icon: <Info className="w-5 h-5 text-blue-500" />,
          colorClass: 'border-blue-500',
          badgeClass: 'bg-blue-50 text-blue-700',
        };
      case 'DEBUG':
        return {
          icon: <FileText className="w-5 h-5 text-gray-500" />,
          colorClass: 'border-gray-500',
          badgeClass: 'bg-gray-100 text-gray-700',
        };
      default:
        return {
          icon: <AlertTriangle className="w-5 h-5 text-gray-500" />,
          colorClass: 'border-gray-500',
          badgeClass: 'bg-gray-100 text-gray-700',
        };
    }
  };

  // Format timestamp to local date and time
  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'N/A';
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  const { icon, colorClass, badgeClass } = getLevelInfo(issue.level);

  const handleRelatedItemClick = (element, type) => {
    // Only handle task navigation for now
    if (type.includes('Task')) {
      onTaskSelect(element);
    }
  };

  // Function to prettify type names
  const prettifyTypeName = (type) => {
    if (!type) return 'Unknown';

    // Extract just the class name from the fully qualified name
    const parts = type.split('.');
    const className = parts[parts.length - 1];

    // Make it more readable (e.g., "BaseTrace" -> "Trace")
    if (className === 'BaseTrace') return 'Trace';
    return className;
  };

  return (
    <div className="space-y-4">
      {/* Top panel with issue overview */}
      <div className={`bg-white p-6 mb-4 border-t-4 border-solid ${colorClass}`}>
        <div className="text-sm text-gray-600 mb-1">Issue Details</div>
        <h2 className="text-xl font-semibold mb-4 flex items-center">
          {icon}
          <span className="ml-2">{issue.name}</span>
        </h2>

        <div className="grid grid-cols-2 gap-4">
          <div className="flex items-start gap-2">
            <span className="p-2">
              <Tag className="w-4 h-4" />
            </span>
            <div>
              <p className="text-sm text-gray-600">Level</p>
              <p className="font-medium text-sm">
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${badgeClass}`}>
                  {issue.level}
                </span>
              </p>
            </div>
          </div>

          <div className="flex items-start gap-2">
            <span className="p-2">
              <Clock className="w-4 h-4" />
            </span>
            <div>
              <p className="text-sm text-gray-600">Timestamp</p>
              <p className="font-medium text-sm">{formatTimestamp(issue.timestamp)}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Description panel */}
      <div className="bg-white p-6">
        <h3 className="text-sm font-medium text-gray-900 mb-2 flex justify-between items-center">
          Description
          <button
            onClick={() => setIsDescriptionModalOpen(true)}
            className="text-blue-700 hover:bg-gray-200 rounded-full"
            title="Expand view"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"
              />
            </svg>
          </button>
        </h3>
        <div className="bg-gray-50 p-3 rounded text-sm max-h-60 overflow-y-auto prose prose-sm max-w-none">
          <ReactMarkdown>{issue.description}</ReactMarkdown>
        </div>

        {/* Effects panel, if available */}
        {issue.effect && issue.effect.length > 0 && (
          <div className="mt-4">
            <h3 className="text-sm font-medium text-gray-900 mb-2">Effects</h3>
            <ul className="bg-gray-50 p-3 rounded text-sm">
              {issue.effect.map((effect, index) => (
                <li key={index} className="mb-1 last:mb-0">
                  • {effect}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Related Items panel */}
        {issue.related_to_ids && issue.related_to_ids.length > 0 && (
          <div className="mt-4">
            <h3 className="text-sm font-medium text-gray-900 mb-2">Related Items</h3>
            <div className="bg-gray-50 rounded overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-100">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Type
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      ID
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {issue.related_elements.map((element, index) => {
                    const id = element
                      ? element.element_id
                      : issue.related_to_ids && issue.related_to_ids[index]
                      ? issue.related_to_ids[index]
                      : 'Unknown';
                    const type =
                      issue.related_to_types && issue.related_to_types[index]
                        ? issue.related_to_types[index]
                        : 'Unknown';

                    const isTask = type.includes('Task'); // then - element must exist
                    const displayType = prettifyTypeName(type);

                    return (
                      <tr
                        key={index}
                        className={isTask ? 'hover:bg-gray-100 cursor-pointer' : ''}
                        onClick={isTask ? () => handleRelatedItemClick(element, type) : undefined}
                      >
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">{displayType}</td>
                        <td
                          className={`px-4 py-2 whitespace-nowrap text-sm ${
                            isTask ? 'text-blue-600 flex items-center' : 'text-gray-500'
                          }`}
                        >
                          {id}
                          {isTask && <ChevronRight className="ml-1 w-4 h-4" />}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Description Modal - Using the OverlayModal passed as a prop */}
      {OverlayModal && (
        <OverlayModal
          isOpen={isDescriptionModalOpen}
          onClose={() => setIsDescriptionModalOpen(false)}
          title="Description"
        >
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown>{issue.description}</ReactMarkdown>
          </div>
        </OverlayModal>
      )}
    </div>
  );
};

export default IssuesSidePanel;
