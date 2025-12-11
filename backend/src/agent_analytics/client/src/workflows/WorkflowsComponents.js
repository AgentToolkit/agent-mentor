// WorkflowsComponents.js
import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "../components/AuthComponents";
import MetricsStrip from "../components/MetricsStrip";
import SidePanel from "../components/SidePanel";
import GraphVisualizerApp from "../components/graph/graph-app";
import { buildHierarchy, buildIssuesAndMetrics } from "../components/utils/hierarchyUtils";
import { handleGroupMetrics } from "../components/utils/metricsUtils";

/**
 * WorkflowsContent - Displays workflow visualizations for a trace group
 * Simplified version focused on workflows only - no tabs, navigation, or settings
 */
export const WorkflowsContent = ({
  serverUrl, setTenantId, tenant_id
}) => {
  const { authFetch } = useAuth();

  // State management
  const [traceGroupId, setTraceGroupId] = useState(null);
  const [workflowData, setWorkflowData] = useState([]);
  const [analyticsMetrics, setAnalyticsMetrics] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [issues, setIssues] = useState([]);
  const [selectedMetric, setSelectedMetric] = useState(null);
  const [selectedIssue, setSelectedIssue] = useState(null);
  const [selectedRunnableNodeId, setSelectedRunnableNodeId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const runnableMetricsMapRef = useRef(new Map());

  // Extract trace_group_id from URL query params
  useEffect(() => {
    const queryParams = new URLSearchParams(window.location.search);
    const groupId = queryParams.get("trace_group_id");
    const tenant_id = queryParams.get("tenant_id");

    if (groupId) {
      setTraceGroupId(groupId);
    }
    if (tenant_id) {
      setTenantId(tenant_id);
    }
  }, []);

  // Fetch trace group data when trace_group_id is available
  useEffect(() => {
    const fetchTraceGroupData = async () => {
      if (!traceGroupId) return;

      setError(null);
      setIsLoading(true);

      try {
        const response = await authFetch(
          // `${serverUrl}/storage/${serviceName}/groups/${traceGroupId}/traces`
          `${serverUrl}/api/v1/trace_group/${traceGroupId}`,
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(`Error fetching trace group: ${response.status} ${errorData.detail || response.statusText}`);
        }

        const groupData = await response.json();

        if (groupData.workflows && groupData.workflows.nodes.length > 0) {
          // Set workflow data
          setWorkflowData(groupData.workflows || []);

          // Set analytics metrics
          setAnalyticsMetrics(groupData.workflows_metrics || []);

          ////////// Currently disabled  /////////
          // Process issues
          // const [processedIssues] = buildIssuesAndMetrics(
          //   groupData.tasks,
          //   groupData.issues,
          //   groupData.metrics,
          //   null
          // );
          // setIssues(processedIssues);

          // // Calculate and set group metrics
          // const groupTasks = buildHierarchy(groupData.tasks, () => {}, () => {});
          // const groupMetrics = handleGroupMetrics(groupTasks, groupData.traces);
          // setMetrics({
          //   ...groupMetrics,
          //   issues: processedIssues.length,
          // });
          //////////////////////////////////////

          setMetrics(groupData.trace_group_metrics);

          if (groupData.error) {
            setError("Some traces encountered errors: " + groupData.error);
          }
        } else {
          setError("No workflows found in this group.");
          setWorkflowData([]);
        }
      } catch (error) {
        console.error("Error fetching trace group data:", error);
        setError(error.message);
      } finally {
        setIsLoading(false);
      }
    };

    fetchTraceGroupData();
  }, [traceGroupId, serverUrl, authFetch]);

  // Build runnable metrics map
  useEffect(() => {
    if (!analyticsMetrics || !Array.isArray(analyticsMetrics) || analyticsMetrics.length === 0) {
      return;
    }
    const newMap = new Map();
    analyticsMetrics.forEach((metric) => {
      (metric.related_to_ids || []).forEach((relatedId, index) => {
        const relatedType = (metric.related_to_types || [])[index];
        if (relatedType && relatedType.toLowerCase().includes("workflownode")) {
          if (!newMap.has(relatedId)) {
            newMap.set(relatedId, []);
          }
          newMap.get(relatedId).push(metric);
        }
      });
    });
    runnableMetricsMapRef.current = newMap;
  }, [analyticsMetrics]);

  // Handle node metrics click
  const handleNodeMetricsClick = useCallback((nodeId) => {
    const metricsForNode = runnableMetricsMapRef.current.get(nodeId);
    if (metricsForNode && metricsForNode.length > 0) {
      setSelectedIssue(null);
      setSelectedMetric(metricsForNode);
      setSelectedRunnableNodeId(nodeId);
    } else {
      setSelectedMetric(null);
      setSelectedRunnableNodeId(null);
    }
  }, []);

  // Handle issue select
  const handleIssueSelect = (issue) => {
    setSelectedMetric(null);
    setSelectedIssue(issue);
  };

  if (isLoading) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading workflow data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center max-w-md">
          <div className="text-red-500 text-5xl mb-4">⚠</div>
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Error Loading Workflow</h2>
          <p className="text-gray-600">{error}</p>
        </div>
      </div>
    );
  }

  if (!traceGroupId) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Missing Parameters</h2>
          <p className="text-gray-600">
            Please provide trace_group_id as query parameter
          </p>
          <p className="text-sm text-gray-500 mt-2">
            Example: ?trace_group_id=123
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-gray-100">
      {/* Metrics Strip */}
      <MetricsStrip
        metrics={metrics}
        analyticsType="group"
        selectedGroup={{ id: traceGroupId }}
        traceId={null}
      />

      {/* Main content area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Workflow Viewer - Main content */}
        <div className="flex-grow h-full overflow-hidden pl-2 pr-4">
          <div className="h-full bg-white overflow-auto">
            <GraphVisualizerApp
              workflowData={workflowData}
              analyticsMetrics={analyticsMetrics || []}
              onNodeMetricsClick={handleNodeMetricsClick}
              selectedRunnableNodeId={selectedRunnableNodeId}
            />
          </div>
        </div>

        {/* Side Panel - Fixed width, no collapse */}
        <div className="w-96 h-full border-l border-gray-200 bg-white">
          <SidePanel
            task={null}
            handleTaskClick={() => {}}
            setData={() => {}}
            serverUrl={serverUrl}
            serviceName={tenant_id}
            issues={issues}
            selectedIssue={selectedIssue}
            onIssueSelect={handleIssueSelect}
            setActiveTab={() => {}}
            hideTaskPrefixes={false}
            selectedMetric={selectedMetric}
          />
        </div>
      </div>
    </div>
  );
};
