import { useState, useEffect } from "react";
import { useAuth } from "../AuthComponents";
import { buildHierarchy, buildIssuesAndMetrics } from "../utils/hierarchyUtils";
import { computeMetrics } from "../utils/metricsUtils";
import { ANALYTICS_STATUS } from "../traceSelection/modalConstants";
import { convertToJaegerFormat } from '../utils/traceConverter';

export const useDataFetching = ({
  serverUrl,
  setTraceName,
  setTraceId,
  setTraceStart,
  setMetrics,
  setAnalyticsMetrics,
  setData,
  setProcessedData,
  setIssues,
  setAnalysisStatus,
  setWorkflowData,
  setTraceData,
  setTrajectoryData,
  selectedGroup,
  setActiveTab,
  analyticsMetrics
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const { authFetch } = useAuth();

  // Fetch Jaeger URL when component mounts
  const [jaegerUrl, setJaegerUrl] = useState("");
  const [extensionsEnabled, setExtensionsEnabled] = useState(false);

  useEffect(() => {
    const fetchJaegerUrl = async () => {
      try {
        const response = await fetch(`${serverUrl}/config/jaeger-url`);
        if (response.ok) {
          const data = await response.json();
          // workaround for working local with ports
          if (!data.url.startsWith("http")) {
            setJaegerUrl(`${serverUrl}${data.url}`);
          } else {
            setJaegerUrl(data.url);
          }
        }
      } catch (error) {
        console.error("Error fetching Jaeger URL:", error);
      }
    };
    fetchJaegerUrl();

    const fetchExtensionsEnabled = async () => {
      try {
        const response = await fetch(`${serverUrl}/config/extensions-enabled`);
        if (response.ok) {
          const data = await response.json();
          setExtensionsEnabled(data.state);
        }
      } catch (error) {
        console.error("Error fetching extensions state:", error);
      }
    };
    fetchExtensionsEnabled();
  }, [serverUrl]);

  const handleDataReceived = (tasks, issues, analyticsMetrics, trajectory, analysisStatus) => {
    const hierarchyData = buildHierarchy(tasks, setTraceName, setTraceId);
    if (hierarchyData != null && hierarchyData.length > 0) {
      setTraceStart(hierarchyData[0].start_time);
      const metrics = computeMetrics(hierarchyData, analyticsMetrics);
      setMetrics({
        ...metrics,
        issues: issues?.length || 0,
      });
    } else {
      setTraceStart("");
      setMetrics(null);
    }

    const [processedIssues, processedEvalMetrics] = buildIssuesAndMetrics(tasks, issues, analyticsMetrics, trajectory);
    setData(hierarchyData);
    setProcessedData(tasks); // Store the processed data for download
    setIssues(processedIssues);

    // Extract analysis status from the first task (root task)
    if (hierarchyData && hierarchyData.length > 0) {
      // Update analysis status if available in the data
      const rootTask = hierarchyData[0];
      if (analysisStatus) {
        setAnalysisStatus({
          basic: analysisStatus.basic || null,
          advanced: analysisStatus.advanced || null,
        });
      } else if (rootTask) {
        setAnalysisStatus({
          basic: ANALYTICS_STATUS.COMPLETED,
          advanced: rootTask.metrics ? ANALYTICS_STATUS.COMPLETED : ANALYTICS_STATUS.NOT_STARTED,
        });
      }
    }
  };

  const fetchStorageTraceDetails = async (traceId, serviceName, isGroupCall = false) => {
    setError(null);
    try {
      setIsLoading(true);
      const response = await authFetch(`${serverUrl}/storage/${serviceName}/traces/${traceId}?spans=true`);

      if (!response.ok) {
        setIsLoading(false);
        const errorData = await response.json();
        const msg =
          `Error ${response.status} processing trace details. Check if this trace is instrumented properly.` +
          (errorData.detail ? `\n\nDetails: ${errorData.detail}` : "");
        throw new Error(msg);
      }
      const jsonData = await response.json();
      setIsLoading(false);

      handleDataReceived(jsonData.tasks, jsonData.issues, jsonData.metrics, jsonData.trajectory);

      if (jsonData.spans){
        const jaegerTraces = convertToJaegerFormat(jsonData);
        setTraceData(jaegerTraces);
      }
      // Store workflow data
      if (selectedGroup === null && !isGroupCall)
        setWorkflowData(jsonData.workflow);
      if (! isGroupCall){
        setAnalyticsMetrics(jsonData.metrics || []);
      }
      // Store trajectory data if available
      if (jsonData.trajectory) {
        setTrajectoryData(jsonData.trajectory);
      } else {
        setTrajectoryData([]); // Reset if no trajectory data
      }

      // Store analysis status if available
      if (jsonData.analysisStatus) {
        setAnalysisStatus(jsonData.analysisStatus);
      } else if (jsonData.traces && jsonData.traces.length > 0 && jsonData.traces[0].analysisStatus) {
        setAnalysisStatus(jsonData.traces[0].analysisStatus);
      }

      if (jsonData.error) {
        setError(jsonData.error);
        setTraceId(traceId);
        setActiveTab("spans");
      }

      if (jsonData.length === 0) {
        setError("The selected trace produced 0 tasks.");
        setTraceId(traceId);
        setActiveTab("spans");
      }
    } catch (error) {
      console.error("Error fetching trace details:", error);
      setError(error.message);
    }
  };

  const handleFullArtifactDownload = async (traceId, serviceName) => {
    if (!traceId || !serviceName) return;

    try {
      const response = await authFetch(`${serverUrl}/storage/${serviceName}/traces/${traceId}?spans=true`);
      if (!response.ok) {
        throw new Error(`Error fetching full artifact log: ${response.status}`);
      }

      const data = await response.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `trace_${traceId}_full.log`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Error downloading full artifact log:", error);
      setError(`Failed to download full artifact log: ${error.message}`);
    }
  };

  return {
    isLoading,
    error,
    setError,
    jaegerUrl,
    extensionsEnabled,
    handleDataReceived,
    fetchStorageTraceDetails,
    handleFullArtifactDownload,
  };
};
