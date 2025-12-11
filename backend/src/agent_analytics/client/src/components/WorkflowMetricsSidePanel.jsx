import React, { useState } from 'react';
import { 
  BarChart, 
  TrendingUp, 
  Sigma, 
  ArrowDown, 
  ArrowUp, 
  Scale, 
  Hash, 
  ChevronDown,
  PieChart
} from 'lucide-react';

// A reusable component for statistic lines
const StatLine = ({ icon: Icon, label, value }) => (
    <div className="flex items-center justify-between text-sm">
      <div className="flex items-center">
        <Icon className="w-5 h-5 mr-3 text-gray-500" strokeWidth={2.5} />
        <span className="font-medium text-gray-700">{label}</span>
      </div>
      <span className="font-mono text-gray-900">{value}</span>
    </div>
);

const formatStatValue = (value) => {
    if (value === null || typeof value === 'undefined') {
      return <span className="text-gray-500">N/A</span>;
    }
    return typeof value === 'number' ? value.toFixed(4) : value;
};


/**
 * MODIFIED: This card is now collapsible to match the statistics card.
 * It shows the total count as a key metric and hides the details by default.
 */
const DistributionMetricCard = ({ metric }) => {
    const [isDetailsVisible, setIsDetailsVisible] = useState(false);
    const { name, value: distributionData } = metric;
    
    if (!distributionData || Object.keys(distributionData).length === 0) {
        return null;
    }
    
    const totalCount = Object.values(distributionData).reduce((sum, count) => sum + count, 0);
    const sortedItems = Object.entries(distributionData).sort(([, a], [, b]) => b - a);

    return (
        <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
            {/* --- Header with Toggle Button --- */}
            <div className="flex items-center justify-between">
                <div className="flex items-center text-lg font-semibold text-gray-800">
                    <PieChart className="w-5 h-5 text-purple-600 mr-3" strokeWidth={2.5} />
                    <span>{name || 'Distribution Metric'}</span>
                </div>
                <button
                    onClick={() => setIsDetailsVisible(!isDetailsVisible)}
                    className="p-2 rounded-full hover:bg-gray-100 text-gray-500 hover:text-gray-800"
                    aria-label={isDetailsVisible ? 'Hide details' : 'Show details'}
                >
                    <ChevronDown
                        className={`w-5 h-5 transition-transform duration-200 ${isDetailsVisible ? 'rotate-180' : ''}`}
                        strokeWidth={2.5}
                    />
                </button>
            </div>

            {/* --- Key Statistic (Total Count) --- */}
            <div className="mt-4 flex items-center gap-6">
                <div className="flex items-center gap-2">
                    <Hash className="w-5 h-5 text-gray-600" strokeWidth={2.5} />
                    <div>
                        <p className="text-xs text-gray-500">Total Count</p>
                        <p className="font-semibold font-mono text-base text-gray-900">{totalCount}</p>
                    </div>
                </div>
            </div>

            {/* --- Collapsible Distribution List --- */}
            {isDetailsVisible && (
                <div className="mt-4 pt-4 border-t border-gray-200 animate-fade-in">
                    <h3 className="text-sm font-medium text-gray-900 mb-3">Item Breakdown</h3>
                    <div className="space-y-3">
                        {sortedItems.map(([key, count]) => {
                            const percentage = totalCount > 0 ? (count / totalCount) * 100 : 0;
                            return (
                                <div key={key}>
                                    <div className="flex justify-between items-center text-sm mb-1">
                                        <span className="font-medium text-gray-700 truncate" title={key}>{key}</span>
                                        <span className="font-mono text-gray-900">{count} ({percentage.toFixed(1)}%)</span>
                                    </div>
                                    <div className="w-full bg-gray-200 rounded-full h-2">
                                        <div 
                                            className="bg-purple-500 h-2 rounded-full" 
                                            style={{ width: `${percentage}%` }}
                                        ></div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
};


/**
 * The original card, specifically for STATISTICS metrics.
 */
const StatisticsMetricCard = ({ metric }) => {
    const [isDetailsVisible, setIsDetailsVisible] = useState(false);
    const { name, units, value: stats } = metric;

    if (!stats || Object.keys(stats).length === 0) return null;

    return (
        <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
            {/* --- ROW 1: Metric Name and Toggle Button --- */}
            <div className="flex items-center justify-between">
                <div className="flex items-center text-lg font-semibold text-gray-800">
                    <BarChart className="w-5 h-5 text-blue-600 mr-3" strokeWidth={2.5} />
                    <span>{name || 'Statistical Metric'}</span>
                </div>
                <button
                    onClick={() => setIsDetailsVisible(!isDetailsVisible)}
                    className="p-2 rounded-full hover:bg-gray-100 text-gray-500 hover:text-gray-800"
                    aria-label={isDetailsVisible ? 'Hide details' : 'Show details'}
                >
                    <ChevronDown
                        className={`w-5 h-5 transition-transform duration-200 ${isDetailsVisible ? 'rotate-180' : ''}`}
                        strokeWidth={2.5}
                    />
                </button>
            </div>

            {/* --- ROW 2: Key Statistics (Mean and Units) --- */}
            <div className="mt-4 flex items-center gap-6">
                <div className="flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-gray-600" strokeWidth={2.5} />
                    <div>
                        <p className="text-xs text-gray-500">Mean</p>
                        <p className="font-semibold font-mono text-base text-gray-900">{formatStatValue(stats.mean)}</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Scale className="w-5 h-5 text-gray-600" strokeWidth={2.5} />
                    <div>
                        <p className="text-xs text-gray-500">Units</p>
                        <p className="font-semibold text-sm text-gray-900">{units || 'N/A'}</p>
                    </div>
                </div>
            </div>

            {/* --- Collapsible Details Section --- */}
            {isDetailsVisible && (
                <div className="mt-4 pt-4 border-t border-gray-200 animate-fade-in">
                    <h3 className="text-sm font-medium text-gray-900 mb-2">{metric.description}</h3>
                    <div className="space-y-2 bg-gray-50 p-3 rounded-md">
                        <StatLine icon={Hash} label="Count" value={stats.count} />
                        <StatLine icon={Sigma} label="Std. Deviation" value={formatStatValue(stats.std)} />
                        <StatLine icon={ArrowDown} label="Min" value={formatStatValue(stats.min)} />
                        <StatLine icon={ArrowUp} label="Max" value={formatStatValue(stats.max)} />
                    </div>

                    {stats.attributes && Object.keys(stats.attributes).length > 0 && (
                        <div className="mt-4">
                            <h3 className="text-sm font-medium text-gray-900 mb-2">Attributes</h3>
                            <div className="bg-gray-50 rounded-md overflow-hidden border border-gray-200">
                                <table className="min-w-full text-sm">
                                    <tbody className="divide-y divide-gray-200">
                                        {Object.entries(stats.attributes).map(([key, value]) => (
                                            <tr key={key}>
                                                <td className="px-3 py-1.5 font-medium text-gray-600">{key}</td>
                                                <td className="px-3 py-1.5 text-gray-800 font-mono">{String(value)}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

/**
 * This component acts as a dispatcher.
 */
const MetricCard = ({ metric }) => {
    const type = String(metric.metric_type);

    if (type.includes('DISTRIBUTION')) {
        return <DistributionMetricCard metric={metric} />;
    }
    
    if (type.includes('STATISTICS')) {
        return <StatisticsMetricCard metric={metric} />;
    }

    // Fallback for unknown metric types 
    // TODO: add numeric regular metrics
    return 
};


/**
 * The main component (no changes needed here).
 */
const WorkflowMetricsSidePanel = ({ metrics }) => {
    if (!metrics || metrics.length === 0) {
        return (
          <div className="p-6 h-full text-center flex flex-col justify-center items-center bg-gray-50 border-t-4 border-solid border-gray-300">
              <BarChart className="w-12 h-12 text-gray-300 mb-4" />
              <h3 className="text-lg font-medium text-gray-800">No Metrics to Display</h3>
              <p className="text-sm text-gray-500 mt-1">Select a runnable to view its metrics.</p>
          </div>
        );
    }

    const runnableId = metrics[0]?.related_to_ids?.join(', ');

    return (
        <div className="h-full bg-white">
          <div className="p-6 bg-white border-b border-gray-200 border-t-4 border-solid border-[#93C5FD]">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Metrics for</h2>
            <p className="font-mono text-gray-800 text-lg font-bold truncate mt-1">{runnableId || 'Selected Runnable'}</p>
          </div>

          <div className="p-4 space-y-4 overflow-y-auto bg-gray-50 h-full">
            {metrics.map((metric, index) => (
                <MetricCard key={metric.element_id || index} metric={metric} />
            ))}
          </div>
        </div>
    );
};

export default WorkflowMetricsSidePanel;