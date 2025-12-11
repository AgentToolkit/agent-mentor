import { AlertTriangle, ArrowUp, Clock, MessageSquare, Hammer, TrendingUp, Percent, Hash, BarChart3 } from "lucide-react";

// Helper function to convert snake_case to Title Case
const snakeToTitleCase = (str) => {
  return str
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
};

// Helper function to get icon based on units
const getIconForUnit = (units, iconColor = "text-purple-700") => {
  switch (units) {
    case 'seconds':
      return <Clock className={`w-5 h-5 ${iconColor}`} />;
    case 'ratio':
      return <Percent className={`w-5 h-5 ${iconColor}`} />;
    case 'count':
      return <Hash className={`w-5 h-5 ${iconColor}`} />;
    default:
      return <BarChart3 className={`w-5 h-5 ${iconColor}`} />;
  }
};

// Helper function to format metric value based on units
const formatMetricValue = (value, units) => {
  if (units === 'ratio') {
    // Convert ratio to percentage
    return `${(value * 100).toFixed(1)}%`;
  } else if (units === 'seconds') {
    return `${value.toFixed(3)} sec`;
  }
  return value;
};

const MetricBox = ({ title, value, icon, alert }) => {
  return (
    <div className="flex items-center bg-white p-2 rounded-sm">
      <div className="mr-4">{icon}</div>
      <div>
        <div className="text-sm text-gray-600">{title}</div>
        <div className="flex items-center">
          <span className="text-lg font-semibold">{value}</span>
          {alert && <AlertTriangle className="ml-2 w-4 h-4 text-amber-500" />}
        </div>
      </div>
    </div>
  );
};

const MetricsStrip = ({ metrics, analyticsType = "trace", selectedGroup = null, traceId = null }) => {
  // Default metrics if none provided
  const defaultMetrics = {
    llmCalls: 0,
    toolCalls: 0,
    inputTokens: 0,
    outputTokens: 0,
    duration: "0",
    issues: 0,
  };

  const data = metrics || defaultMetrics;

  // Determine background color class based on the current state
  const getBackgroundColorClass = () => {
    if (selectedGroup) {
      if (analyticsType === "group") {
        return "bg-purple-50"; // Light purple for group view
      } else {
        return "bg-blue-50"; // Light blue for trace within group
      }
    } else if (traceId) {
      return "bg-blue-50"; // Light blue for single trace
    }
    return "transparent"; // Transparent to let parent background show through
  };

  // Apply aggregate metrics when showing group analytics
  const getAggregateMetricView = () => {
    if (analyticsType === "group" && selectedGroup) {
      // Data is expected to be an array of metric objects
      const metricsArray = Array.isArray(data) ? data : [];

      // If empty or null, return null to hide the metrics strip
      if (metricsArray.length === 0) {
        return null;
      }

      // For 3 or fewer metrics, wrap MetricBox with a div to control width
      const shouldFixWidth = metricsArray.length <= 3;

      return (
        <>
          {metricsArray.map((metric) => (
            shouldFixWidth ? (
              <div key={metric.element_id} className="w-64">
                <MetricBox
                  title={snakeToTitleCase(metric.name)}
                  value={formatMetricValue(metric.value, metric.units)}
                  icon={getIconForUnit(metric.units, "text-purple-700")}
                />
              </div>
            ) : (
              <MetricBox
                key={metric.element_id}
                title={snakeToTitleCase(metric.name)}
                value={formatMetricValue(metric.value, metric.units)}
                icon={getIconForUnit(metric.units, "text-purple-700")}
              />
            )
          ))}
        </>
      );
    }

    // Default trace view with blue icons
    const iconColor = selectedGroup ? "text-blue-700" : "text-blue-700";

    return (
      <>
        <MetricBox
          title="LLM calls"
          value={data.llmCalls}
          icon={<MessageSquare className={`w-5 h-5 ${iconColor}`} />}
        />
        <MetricBox title="Tools calls" value={data.toolCalls} icon={<Hammer className={`w-5 h-5 ${iconColor}`} />} />
        <MetricBox
          title="Input Tokens"
          value={data.inputTokens}
          icon={<ArrowUp className={`w-5 h-5 ${iconColor}`} />}
        />
        <MetricBox
          title="Output Tokens"
          value={data.outputTokens}
          icon={<TrendingUp className={`w-5 h-5 ${iconColor}`} />}
        />
        <MetricBox
          title="Duration"
          value={`${data.duration} sec`}
          icon={<Clock className={`w-5 h-5 ${iconColor}`} />}
        />
        <MetricBox
          title="Issues"
          value={data.issues}
          icon={<AlertTriangle className={`w-5 h-5 ${iconColor}`} />}
          alert={data.issues > 0}
        />
      </>
    );
  };

  const metricView = getAggregateMetricView();

  // If metrics view is null (empty metrics for group), don't render anything
  if (metricView === null) {
    return null;
  }

  // Determine layout based on number of metrics for group view
  let containerClass = "grid grid-cols-6 gap-x-2 p-2"; // Default for trace view

  if (analyticsType === "group" && selectedGroup && Array.isArray(data)) {
    const metricsCount = data.length;
    if (metricsCount <= 3) {
      // For 3 or fewer metrics, use flex with fixed width per item
      containerClass = "flex gap-x-2 p-2";
    } else if (metricsCount === 4) {
      // For 4 metrics, expand to full width
      containerClass = "grid grid-cols-4 gap-x-2 p-2";
    } else {
      // For more than 4, use 6 column grid
      containerClass = "grid grid-cols-6 gap-x-2 p-2";
    }
  }

  return (
    <div className={`relative ${getBackgroundColorClass()}`}>
      <div className={containerClass}>
        {metricView}
      </div>
    </div>
  );
};

export default MetricsStrip;
