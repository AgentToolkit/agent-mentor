import React, { useState, useEffect, useRef, useMemo } from "react";
import TabbedViewer from "./TabbedViewer";
import { debounce } from "lodash";
// Remove the import for NAME_COLUMN_WIDTH

// Inject CSS to global styles or as a style tag in your HTML
const stripesStyle = `
  .bg-stripes {
    --stripe-color: rgba(255, 255, 255, 0.25); /* Adjust opacity to control lightness */
    background-image: linear-gradient(45deg,
      var(--stripe-color) 25%,
      transparent 25%,
      transparent 50%,
      var(--stripe-color) 50%,
      var(--stripe-color) 75%,
      transparent 75%,
      transparent);
    background-size: 10px 10px;
  }
`;

const containerPadding = 64;
const MIN_WIDTH = 1150;
// Add default column width constant
const DEFAULT_NAME_COLUMN_WIDTH = 330;

const TaskHierarchyViewer = ({
  data,
  workflowData,
  selectedTask,
  setSelectedTask,
  traceName,
  traceId,
  traceStart,
  traceData,
  serviceName,
  isEmbedded,
  processedData,
  setShowSettings,
  jaegerUrl,
  error,
  setError,
  activeTab,
  setActiveTab,
  tabs,
  selectedGroup,
  analyticsType,
  setAnalyticsType,
  serverUrl,
  issues,
  onIssueSelect,
  triggerHandleTask,
  onTaskHandleComplete,
  trajectoryData,
  analyticsMetrics,
  hideTaskPrefixes = false,
  handleFullArtifactDownload,
  onNodeMetricsClick,
  selectedRunnableNodeId,
  setSelectedRunnableNodeId
}) => {
  const [expandedGroups, setExpandedGroups] = useState([]);
  const [expandedTasks, setExpandedTasks] = useState({}); // Map of task IDs to expanded state
  const [groupWidth, setGroupWidth] = useState(MIN_WIDTH);
  const [baseTime, setBaseTime] = useState(null);
  const [globalStart, setGlobalStart] = useState(null);
  const [globalEnd, setGlobalEnd] = useState(null);
  const [showDependencies, setShowDependencies] = useState(true);
  const [zoomLevel, setZoomLevel] = useState(0); // 0 to 100
  const [ancestorIds, setAncestorIds] = useState([]);
  const containerRef = useRef(null);
  const scrollContainerRef = useRef(null);
  const [baseWidth, setBaseWidth] = useState(0);
  const [shortestDuration, setShortestDuration] = useState(0);
  const [scrollParent, setScrollParent] = useState(null);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const selectedTaskId = selectedTask ? selectedTask.id : -1;
  const isFullMode = zoomLevel === 100;
  const isLoading = useRef(true);
  const prevWidthRef = useRef(baseWidth);
  // Add state for name column width
  const [nameColumnWidth, setNameColumnWidth] = useState(DEFAULT_NAME_COLUMN_WIDTH);

  // Helper function to build task hierarchy for level calculations
  const buildTaskHierarchy = (taskData) => {
    const taskLevels = {};
    const taskChildrenMap = {};

    const assignLevels = (tasks, level = 0) => {
      tasks.forEach((task) => {
        taskLevels[task.id] = level;
        if (task.children) {
          taskChildrenMap[task.id] = task.children.map((child) => child.id);
          assignLevels(task.children, level + 1);
        } else {
          taskChildrenMap[task.id] = [];
        }
      });
    };

    assignLevels(taskData);
    return { taskLevels, taskChildrenMap };
  };

  // Handlers for expand/collapse actions
  const handleExpandAll = () => {
    const allExpanded = {};
    Object.keys(expandedTasks).forEach((taskId) => {
      allExpanded[taskId] = true;
    });
    setExpandedTasks(allExpanded);
  };

  const handleCollapseAll = () => {
    const allCollapsed = {};
    Object.keys(expandedTasks).forEach((taskId) => {
      allCollapsed[taskId] = false;
    });
    setExpandedTasks(allCollapsed);
  };

  const handleExpandOneLevel = () => {
    const { taskLevels, taskChildrenMap } = buildTaskHierarchy(data);
    const newExpandedTasks = { ...expandedTasks };

    // Find the next unexpanded level
    let maxExpandedLevel = -1;
    Object.entries(expandedTasks).forEach(([taskId, isExpanded]) => {
      if (isExpanded) {
        maxExpandedLevel = Math.max(maxExpandedLevel, taskLevels[taskId] || 0);
      }
    });

    // Expand tasks at the next level
    Object.entries(taskLevels).forEach(([taskId, level]) => {
      if (level === maxExpandedLevel + 1 && taskChildrenMap[taskId]?.length > 0) {
        newExpandedTasks[taskId] = true;
      }
    });

    setExpandedTasks(newExpandedTasks);
  };

  const handleCollapseOneLevel = () => {
    const { taskLevels } = buildTaskHierarchy(data);
    const newExpandedTasks = { ...expandedTasks };

    // Find the deepest expanded level
    let maxExpandedLevel = -1;
    Object.entries(expandedTasks).forEach(([taskId, isExpanded]) => {
      if (isExpanded) {
        maxExpandedLevel = Math.max(maxExpandedLevel, taskLevels[taskId] || 0);
      }
    });

    // Collapse tasks at the deepest level
    if (maxExpandedLevel >= 0) {
      Object.entries(expandedTasks).forEach(([taskId, isExpanded]) => {
        if (isExpanded && taskLevels[taskId] === maxExpandedLevel) {
          newExpandedTasks[taskId] = false;
        }
      });
    }

    setExpandedTasks(newExpandedTasks);
  };

  // Handle column width changes from child components
  const handleColumnWidthChange = (newWidth) => {
    setNameColumnWidth(newWidth);
  };

  useEffect(() => {
    const handleMouseMove = (event) => {
      setMousePosition({
        x: event.clientX,
        y: event.clientY,
      });
    };

    window.addEventListener("mousemove", handleMouseMove);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
    };
  }, []);

  useEffect(() => {
    var _scrollParent = null;
    if (scrollParent == null) {
      const containers = scrollContainerRef.current?.getElementsByClassName("scroll-container");
      if (!containers || containers.length === 0) return;

      // Use the first scroll container as reference for the parent actually!
      setScrollParent(containers[0].parentNode);
      _scrollParent = containers[0].parentNode;
    } else {
      _scrollParent = scrollParent;
    }
    // const delta_adjustment = (_scrollParent.clientWidth / 2)
    const delta_adjustment = mousePosition.x;
    const viewportCenter = _scrollParent.scrollLeft + delta_adjustment;
    const scrollRatio = prevWidthRef.current === 0 ? 0 : viewportCenter / prevWidthRef.current;
    const newScrollLeft = scrollRatio * groupWidth - delta_adjustment;

    if (isLoading.current) {
      _scrollParent.scrollLeft = 0;
    } else {
      _scrollParent.scrollLeft = newScrollLeft;
      // pass - TODO: REMOVE this scroll handling
    }

    prevWidthRef.current = groupWidth;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [groupWidth, scrollParent]); // We ignore the eslint for mousePosition because it causes redundant computation

  const debouncedSetZoomLevel = useMemo(
    () =>
      debounce((newValue) => {
        setZoomLevel(newValue);
      }, 8), // roughly one frame at 60fps
    []
  );

  useEffect(() => {
    const handleWheel = (event) => {
      if (event.ctrlKey || event.metaKey) {
        event.preventDefault();
        debouncedSetZoomLevel((prevLevel) => {
          const increment =
            //  prevLevel <= 100 ? 1 :
            prevLevel <= 250 ? 5 : prevLevel <= 500 ? 10 : prevLevel <= 1000 ? 25 : prevLevel <= 3000 ? 50 : 100;
          const delta = -Math.sign(event.deltaY) * increment;
          return Math.min(1000, Math.max(0, prevLevel + delta));
        });
      }
    };

    const element = scrollContainerRef.current;
    if (element) {
      element.addEventListener("wheel", handleWheel, { passive: false });
    }

    return () => {
      if (element) {
        element.removeEventListener("wheel", handleWheel);
      }
    };
  }, [debouncedSetZoomLevel]);

  useEffect(() => {
    isLoading.current = true;
    setZoomLevel(0);
    const allTasks = data.flatMap((task) => [task, ...(task.children || [])]);

    const firstTaskStartTime = Math.min(...allTasks.map((task) => new Date(task.start_time)));
    const lastTaskEndTime = Math.max(...allTasks.map((task) => new Date(task.end_time)));
    const shortestTaskDuration = Math.min(
      ...allTasks.map((task) => new Date(task.end_time) - new Date(task.start_time))
    );
    setShortestDuration(shortestTaskDuration);
    setBaseTime(firstTaskStartTime);
    setGlobalStart(firstTaskStartTime);
    setGlobalEnd(lastTaskEndTime);
    setExpandedGroups([data]);

    // Initialize expandedTasks to track all potential parent tasks
    const initialExpandedTasks = {};

    // Helper function to recursively process task hierarchy
    const processTaskHierarchy = (tasks) => {
      tasks.forEach((task) => {
        if (task.children && task.children.length > 0) {
          initialExpandedTasks[task.id] = true; // Changed from false to true to start with all tasks expanded
          processTaskHierarchy(task.children); // Process children recursively
        }
      });
    };

    processTaskHierarchy(data);
    setExpandedTasks(initialExpandedTasks);

    // Set initial width based on container width
    const containerWidth = containerRef.current?.clientWidth || MIN_WIDTH;
    setBaseWidth(Math.max(MIN_WIDTH, containerWidth - containerPadding - nameColumnWidth)); // Use nameColumnWidth
    setGroupWidth(Math.max(MIN_WIDTH, containerWidth - containerPadding - nameColumnWidth)); // Use nameColumnWidth
    setTimeout(() => {
      isLoading.current = false;
    }, 250);
  }, [data, scrollParent, nameColumnWidth]); // Add nameColumnWidth as dependency

  const findAncestors = (taskId, tasks) => {
    const ancestors = [];
    const findParent = (id, taskList) => {
      for (const task of taskList) {
        if (task.children && task.children.some((child) => child.id === id)) {
          ancestors.push(task.id);
          if (task.parent_id) {
            findParent(task.id, data);
          }
        }
        if (task.children) {
          findParent(id, task.children);
        }
      }
    };
    findParent(taskId, tasks);
    return ancestors;
  };

  const fillTaskDetails = (task) => {
    const ancestors = findAncestors(task.id, data);
    setAncestorIds(ancestors);

    // Find all ancestor tasks
    const ancestorTasks = ancestors
      .map(
        (id) =>
          data.find((task) => task.id === id) || data.flatMap((t) => t.children || []).find((task) => task.id === id)
      )
      .filter(Boolean);

    return {
      ...task,
      ancestorIds: ancestors,
      ancestorTasks,
    };
  };

  useEffect(() => {
    if (triggerHandleTask) {
      // Triggered from Main
      handleTaskClick(triggerHandleTask);
      // Notify Main that the action is complete
      onTaskHandleComplete();
    }
    // eslint-disable-next-line
  }, [triggerHandleTask, onTaskHandleComplete]);

  const handleTaskClick = (task) => {
    // Check if this is a request to toggle expansion
    if (task.toggleExpand) {
      // Toggle expansion state for this task
      setExpandedTasks((prev) => ({
        ...prev,
        [task.id]: !prev[task.id],
      }));
      return;
    }

    // Check if this is a request to show the issues tab
    const showIssuesTab = task.showIssuesTab;

    // Remove the flag before passing task to other functions
    if (showIssuesTab) {
      delete task.showIssuesTab;
    }

    onIssueSelect(null); // Clear issue selection when viewing a task
    // Otherwise, handle normal task selection
    setSelectedTask(fillTaskDetails(task));

    // Create a function to find all parent tasks in the hierarchy
    const findAllParents = (taskId) => {
      let parentIds = [];

      const findParent = (id, tasks) => {
        for (const t of tasks) {
          // Check if this task is a parent of our target
          if (t.children && t.children.some((child) => child.id === id)) {
            parentIds.push(t.id);

            // If this task has a parent, recursively find it
            if (t.parent_id) {
              findParent(t.id, data);
            }
          }

          // Also search in children
          if (t.children) {
            findParent(id, t.children);
          }
        }
      };

      findParent(taskId, data);
      return parentIds;
    };

    // Expand parent tasks up to this one if necessary
    const parentIds = task.parent_id ? findAllParents(task.id) : [];
    if (parentIds.length > 0) {
      setExpandedTasks((prev) => {
        const parentsToExpand = {};

        // Set all parents to expanded state
        parentIds.forEach((id) => {
          parentsToExpand[id] = true;
        });

        return { ...prev, ...parentsToExpand };
      });
    }

    if (task.children && task.children.length > 0) {
      // Auto-expand this task when selected
      setExpandedTasks((prev) => ({
        ...prev,
        [task.id]: true,
      }));

      // Update the expanded groups as before (for backward compatibility)
      setExpandedGroups((prev) => {
        const index = prev.findIndex((group) => group.includes(task));
        if (index !== -1) {
          return [...prev.slice(0, index + 1), task.children];
        }
        return prev;
      });
      setGroupWidth(groupWidth);
    }

    // Set the active tab to 'issues' if requested
    if (showIssuesTab) {
      setActiveTab("tasks"); // First ensure we're on the tasks tab

      // Use a small timeout to ensure the task is selected first
      setTimeout(() => {
        onIssueSelect(showIssuesTab);
        // const issuesTab = document.querySelector('[data-testid="click-issues-tab"]');
        // if (issuesTab) {
        //   issuesTab.click();
        // }
      }, 100);
    }
  };

  useEffect(() => {
    // Basically it means it was a propagation from an external container
    if (selectedTask != null && selectedTask.ancestorIds == null) handleTaskClick(selectedTask);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTask]);

  const handleDownload = () => {
    if (!processedData) return;

    // const blob = new Blob([JSON.stringify(processedData, null, 2)], { type: 'application/json' });
    // Avoid circular references!!!
    const blob = new Blob(
      [
        JSON.stringify(
          processedData,
          (key, value) => {
            // Skip properties that might cause circular references
            if (key === "related_elements") {
              return undefined; // This will exclude the property
            }
            return value;
          },
          2
        ),
      ],
      { type: "application/json" }
    );

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "processed_data.json";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col h-full overflow-hidden" ref={containerRef}>
      <style>{stripesStyle}</style>
      {error && (
        <div className="px-4 pt-4 mb-2">
          <span className="block p-2 bg-red-50 border-l-4 border-red-500 text-red-700 text-sm">{error}</span>
        </div>
      )}

      <div className="flex-1 overflow-hidden" ref={scrollContainerRef}>
        <TabbedViewer
          data={data}
          workflowData={workflowData}
          selectedTask={selectedTask}
          setSelectedTask={setSelectedTask}
          traceName={traceName}
          traceStart={traceStart}
          traceData={traceData}
          serviceName={serviceName}
          isEmbedded={isEmbedded}
          processedData={processedData}
          setShowSettings={setShowSettings}
          globalStart={globalStart}
          globalEnd={globalEnd}
          groupWidth={groupWidth}
          expandedGroups={expandedGroups}
          handleTaskClick={handleTaskClick}
          showDependencies={showDependencies}
          setShowDependencies={setShowDependencies}
          selectedTaskId={selectedTaskId}
          ancestorIds={ancestorIds}
          isFullMode={isFullMode}
          zoomLevel={zoomLevel}
          setZoomLevel={setZoomLevel}
          setGroupWidth={setGroupWidth}
          shortestDuration={shortestDuration}
          baseWidth={baseWidth}
          baseTime={baseTime}
          traceId={traceId}
          jaegerUrl={jaegerUrl}
          expandedTasks={expandedTasks}
          setExpandedTasks={setExpandedTasks}
          onExpandAll={handleExpandAll}
          onCollapseAll={handleCollapseAll}
          onExpandOneLevel={handleExpandOneLevel}
          onCollapseOneLevel={handleCollapseOneLevel}
          handleDownload={handleDownload}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          tabs={tabs}
          selectedGroup={selectedGroup}
          analyticsType={analyticsType}
          setAnalyticsType={setAnalyticsType}
          serverUrl={serverUrl}
          issues={issues}
          onIssueSelect={onIssueSelect}
          trajectoryData={trajectoryData}
          nameColumnWidth={nameColumnWidth}
          onColumnWidthChange={handleColumnWidthChange}
          analyticsMetrics={analyticsMetrics}
          hideTaskPrefixes={hideTaskPrefixes}
          handleFullArtifactDownload={handleFullArtifactDownload}
          onNodeMetricsClick = {onNodeMetricsClick}
          selectedRunnableNodeId={selectedRunnableNodeId}
          setSelectedRunnableNodeId={setSelectedRunnableNodeId}
        />
      </div>
    </div>
  );
};

export default TaskHierarchyViewer;
