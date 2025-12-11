import React, { useState, useEffect } from "react";
import TimelineRuler from "./TimelineRuler";
import TaskGroup from "./TaskGroup";
import EvalAnalytics from "./EvalAnalytics";
import GraphVisualizerApp from "./graph/graph-components";
import TaskGroupHeader from "./TaskGroupHeader";
import IssuesTable from "./IssuesTable";
import TrajectoryViewer from "./TrajectoryViewer";
import TraceViewer from "./spanViewer/TraceViewer";
import { Download, Settings, ChevronDown } from "lucide-react";
import ResizableColumnDivider from "./ResizableColumnDivider";
import { updateUrlParams, getUrlParams } from "./utils/urlUtils";

// Column width constants
const DEFAULT_NAME_COLUMN_WIDTH = 330;
const MIN_NAME_COLUMN_WIDTH = 120;
const MAX_NAME_COLUMN_WIDTH = 1000;

const TabbedViewer = ({
  data,
  workflowData,
  selectedTask,
  setSelectedTask,
  traceName,
  traceStart,
  traceData,
  serviceName,
  isEmbedded,
  processedData,
  setShowSettings,
  globalStart,
  globalEnd,
  groupWidth,
  expandedGroups,
  handleTaskClick,
  showDependencies,
  setShowDependencies,
  selectedTaskId,
  ancestorIds,
  isFullMode,
  zoomLevel,
  setZoomLevel,
  setGroupWidth,
  shortestDuration,
  baseWidth,
  baseTime,
  traceId,
  jaegerUrl,
  expandedTasks,
  setExpandedTasks,
  onExpandAll,
  onCollapseAll,
  onExpandOneLevel,
  onCollapseOneLevel,
  handleDownload,
  activeTab,
  setActiveTab,
  tabs,
  selectedGroup,
  analyticsType,
  setAnalyticsType,
  serverUrl,
  issues,
  onIssueSelect,
  trajectoryData,
  nameColumnWidth = DEFAULT_NAME_COLUMN_WIDTH,
  onColumnWidthChange,
  analyticsMetrics,
  hideTaskPrefixes = false,
  handleFullArtifactDownload,
  onNodeMetricsClick,
  selectedRunnableNodeId,
  setSelectedRunnableNodeId
}) => {
  const [prevId, setPrevId] = useState(null);
  const [showDownloadDropdown, setShowDownloadDropdown] = useState(false);
  // useEffect(() => {
  //   setActiveTab('tasks');

  // // eslint-disable-next-line react-hooks/exhaustive-deps
  // }, [isEmbedded, selectedGroup]);

  useEffect(() => {
    if (activeTab !== "tasks" && activeTab !== "trajectory") {
      setSelectedTask(null);
    }

    // Set analytics type based on active tab
    if (activeTab === "workflow") {
      setAnalyticsType("group");
    } else {
      setAnalyticsType("trace");
    }
  }, [activeTab, setSelectedTask, setAnalyticsType]);

  // When traceId changes, force iframe refresh
  useEffect(() => {
    if (traceId && traceId !== prevId) {
      setPrevId(traceId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [traceId]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (showDownloadDropdown && !event.target.closest(".download-dropdown")) {
        setShowDownloadDropdown(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showDownloadDropdown]);

  // Toggle between group and trace analytics
  const handleToggleAnalyticsType = () => {
    if (selectedGroup) {
      setAnalyticsType((prev) => (prev === "group" ? "trace" : "group"));
    }
  };

  // Handle column width change - propagate to parent
  const handleColumnWidthChange = (newWidth) => {
    if (onColumnWidthChange) {
      onColumnWidthChange(newWidth);
    }
  };

  // Render group analytics tab content
  const renderGroupAnalytics = () => {
    if (!selectedGroup) return <div>No group selected</div>;

    return (
      <div className="p-4">
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Group Overview</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-600">Group Name</p>
              <p className="font-medium">{selectedGroup.name || selectedGroup.id}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Service</p>
              <p className="font-medium">{serviceName}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Total Traces</p>
              <p className="font-medium">{selectedGroup.traceCount || "—"}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Created</p>
              <p className="font-medium">
                {new Date(selectedGroup.startTime || selectedGroup.createdAt || Date.now()).toLocaleString()}
              </p>
            </div>
          </div>
        </div>

        {/* Group Metrics Charts - Placeholder */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Performance Metrics</h2>
          <div className="h-64 flex items-center justify-center bg-gray-100 rounded">
            <p className="text-gray-500">Group performance metrics visualization goes here</p>
          </div>
        </div>

        {/* Traces in Group Table - Placeholder */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Traces in Group</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  <th className="px-6 py-3 bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Trace ID
                  </th>
                  <th className="px-6 py-3 bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Timestamp
                  </th>
                  <th className="px-6 py-3 bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Duration
                  </th>
                  <th className="px-6 py-3 bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {/* Placeholder rows - would be populated with actual trace data */}
                <tr className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">2/15/2025</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">2.456s</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                      Complete
                    </span>
                  </td>
                </tr>
                <tr className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">2/17/2025</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">3.124s</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                      Complete
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Tabs Navigation with Controls - Fixed at top */}
      <div className="border-b border-gray-200 flex justify-between items-center bg-white sticky top-0 z-20">
        <nav className="flex space-x-2" aria-label="Tabs">
          {tabs.map((tab) => (
            <button
              key={tab}
              data-testid={`click-${tab}-tab`}
              onClick={() => {
                setActiveTab(tab);
                // Update URL to include the new tab and preserve other parameters
                const currentParams = getUrlParams();
                updateUrlParams({
                  ...currentParams,
                  tabName: tab,
                });
              }}
              className={`
                py-4 px-6 border-b-4 text-base
                ${
                  activeTab === tab
                    ? "border-blue-500 text-blue-600 font-bold"
                    : "border-transparent text-gray-600 font-medium hover:text-gray-900 hover:border-gray-300"
                }
              `}
            >
              {tab === "group" ? "Group Analytics" : tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </nav>

        {/* Controls for Tasks tab */}
        {activeTab === "tasks" && (
          <div className="flex items-center space-x-4 pr-4">
            {false && selectedGroup && (
              <button
                onClick={handleToggleAnalyticsType}
                className="px-3 py-1 bg-blue-50 text-blue-600 border border-blue-200 rounded text-sm hover:bg-blue-100"
              >
                {analyticsType === "group" ? "Show Trace View" : "Show Group View"}
              </button>
            )}

            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={showDependencies}
                onChange={(e) => setShowDependencies(e.target.checked)}
                className="form-checkbox h-5 w-5 text-blue-400"
                disabled={!processedData || processedData.length === 0}
              />
              <span className="text-sm font-medium text-gray-700">Dependencies</span>
            </label>

            <div className="flex items-center space-x-2">
              <span className="text-sm font-medium text-gray-700">Zoom:</span>
              <span className="text-lg font-semibold text-gray-700">-</span>
              <input
                type="range"
                min="0"
                max="1000"
                value={zoomLevel}
                onChange={(e) => setZoomLevel(Number(e.target.value))}
                className="w-32"
                disabled={!processedData || processedData.length === 0}
              />
              <span className="text-lg font-semibold text-gray-700">+</span>
            </div>

            <div className="relative download-dropdown">
              <button
                onClick={() => setShowDownloadDropdown(!showDownloadDropdown)}
                className="flex items-center p-2 bg-white border border-blue-500 text-blue-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:border-gray-200 disabled:text-gray-400"
                disabled={!processedData || processedData.length === 0}
              >
                <Download className="w-4 h-4 mr-1" />
                <ChevronDown className="w-3 h-3" />
              </button>

              {showDownloadDropdown && (
                <div className="absolute right-0 mt-1 w-48 bg-white border border-gray-200 rounded-md shadow-lg z-20">
                  <div className="py-1">
                    <button
                      onClick={() => {
                        handleDownload();
                        setShowDownloadDropdown(false);
                      }}
                      className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                    >
                      Tasks JSON
                    </button>
                    <button
                      onClick={() => {
                        handleFullArtifactDownload(traceId, serviceName);
                        setShowDownloadDropdown(false);
                      }}
                      className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                      disabled={!traceId || !serviceName}
                    >
                      Full Artifact Log
                    </button>
                  </div>
                </div>
              )}
            </div>

            {isEmbedded && (
              <button
                onClick={() => setShowSettings(true)}
                className="p-2 bg-white border-blue-500 text-blue-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                <Settings className="w-4 h-4" />
              </button>
            )}
          </div>
        )}
      </div>

      {/* Tab Content Area - Full height and scrollable */}
      <div className="flex-1 overflow-hidden">
        {/* Tasks View */}
        {activeTab === "tasks" && (
          <div className="h-full" data-testid="tasks-tab">
            {globalStart && globalEnd && (
              <div className="flex flex-col h-full">
                {/* Header row with timeline ruler and task header - Sticky */}
                <div className="sticky top-0 z-10 bg-white flex">
                  {/* Name column header with expand/collapse controls */}
                  <div
                    style={{ width: `${nameColumnWidth}px`, position: "relative" }}
                    className="flex-shrink-0 sticky left-0 z-20 bg-white"
                  >
                    <TaskGroupHeader
                      onExpandAll={onExpandAll}
                      onCollapseAll={onCollapseAll}
                      onExpandOneLevel={onExpandOneLevel}
                      onCollapseOneLevel={onCollapseOneLevel}
                    />

                    {/* Add the resizable divider here */}
                    <ResizableColumnDivider
                      initialWidth={nameColumnWidth}
                      minWidth={MIN_NAME_COLUMN_WIDTH}
                      maxWidth={MAX_NAME_COLUMN_WIDTH}
                      onWidthChange={handleColumnWidthChange}
                    />
                  </div>

                  {/* Timeline ruler */}
                  <div className="relative">
                    <TimelineRuler
                      startTime={0}
                      endTime={globalEnd - globalStart}
                      width={groupWidth}
                      zoom={zoomLevel}
                      baseWidth={baseWidth}
                    />
                  </div>
                </div>

                {/* Main scrollable task area */}
                <div className="flex-1 overflow-auto">
                  {expandedGroups.map((taskGroup, index) => (
                    <div key={index}>
                      <TaskGroup
                        tasks={taskGroup}
                        onTaskClick={handleTaskClick}
                        parentWidth={groupWidth + nameColumnWidth}
                        globalStart={globalStart}
                        globalEnd={globalEnd}
                        baseTime={baseTime}
                        showDependencies={showDependencies}
                        selectedTaskId={selectedTaskId}
                        ancestorIds={ancestorIds}
                        isFullMode={isFullMode}
                        zoomLevel={zoomLevel}
                        setZoomLevel={setZoomLevel}
                        setContainerWidth={setGroupWidth}
                        shortestDuration={shortestDuration}
                        baseWidth={baseWidth}
                        expandedTasks={expandedTasks || {}}
                        onExpandAll={onExpandAll}
                        onCollapseAll={onCollapseAll}
                        onExpandOneLevel={onExpandOneLevel}
                        onCollapseOneLevel={onCollapseOneLevel}
                        nameColumnWidth={nameColumnWidth}
                        hideTaskPrefixes={hideTaskPrefixes} // Pass down the prop
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Spans View */}
        <div
          className={`w-full h-full border border-gray-200 rounded transition-opacity duration-300 ${
            activeTab === "spans" ? "opacity-100" : "opacity-0 hidden"
          }`}
        >
          {activeTab === "spans" && traceId && jaegerUrl && (
            <div className="relative w-full h-full">
              {/* Loading message overlay */}
              <div
                id={`loading-message-${traceId}`}
                className="absolute inset-0 flex items-center justify-center bg-white z-10"
              >
                <div className="text-center">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-blue-500 border-t-transparent mb-2"></div>
                  <p className="text-gray-700">Loading trace data...</p>
                </div>
              </div>
              <iframe
                key={prevId}
                src={`${jaegerUrl}/trace/${traceId}?uiEmbed=v0&uiTimelineHideMinimap=1&uiTimelineHideSummary=1`}
                className="w-full h-full"
                title="Jaeger Trace View"
                frameBorder="0"
                onLoad={() => {
                  // Hide the loading message when iframe is loaded
                  const loadingElement = document.getElementById(`loading-message-${traceId}`);
                  if (loadingElement) {
                    loadingElement.style.display = "none";
                  }
                }}
              />
            </div>
          )}

          {activeTab === "spans" && traceId && !jaegerUrl && (
            <div className="p-4">
              {/* <h1 className="text-2xl mb-4">Trace Span Viewer</h1> */}
              <TraceViewer trace={traceData} />
            </div>
          )}

        </div>

        {/* Workflow View */}
        {activeTab === "workflow" && (
          <div className="overflow-auto h-full" data-testid="workflow-tab">
            <GraphVisualizerApp 
              workflowData={workflowData} 
              analyticsMetrics={analyticsMetrics || []} 
              onNodeMetricsClick={onNodeMetricsClick}
              selectedRunnableNodeId = {selectedRunnableNodeId}
            />
          </div>
        )}

        {/* Eval View */}
        {activeTab === "eval" && (
          <div className="overflow-auto h-full px-4" data-testid="eval-tab">
            <EvalAnalytics
              analyticsMetrics={analyticsMetrics}
              onTaskSelect={(task) => {
                setActiveTab("tasks");
                handleTaskClick(task);
              }}
            />
          </div>
        )}

        {/* Issues View */}
        {activeTab === "issues" && (
          <div className="p-4 overflow-auto h-full" data-testid="issues-tab">
            <IssuesTable issues={issues || []} onIssueSelect={onIssueSelect} />
          </div>
        )}

        {/* Trajectory View */}
        {activeTab === "trajectory" && (
          <div className="trajectory-view overflow-auto h-full" data-testid="trajectory-tab">
            <TrajectoryViewer
              data={trajectoryData || []}
              handleTaskClick={handleTaskClick}
              hideTaskPrefixes={hideTaskPrefixes} // Pass down the prop
            />
          </div>
        )}

        {/* Group Analytics View */}
        {activeTab === "group" && (
          <div className="group-analytics-view overflow-auto h-full" data-testid="group-tab">
            {renderGroupAnalytics()}
          </div>
        )}
      </div>
    </div>
  );
};

export default TabbedViewer;
