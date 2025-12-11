import React from 'react';
import { AlertTriangle, AlertCircle, Info, FileText } from 'lucide-react';

const TaskIssuesPanel = ({ taskId, issues, onIssueSelect }) => {
  // Filter issues related to this task
  const taskIssues = issues?.filter((issue) => issue.related_to_ids && issue.related_to_ids.includes(taskId)) || [];

  if (taskIssues.length === 0) {
    return <div className="p-4 text-center text-gray-500">No issues associated with this task</div>;
  }

  // Get issue level icon and color
  const getLevelInfo = (level) => {
    switch (level) {
      case 'CRITICAL':
        return {
          icon: <AlertCircle className="w-4 h-4 text-red-600" />,
          badgeClass: 'bg-red-100 text-red-800',
        };
      case 'ERROR':
        return {
          icon: <AlertCircle className="w-4 h-4 text-red-500" />,
          badgeClass: 'bg-red-50 text-red-700',
        };
      case 'WARNING':
        return {
          icon: <AlertTriangle className="w-4 h-4 text-amber-500" />,
          badgeClass: 'bg-amber-50 text-amber-700',
        };
      case 'INFO':
        return {
          icon: <Info className="w-4 h-4 text-blue-500" />,
          badgeClass: 'bg-blue-50 text-blue-700',
        };
      case 'DEBUG':
        return {
          icon: <FileText className="w-4 h-4 text-gray-500" />,
          badgeClass: 'bg-gray-100 text-gray-700',
        };
      default:
        return {
          icon: <AlertTriangle className="w-4 h-4 text-gray-500" />,
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

  return (
    <div className="overflow-x-auto max-w-full">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Issue</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Level</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {taskIssues.map((issue, index) => {
            const { icon, badgeClass } = getLevelInfo(issue.level);
            return (
              <tr key={index} className="hover:bg-gray-50 cursor-pointer" onClick={() => onIssueSelect(issue)}>
                <td className="px-4 py-3 whitespace-nowrap text-sm font-medium">{issue.title}</td>
                <td className="px-4 py-3 whitespace-nowrap text-sm">
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${badgeClass}`}
                  >
                    {icon}
                    <span className="ml-1">{issue.level}</span>
                  </span>
                </td>
                <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                  {formatTimestamp(issue.timestamp)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default TaskIssuesPanel;
