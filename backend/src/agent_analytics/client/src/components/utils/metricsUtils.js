// Metrics calculation utilities

/**
 * Helper function to extract metric value from metrics array by matching element_id pattern
 * @param {Array} metricsArray - Array of metric objects
 * @param {string} metricType - Type of metric (e.g., 'Input_Tokens', 'Output_Tokens', 'Execution_Time')
 * @param {string} taskId - Task element_id to match
 * @returns {number} - Metric value or 0 if not found
 */
const extractMetricValue = (metricsArray, metricType, taskId) => {
  if (!metricsArray || !Array.isArray(metricsArray)) return 0;

  // Handle both formats: "Metric:Type:taskId" and legacy "Metric:TypetaskId" (missing colon)
  const metric = metricsArray.find(m => {
    if (!m.element_id) return false;
    // Try standard format first
    if (m.element_id === `Metric:${metricType}:${taskId}`) return true;
    // Try legacy format without colon between metric type and task id
    if (m.element_id === `Metric:${metricType}${taskId}`) return true;
    return false;
  });

  return metric ? (metric.value || 0) : 0;
};

export const computeMetrics = (tasks, metricsArray = []) => {
  // Extract metrics from the data
  let llmCalls = 0;
  let toolCalls = 0;
  let inputTokens = 0;
  let outputTokens = 0;
  let duration = 0;
  let exceptions = 0;

  // Loop through all tasks to calculate metrics
  const processTask = (task) => {
    // Check tags to identify LLM and tool calls
    if (task.tags && task.tags.includes('llm_call')) llmCalls++;
    if (task.tags && task.tags.includes('tool_call')) toolCalls++;

    // Extract metrics from the metrics array for this task
    if (task.element_id && metricsArray && metricsArray.length > 0) {
      const taskInputTokens = extractMetricValue(metricsArray, 'Input_Tokens', task.element_id);
      const taskOutputTokens = extractMetricValue(metricsArray, 'Output_Tokens', task.element_id);
      const taskDuration = extractMetricValue(metricsArray, 'Execution_Time', task.element_id);

      inputTokens += taskInputTokens;
      outputTokens += taskOutputTokens;

      // For duration, take the maximum value (root task should have the total)
      if (taskDuration > duration) {
        duration = taskDuration;
      }
    }

    // Check for issues
    if (task.exceptions && task.exceptions.length > 0) exceptions += task.exceptions.length;

    // Process children
    if (task.children) {
      task.children.forEach(processTask);
    }
  };

  tasks.forEach(processTask);

  // Return metrics
  return {
    llmCalls,
    toolCalls,
    inputTokens: inputTokens || 0,
    outputTokens: outputTokens || 0,
    duration: typeof duration === 'number' ? duration.toFixed(3) : '0',
    exceptions,
  };
};

export const handleGroupMetrics = (tasks, traces, metricsArray = []) => {
  // Initialize group metrics
  let totalTraces = traces.length;
  let totalLlmCalls = 0;
  let totalToolCalls = 0;
  let totalDuration = 0;
  let maxDuration = 0;
  let totalIssues = 0;

  // Process each task (trace)
  tasks.forEach((task) => {
    // Initialize per-trace metrics
    let traceLlmCalls = 0;
    let traceToolCalls = 0;
    let traceDuration = 0;
    let traceIssues = 0;

    // Recursive function to process task and its children
    const processTask = (t) => {
      // Check tags to identify LLM and tool calls
      if (t.tags && t.tags.includes('llm_call')) traceLlmCalls++;
      if (t.tags && t.tags.includes('tool_call')) traceToolCalls++;

      // Extract duration from metrics array for this task
      if (t.element_id && metricsArray && metricsArray.length > 0) {
        const taskDuration = extractMetricValue(metricsArray, 'Execution_Time', t.element_id);
        if (taskDuration > traceDuration) {
          traceDuration = taskDuration;
        }
      }

      // Check for issues
      if (t.exceptions && t.exceptions.length > 0) traceIssues += t.exceptions.length;

      // Process children
      if (t.children) {
        t.children.forEach(processTask);
      }
    };

    // Process the entire task tree
    processTask(task);

    // Accumulate metrics for all traces
    totalLlmCalls += traceLlmCalls;
    totalToolCalls += traceToolCalls;
    totalDuration += traceDuration;
    totalIssues += traceIssues;

    // Update max duration if this trace has a longer duration
    if (traceDuration > maxDuration) {
      maxDuration = traceDuration;
    }
  });

  // Calculate averages
  const avgLlmCalls = totalTraces > 0 ? (totalLlmCalls / totalTraces).toFixed(1) : '0';
  const avgToolCalls = totalTraces > 0 ? (totalToolCalls / totalTraces).toFixed(1) : '0';
  const avgDuration = totalTraces > 0 ? (totalDuration / totalTraces).toFixed(3) : '0';

  // Return metrics
  return {
    totalTraces,
    avgLlmCalls,
    avgToolCalls,
    avgDuration,
    maxDuration: maxDuration.toFixed(3),
    totalIssues,
  };
};
