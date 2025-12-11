import React, { useState } from "react";
import ReactMarkdown from "react-markdown";

// Component to display analytics status and results
const EvalAnalytics = ({ analyticsMetrics, onTaskSelect }) => {
  const [sortConfig, setSortConfig] = useState({
    key: "timestamp",
    direction: "desc",
  });

  // Sort the results based on the current sort configuration
  const sortedResults = React.useMemo(() => {
    if (!analyticsMetrics || analyticsMetrics.length === 0) return [];

    const sortableResults = [...analyticsMetrics].filter((element) => element.plugin_metadata_id === "eval_metrics");

    sortableResults.sort((a, b) => {
      let aValue = a[sortConfig.key];
      let bValue = b[sortConfig.key];

      // Handle special sorting for different data types
      if (sortConfig.key === "score") {
        aValue = parseFloat(aValue) || 0;
        bValue = parseFloat(bValue) || 0;
      }

      if (aValue < bValue) {
        return sortConfig.direction === "asc" ? -1 : 1;
      }
      if (aValue > bValue) {
        return sortConfig.direction === "asc" ? 1 : -1;
      }
      return 0;
    });

    return sortableResults;
  }, [analyticsMetrics, sortConfig]);

  // Handle the sort request when a column header is clicked
  const requestSort = (key) => {
    let direction = "asc";
    if (sortConfig.key === key && sortConfig.direction === "asc") {
      direction = "desc";
    }
    setSortConfig({ key, direction });
  };

  // Render different content based on the status
  const renderContent = () => {
    if (!analyticsMetrics || analyticsMetrics.length === 0) {
      return (
        <div className="status-container">
          <div className="flex justify-left font-medium space-x-2 pb-4 text-gray-500">
            <h1 className="error">
              Advanced analytics not computed. Return to trace list and click to compute `Advanced` analytics.
            </h1>
          </div>
        </div>
      );
    } else {
      return (
        <div className="results-container">
          <div className="flex justify-left font-medium space-x-2 text-gray-500">
            <h1 className="text-lg font-bold">Evaluation Results</h1>
          </div>
          {renderResultsTable()}
        </div>
      );
    }
  };

  const handleRelatedTaskClick = (element) => {
    // Only handle task navigation for now
    onTaskSelect(element);
  };

  // Render the results table when status is READY
  const renderResultsTable = () => {
    if (!analyticsMetrics || analyticsMetrics.length === 0) {
      return <p>No results available.</p>;
    }

    return (
      <div className="bx--data-table-container">
        <div className="max-h-screen overflow-y-auto border border-gray-200 rounded-lg">
          <table className="bx--data-table w-full">
            <thead className="sticky top-0 bg-white z-10">
              <tr className="border-b-2 border-gray-200">
                <th className="p-4 text-left cursor-pointer bg-white" onClick={() => requestSort("affected_element")}>
                  <div className="flex items-center">
                    ID
                    {renderSortIndicator("affected_element")}
                  </div>
                </th>
                <th className="p-4 text-left cursor-pointer bg-white" onClick={() => requestSort("timestamp")}>
                  <div className="flex items-center">
                    Time
                    {renderSortIndicator("timestamp")}
                  </div>
                </th>
                <th className="p-4 text-left cursor-pointer bg-white" onClick={() => requestSort("description")}>
                  <div className="flex items-center">
                    Evaluation
                    {renderSortIndicator("description")}
                  </div>
                </th>
                <th className="p-4 text-left cursor-pointer bg-white" onClick={() => requestSort("value")}>
                  <div className="flex items-center">
                    Score
                    {renderSortIndicator("value")}
                  </div>
                </th>
                <th className="p-4 text-left cursor-pointer bg-white" onClick={() => requestSort("value")}>
                  <div className="flex items-center">
                    Final
                    {renderSortIndicator("value")}
                  </div>
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedResults.map((result, index) => {
                const isTask = result.affected_task; // then - element must exist

                return (
                  <tr key={result.id || index} className="border-b border-gray-200 hover:bg-gray-50">
                    <td
                      className={`p-4 align-top ${isTask ? "hover:bg-gray-100 cursor-pointer text-blue-600" : ""}`}
                      onClick={isTask ? () => handleRelatedTaskClick(result.affected_task) : undefined}
                    >
                      <div className="flex items-start">
                        {isTask ? result.affected_task.name : result.affected_element}
                      </div>
                    </td>
                    <td className="p-4 align-top">{formatTimestamp(result.timestamp)}</td>
                    <td className="p-4 align-top">
                      <ReactMarkdown>
                        {result.attributes.evaluation_summary
                          ? result.attributes.evaluation_summary
                          : result.description}
                      </ReactMarkdown>
                    </td>
                    <td className="p-4 align-top">{result.value}</td>
                    <td className="p-4 align-top">{result.attributes.is_final_response ? "Y" : "N"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  // Render sort indicator (arrow up/down) based on current sort configuration
  const renderSortIndicator = (key) => {
    if (sortConfig.key !== key) {
      return null;
    }
    return <span className="sort-indicator ml-2">{sortConfig.direction === "asc" ? " ▲" : " ▼"}</span>;
  };

  // Format timestamp for display
  const formatTimestamp = (timestamp) => {
    if (!timestamp) return "N/A";

    try {
      const date = new Date(timestamp);
      return date.toLocaleString();
    } catch (e) {
      return timestamp;
    }
  };

  return <div className="analytics-status-component">{renderContent()}</div>;
};

export default EvalAnalytics;
