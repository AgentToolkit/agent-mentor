import React from 'react';
import { BarChart, Hash, TrendingUp, Sigma, ArrowDown, ArrowUp, Info } from 'lucide-react';

const MetricsSidePanel = ({ metric }) => {
  // Renders a fallback view if no metric is selected
  if (!metric) {
    return (
      <div className="bg-white p-6 mb-4 border-t-4 border-solid border-gray-300 min-h-screen">
        Select a metric to view details
      </div>
    );
  }

  // Helper to format numeric stat values, showing N/A for null/undefined
  const formatStatValue = (value) => {
    if (value === null || typeof value === 'undefined') {
      return <span className="text-gray-500">N/A</span>;
    }
    // Format numbers to a reasonable precision
    return value.toFixed(4);
  };

  // Extract the aggregated stats from the metric value
  const stats = metric.value;

  return (
    <div className="space-y-4">
      {/* Top panel with metric overview */}
      <div className="bg-white p-6 mb-4 border-t-4 border-solid border-blue-500">
        <div className="text-sm text-gray-600 mb-1">Metric Details</div>
        <h2 className="text-xl font-semibold mb-4 flex items-center">
          <BarChart className="w-5 h-5 text-blue-600" />
          {/* Assumes a 'name' property is passed with the metric for display */}
          <span className="ml-2">{metric.name || 'Statistical Metric'}</span>
        </h2>

        <div className="grid grid-cols-2 gap-4">
          {/* Metric Type Display */}
          <div className="flex items-start gap-2">
            <span className="p-2">
              <Info className="w-4 h-4 text-gray-500" />
            </span>
            <div>
              <p className="text-sm text-gray-600">Metric Type</p>
              <p className="font-medium text-sm">
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                  {metric.metric_type}
                </span>
              </p>
            </div>
          </div>

          {/* Count Display */}
          <div className="flex items-start gap-2">
            <span className="p-2">
              <Hash className="w-4 h-4 text-gray-500" />
            </span>
            <div>
              <p className="text-sm text-gray-600">Count</p>
              <p className="font-medium text-sm">{stats.count}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Aggregated Statistics Panel */}
      <div className="bg-white p-6">
        <h3 className="text-sm font-medium text-gray-900 mb-2">Aggregated Statistics</h3>
        <div className="space-y-3 bg-gray-50 p-4 rounded">
          {/* Mean */}
          <div className="flex items-center text-sm">
            <TrendingUp className="w-4 h-4 mr-3 text-gray-500" />
            <span className="w-32 font-medium text-gray-700">Mean</span>
            <span className="font-mono text-gray-900">{formatStatValue(stats.mean)}</span>
          </div>

          {/* Standard Deviation */}
          <div className="flex items-center text-sm">
            <Sigma className="w-4 h-4 mr-3 text-gray-500" />
            <span className="w-32 font-medium text-gray-700">Std. Deviation</span>
            <span className="font-mono text-gray-900">{formatStatValue(stats.std)}</span>
          </div>

          {/* Min Value */}
          <div className="flex items-center text-sm">
            <ArrowDown className="w-4 h-4 mr-3 text-gray-500" />
            <span className="w-32 font-medium text-gray-700">Min</span>
            <span className="font-mono text-gray-900">{formatStatValue(stats.min)}</span>
          </div>

          {/* Max Value */}
          <div className="flex items-center text-sm">
            <ArrowUp className="w-4 h-4 mr-3 text-gray-500" />
            <span className="w-32 font-medium text-gray-700">Max</span>
            <span className="font-mono text-gray-900">{formatStatValue(stats.max)}</span>
          </div>
        </div>
      </div>

      {/* Attributes Panel (only shown if attributes exist) */}
      {stats.attributes && Object.keys(stats.attributes).length > 0 && (
        <div className="bg-white p-6">
          <h3 className="text-sm font-medium text-gray-900 mb-2">Attributes</h3>
          <div className="bg-gray-50 rounded overflow-hidden">
            <table className="min-w-full text-sm">
              <tbody className="divide-y divide-gray-200">
                {Object.entries(stats.attributes).map(([key, value]) => (
                  <tr key={key}>
                    <td className="px-4 py-2 font-medium text-gray-600">{key}</td>
                    <td className="px-4 py-2 text-gray-800 font-mono">{String(value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default MetricsSidePanel;
