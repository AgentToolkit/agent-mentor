import { AlertTriangle, AlertCircle, Info, FileText } from "lucide-react";

const IssuesTable = ({ issues = [], onIssueSelect }) => {
  if (!issues || issues.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-12 bg-gray-50 border border-gray-200 rounded-md h-64">
        <div className="text-gray-400 mb-4">
          <AlertCircle size={48} />
        </div>
        <h3 className="text-lg font-medium text-gray-600 mb-2">No issues found</h3>
        <p className="text-gray-500 text-sm">This trace doesn't have any recorded issues</p>
      </div>
    );
  }

  // Get issue level icon and color
  const getLevelInfo = (level) => {
    switch (level) {
      case "CRITICAL":
        return {
          icon: <AlertCircle className="w-5 h-5 text-red-600" />,
          badgeClass: "bg-red-100 text-red-800",
        };
      case "ERROR":
        return {
          icon: <AlertCircle className="w-5 h-5 text-red-500" />,
          badgeClass: "bg-red-50 text-red-700",
        };
      case "WARNING":
        return {
          icon: <AlertTriangle className="w-5 h-5 text-amber-500" />,
          badgeClass: "bg-amber-50 text-amber-700",
        };
      case "INFO":
        return {
          icon: <Info className="w-5 h-5 text-blue-500" />,
          badgeClass: "bg-blue-50 text-blue-700",
        };
      case "DEBUG":
        return {
          icon: <FileText className="w-5 h-5 text-gray-500" />,
          badgeClass: "bg-gray-100 text-gray-700",
        };
      default:
        return {
          icon: <AlertTriangle className="w-5 h-5 text-gray-500" />,
          badgeClass: "bg-gray-100 text-gray-700",
        };
    }
  };

  // Format timestamp to local date and time
  const formatTimestamp = (timestamp) => {
    if (!timestamp) return "N/A";
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  // Get related task name
  const getRelatedTaskName = (issue) => {
    if (!issue.related_to_ids || issue.related_to_ids.length === 0) {
      return "N/A";
    }
    // For simplicity, just return the first task ID
    // In a real implementation, you might want to look up the actual task name
    return issue.related_to_ids[0];
  };

  return (
    <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 md:rounded-lg">
      <table className="min-w-full divide-y divide-gray-300">
        <thead className="bg-gray-50">
          <tr>
            <th scope="col" className="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 sm:pl-6">
              Issue
            </th>
            <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
              Level
            </th>
            <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
              Related Task
            </th>
            <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
              Timestamp
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 bg-white">
          {issues.map((issue, index) => {
            const { icon, badgeClass } = getLevelInfo(issue.level);
            return (
              <tr key={index} className="hover:bg-gray-50 cursor-pointer" onClick={() => onIssueSelect(issue)}>
                <td className="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6">
                  {issue.name}
                </td>
                <td className="whitespace-nowrap px-3 py-4 text-sm">
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${badgeClass}`}
                  >
                    {icon}
                    <span className="ml-1">{issue.level}</span>
                  </span>
                </td>
                <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">{getRelatedTaskName(issue)}</td>
                <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
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

export default IssuesTable;
