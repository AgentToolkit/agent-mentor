import TaskHierarchyViewer from "./TaskHierarchyViewer.js";
import SidePanel from "./SidePanel.js";
import { useAuth, storage } from "./AuthComponents.js";
import { SettingsModal } from "./SettingsModal";
import TopBar from "./TopBar";
import MetricsStrip from "./MetricsStrip";
import { useEffect, useState, useCallback, useRef } from "react";
import { Menu, PanelTopClose } from "lucide-react";
import { updateUrlParams } from "./utils/urlUtils.js";

// Import our new modular files
import { DEFAULT_PANEL_CONFIG } from "./constants/panelConfig";
import { findTaskById } from "./utils/hierarchyUtils";
import { computeMetrics, handleGroupMetrics } from "./utils/metricsUtils";
import { useUrlState } from "./hooks/useUrlState";
import { usePanelState } from "./hooks/usePanelState";
import { useDataFetching } from "./hooks/useDataFetching";
import { useGroupManagement } from "./hooks/useGroupManagement";
import { Navigation } from "./main/Navigation";
import { CollapsedTopBar } from "./main/CollapsedTopBar";
import { ResizableSidePanel } from "./main/ResizableSidePanel";
import { LoadingOverlay } from "./main/LoadingOverlay";

export const MainContent = ({
  data,
  setData,
  error,
  setError,
  isEmbedded,
  tenantId,
  setTenantId,
  panelConfig = DEFAULT_PANEL_CONFIG,
  serverUrl,
  setServerUrl,
}) => {
  const [hideTaskPrefixes, setHideTaskPrefixes] = useState(storage.getItem("hideTaskPrefixes") === "true" || false);

  const saveHideTaskPrefixes = (hideTaskPrefixes) => {
    storage.setItem("hideTaskPrefixes", hideTaskPrefixes.toString());
    setHideTaskPrefixes(hideTaskPrefixes);
  };

  // Storage state
  const [serviceName, setServiceName] = useState(storage.getItem("serviceName") || "");

  // UI state
  const [selectedTask, setSelectedTask] = useState(null);
  const [traceName, setTraceName] = useState("");
  const [traceId, setTraceId] = useState(null);
  const [traceStart, setTraceStart] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const [processedData, setProcessedData] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [workflowData, setWorkflowData] = useState(null);
  const [traceData, setTraceData] = useState(null);
  const [activeTab, setActiveTab] = useState("tasks");
  const [metrics, setMetrics] = useState(null);
  const [analyticsMetrics, setAnalyticsMetrics] = useState(null);
  const [issues, setIssues] = useState([]);
  const [selectedIssue, setSelectedIssue] = useState(null);
  const [triggerHandleTask, setTriggerHandleTask] = useState(null);
  const [selectedMetric, setSelectedMetric] = useState(null);
  const [trajectoryData, setTrajectoryData] = useState([]);
  const [analysisStatus, setAnalysisStatus] = useState({
    basic: null,
    advanced: null,
  });
  const [selectedRunnableNodeId, setSelectedRunnableNodeId] = useState(null);
  const runnableMetricsMapRef = useRef(new Map());
  // Tab configuration
  const [tabs, setTabs] = useState(["tasks", "spans", "workflow", "eval", "issues", "trajectory"]);

  // Custom hooks
  const panelState = usePanelState(panelConfig);

  const dataFetching = useDataFetching({
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
    selectedGroup: null, // Will be set by group management hook
    setActiveTab,
    analyticsMetrics,
  });

  const groupManagement = useGroupManagement({
    serverUrl,
    setIsLoading: () => {}, // Will be handled by dataFetching hook
    setError: dataFetching.setError,
    setAnalyticsMetrics,
    setIssues,
    setMetrics,
    setWorkflowData,
    setTrajectoryData,
    fetchStorageTraceDetails: dataFetching.fetchStorageTraceDetails,
    setAnalysisStatus,
    activeTab,
    serviceName,
    analyticsMetrics,
  });

  // Update selectedGroup reference in dataFetching
  dataFetching.selectedGroup = groupManagement.selectedGroup;

  // Storage functions
  const saveServiceName = (newServiceName) => {
    if (newServiceName) {
      storage.setItem("serviceName", newServiceName);
      storage.addServiceToHistory(newServiceName);
      setServiceName(newServiceName);
    }
  };

  // URL state management
  useUrlState({
    serverUrl,
    serviceName,
    activeTab,
    tabs,
    selectedGroup: groupManagement.selectedGroup,
    groupTraces: groupManagement.groupTraces,
    traceId,
    saveServiceName,
    setIsModalOpen,
    setActiveTab,
    handleGroupSelect: groupManagement.handleGroupSelect,
    handleTraceNavigation: groupManagement.handleTraceNavigation,
    fetchStorageTraceDetails: dataFetching.fetchStorageTraceDetails,
    setSelectedGroup: groupManagement.setSelectedGroup,
    setGroupTraces: groupManagement.setGroupTraces,
    setWorkflowData,
    setTrajectoryData,
    setData,
    setProcessedData,
    authFetch: useAuth().authFetch,
  });

  // Update tabs based on embedded mode and extensions
  useEffect(() => {
    let newTabs = isEmbedded
      ? ["tasks", "workflow", "trajectory"]
      : ["tasks", "spans", "workflow", "eval", "issues", "trajectory"];

    // Remove "eval" if extensions are enabled
    if (!dataFetching.extensionsEnabled) {
      newTabs = newTabs.filter((tab) => tab !== "eval");
    }

    setTabs(newTabs);
  }, [isEmbedded, dataFetching.extensionsEnabled]);

  // Reset selected task when data changes
  useEffect(() => {
    setSelectedTask(null);
  }, [data]);
  

  // This useEffect builds the metrics map and stores it in the ref.
  useEffect(() => {
    if (!analyticsMetrics || !Array.isArray(analyticsMetrics) || analyticsMetrics.length === 0) {
      return; 
    }
    const newMap = new Map();
    analyticsMetrics.forEach(metric => {
      (metric.related_to_ids || []).forEach((relatedId, index) => {
        const relatedType = (metric.related_to_types || [])[index];
        // Use a robust, case-insensitive check
        if (relatedType && relatedType.toLowerCase().includes('workflownode')) {
          if (!newMap.has(relatedId)) {
            newMap.set(relatedId, []);
          }
          newMap.get(relatedId).push(metric);
        }
      });
    });

    // Update the ref's current value. This does NOT cause a component re-render.
    runnableMetricsMapRef.current = newMap;

  }, [analyticsMetrics]);



  useEffect(() => {
  // Clear workflow metric selection when switching tabs
    setSelectedMetric(null);
  // Optionally clear other selections too
    setSelectedTask(null);
    setSelectedIssue(null);
  }, [activeTab]);


  // Update metrics when analytics type or issues change
  useEffect(() => {
    if (groupManagement.analyticsType === "group" && groupManagement.selectedGroup) {
      const groupMetrics = handleGroupMetrics(groupManagement.groupTasks, groupManagement.groupTraces, analyticsMetrics);
      setMetrics({
        ...groupMetrics,
        issues: issues.length,
      });
    } else {
      const taskMetrics = computeMetrics(data, analyticsMetrics);
      setMetrics({
        ...taskMetrics,
        issues: issues ? issues.length : 0,
      });
    }
  }, [
    groupManagement.analyticsType,
    issues,
    data,
    groupManagement.groupTasks,
    groupManagement.groupTraces,
    groupManagement.selectedGroup,
    analyticsMetrics,
  ]);

  const saveTenantId = (newTenantId) => {
    storage.setItem("tenantId", newTenantId);
    setTenantId(newTenantId);
  };

  // Event handlers
  const handleIssueSelect = (issue) => {
    setSelectedMetric(null);
    setSelectedIssue(issue);
    if (issue) {
      setSelectedTask(null); // Clear task selection when viewing an issue
    }
  };


  const handleNodeMetricsClick = useCallback((nodeId) => {
    const metricsForNode = runnableMetricsMapRef.current.get(nodeId);
    if (metricsForNode && metricsForNode.length > 0) {
      setSelectedIssue(null);
      setSelectedTask(null);
      setSelectedMetric(metricsForNode);
      // NEW: Set the selected runnable node for tree synchronization
      setSelectedRunnableNodeId(nodeId);
    } else {
      setSelectedMetric(null);
      setSelectedRunnableNodeId(null);
    }
  }, []);


  const handleTaskSelectMain = (task) => {
    // If only an ID was passed, find the full task
    setSelectedMetric(null);
    if (task && task.id && !task.name) {
      const fullTask = findTaskById(task.id, data);
      if (fullTask) {
        setTriggerHandleTask(fullTask);
        return;
      }
    }
    setTriggerHandleTask(task);
  };

  const onTaskHandleComplete = () => {
    setTriggerHandleTask(null);
  };

  // Handle trace or group selection from the modal
  const handleSelectionFromModal = (selection, serviceName) => {
    // Clear previous selections
    groupManagement.setSelectedGroup(null);
    groupManagement.setGroupTraces([]);
    setWorkflowData([]);
    setTrajectoryData([]);

    // Update analysis status if available in the selected item
    if (selection.analysisStatus) {
      setAnalysisStatus(selection.analysisStatus);
    } else {
      setAnalysisStatus({
        basic: null,
        advanced: null,
      });
    }

    // Update URL parameters based on selection
    if (selection.isGroup) {
      updateUrlParams({
        serviceName,
        groupId: selection.id,
        traceId: null,
        tabName: activeTab,
      });
      groupManagement.handleGroupSelect(selection, serviceName);
    } else {
      updateUrlParams({
        serviceName,
        traceId: selection.id,
        groupId: null,
        tabName: activeTab,
      });
      dataFetching.fetchStorageTraceDetails(selection.id, serviceName);
    }
  };

  const getBackgroundColorClass = () => {
    if (groupManagement.selectedGroup) {
      if (groupManagement.analyticsType === "group") {
        return "bg-purple-50"; // Light purple for group view
      } else {
        return "bg-blue-50"; // Light blue for trace within group
      }
    } else if (traceId) {
      return "bg-blue-50"; // Light blue for single trace
    }
    return "bg-gray-100"; // Default background
  };

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Top section - collapsible */}
      {!panelState.isTopCollapsed && panelConfig.topPanel.collapsible && (
        <>
          {!isEmbedded && (
            <Navigation
              serverUrl={serverUrl}
              setServerUrl={setServerUrl}
              tenantId={tenantId}
              setTenantId={saveTenantId}
              serviceName={serviceName}
              setServiceName={saveServiceName}
              onDataReceived={dataFetching.handleDataReceived}
              error={dataFetching.error}
              setError={dataFetching.setError}
              isEmbedded={isEmbedded}
              setIsModalOpen={setIsModalOpen}
              saveHideTaskPrefixes={saveHideTaskPrefixes}
            />
          )}
          {isEmbedded && (
            <button onClick={() => setIsModalOpen(true)} className="p-2 hover:bg-gray-100 rounded-full">
              <Menu className="w-6 h-6" />
            </button>
          )}

          <TopBar
            traceId={traceId}
            timestamp={traceStart}
            serviceName={serviceName}
            setServiceName={saveServiceName}
            serverUrl={serverUrl}
            onTraceSelect={handleSelectionFromModal}
            onTraceNavigation={groupManagement.handleTraceNavigation}
            isModalOpen={isModalOpen}
            setIsModalOpen={setIsModalOpen}
            handleJsonUpload={dataFetching.handleDataReceived}
            selectedGroup={groupManagement.selectedGroup}
            currentTraceIndex={groupManagement.currentTraceIndex}
            totalTraces={groupManagement.groupTraces.length}
            analyticsType={groupManagement.analyticsType}
            analysisStatus={analysisStatus}
            extensionsEnabled={dataFetching.extensionsEnabled}
          />

          <MetricsStrip
            metrics={metrics}
            analyticsType={groupManagement.analyticsType}
            selectedGroup={groupManagement.selectedGroup}
            traceId={traceId}
          />
        </>
      )}

      {/* Show non-collapsible top section if collapsible is disabled */}
      {!panelConfig.topPanel.collapsible && (
        <>
          {!isEmbedded && (
            <Navigation
              serverUrl={serverUrl}
              setServerUrl={setServerUrl}
              tenantId={tenantId}
              setTenantId={saveTenantId}
              serviceName={serviceName}
              setServiceName={saveServiceName}
              onDataReceived={dataFetching.handleDataReceived}
              error={dataFetching.error}
              setError={dataFetching.setError}
              isEmbedded={isEmbedded}
              setIsModalOpen={setIsModalOpen}
              saveHideTaskPrefixes={saveHideTaskPrefixes}
            />
          )}
          {isEmbedded && (
            <button onClick={() => setIsModalOpen(true)} className="p-2 hover:bg-gray-100 rounded-full">
              <Menu className="w-6 h-6" />
            </button>
          )}

          <TopBar
            traceId={traceId}
            timestamp={traceStart}
            serviceName={serviceName}
            setServiceName={saveServiceName}
            serverUrl={serverUrl}
            onTraceSelect={handleSelectionFromModal}
            onTraceNavigation={groupManagement.handleTraceNavigation}
            isModalOpen={isModalOpen}
            setIsModalOpen={setIsModalOpen}
            handleJsonUpload={dataFetching.handleDataReceived}
            selectedGroup={groupManagement.selectedGroup}
            currentTraceIndex={groupManagement.currentTraceIndex}
            totalTraces={groupManagement.groupTraces.length}
            analyticsType={groupManagement.analyticsType}
            analysisStatus={analysisStatus}
            extensionsEnabled={dataFetching.extensionsEnabled}
          />

          <MetricsStrip
            metrics={metrics}
            analyticsType={groupManagement.analyticsType}
            selectedGroup={groupManagement.selectedGroup}
            traceId={traceId}
          />
        </>
      )}

      {/* Collapsed top bar */}
      {panelState.isTopCollapsed && panelConfig.topPanel.collapsible && (
        <CollapsedTopBar
          traceId={traceId}
          serviceName={serviceName}
          selectedGroup={groupManagement.selectedGroup}
          onExpand={panelState.handleToggleTopCollapse}
          analyticsType={groupManagement.analyticsType}
          config={panelConfig.topPanel}
        />
      )}

      {/* Collapse/Expand button for top panels */}
      {!panelState.isTopCollapsed && panelConfig.topPanel.collapsible && (
        <div className="absolute top-1 right-2 z-30">
          <button
            onClick={panelState.handleToggleTopCollapse}
            className="p-1 bg-blue-50 hover:bg-blue-100 rounded shadow-sm border border-blue-200 text-blue-600 hover:text-blue-700 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
            title="Collapse top panels"
          >
            <PanelTopClose className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Main content flex container with context-based background */}
      <div className={`flex flex-1 ${getBackgroundColorClass()} overflow-hidden`}>
        {/* Main content area - expands to full width when side panel is hidden */}
        <div
          className={`${
            ["workflow", "spans", "eval"].includes(activeTab) || panelState.isSidePanelCollapsed
              ? "w-full"
              : "flex-grow"
          } h-full overflow-hidden transition-all duration-300 pl-2 pr-4`}
        >
          <div className="h-full bg-white">
            <TaskHierarchyViewer
              data={data}
              workflowData={workflowData}
              selectedTask={selectedTask}
              setSelectedTask={setSelectedTask}
              traceName={traceName}
              traceId={traceId}
              traceStart={traceStart}
              traceData={traceData}
              serviceName={serviceName}
              isEmbedded={isEmbedded}
              processedData={processedData}
              setShowSettings={setShowSettings}
              jaegerUrl={dataFetching.jaegerUrl}
              error={dataFetching.error}
              setError={dataFetching.setError}
              activeTab={activeTab}
              setActiveTab={setActiveTab}
              tabs={tabs}
              selectedGroup={groupManagement.selectedGroup}
              analyticsType={groupManagement.analyticsType}
              setAnalyticsType={groupManagement.setAnalyticsType}
              serverUrl={serverUrl}
              issues={issues}
              onIssueSelect={handleIssueSelect}
              triggerHandleTask={triggerHandleTask}
              onTaskHandleComplete={onTaskHandleComplete}
              trajectoryData={trajectoryData}
              analyticsMetrics={analyticsMetrics}
              hideTaskPrefixes={hideTaskPrefixes}
              handleFullArtifactDownload={dataFetching.handleFullArtifactDownload}
              onNodeMetricsClick={handleNodeMetricsClick}
              selectedRunnableNodeId={selectedRunnableNodeId}
              setSelectedRunnableNodeId={setSelectedRunnableNodeId}
            />
          </div>
        </div>

        {/* Resizable Side panel - conditionally shown based on active tab */}
        {!["spans", "eval"].includes(activeTab) && (
          <ResizableSidePanel
            isCollapsed={panelState.isSidePanelCollapsed}
            width={panelState.sidePanelWidth}
            onWidthChange={panelState.handleSidePanelWidthChange}
            onToggleCollapse={panelState.handleToggleSidePanelCollapse}
            config={panelConfig.sidePanel}
          >
            <SidePanel
              task={selectedTask}
              handleTaskClick={handleTaskSelectMain}
              setData={setData}
              serverUrl={serverUrl}
              serviceName={serviceName}
              issues={issues}
              selectedIssue={selectedIssue}
              onIssueSelect={handleIssueSelect}
              setActiveTab={setActiveTab}
              hideTaskPrefixes={hideTaskPrefixes}
              selectedMetric={selectedMetric}
            />
          </ResizableSidePanel>
        )}
      </div>

      {showSettings && (
        <SettingsModal
          setShowSettings={setShowSettings}
          serverUrl={serverUrl}
          setServerUrl={setServerUrl}
          tenantId={tenantId}
          setTenantId={saveTenantId}
          serviceName={serviceName}
          setServiceName={saveServiceName}
          hideTaskPrefixes={hideTaskPrefixes}
          setHideTaskPrefixes={saveHideTaskPrefixes}
        />
      )}

      {/* Loading overlay */}
      <LoadingOverlay isLoading={groupManagement.isLoading || dataFetching.isLoading} />
    </div>
  );
};
