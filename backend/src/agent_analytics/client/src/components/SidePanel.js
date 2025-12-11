import React, { useState, useEffect } from "react";
import TreeNode from "./TreeNode";
import complexIcon from "../icons/complex.svg";
import llmCallIcon from "../icons/llm_call.svg";
import toolCallIcon from "../icons/tool_call.svg";
import TaskIssuesPanel from "./TaskIssuesPanel";
import IssuesSidePanel from "./IssuesSidePanel";
import WorkflowMetricsSidePanel from "./WorkflowMetricsSidePanel";
import { ChevronRight, Timer, Copy, Play, Pause } from "lucide-react";
import { formatTaskName } from "./utils/taskNameUtils";

const OverlayModal = ({ isOpen, onClose, title, children }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white w-[80vw] h-[80vh] rounded flex flex-col relative">
        <div className="flex justify-between items-center p-4 border-b">
          <h3 className="text-lg font-medium">{title}</h3>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-full"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
        <div className="flex-1 overflow-auto p-6">{children}</div>
      </div>
    </div>
  );
};
export { OverlayModal };

const TaskBreadcrumbs = ({
  task,
  globalTasks,
  setSelectedTask,
  findTaskById,
  hideTaskPrefixes = false,
}) => {
  if (!task.ancestorIds) {
    const displayName = formatTaskName(task.name, hideTaskPrefixes);
    return (
      <span
        className="text-blue-600 hover:text-blue-800 cursor-pointer"
        onClick={() => setSelectedTask(task)}
      >
        {displayName}
      </span>
    );
  }

  const ancestors = [...task.ancestorIds].reverse();
  const fullPath = [...ancestors, task.id];

  return (
    <div className="flex items-center flex-wrap gap-2 text-xs">
      {fullPath.map((id, index) => {
        const isLast = index === fullPath.length - 1;
        const currentTask =
          id === task.id ? task : findTaskById(id, globalTasks);
        const rawTaskName = currentTask?.name || `Task ${id}`;
        const taskName = formatTaskName(rawTaskName, hideTaskPrefixes);

        return (
          <React.Fragment key={id}>
            <span
              className={`cursor-pointer ${
                isLast
                  ? "text-gray-800 font-medium"
                  : "text-blue-600 hover:text-blue-800 hover:underline"
              }`}
              onClick={() => setSelectedTask(currentTask)}
            >
              {taskName}
            </span>
            {!isLast && <ChevronRight className="text-gray-400" size={16} />}
          </React.Fragment>
        );
      })}
    </div>
  );
};

// TopSidePanel component to show task overview and key metrics
const TopSidePanel = ({
  task,
  globalTasks,
  setSelectedTask,
  hideTaskPrefixes = false,
}) => {
  // Helper to find a task by ID in the task tree
  const findTaskById = (id, tasks) => {
    if (!tasks) return null;
    for (const task of tasks) {
      if (task.id === id) return task;
      if (task.children) {
        const found = findTaskById(id, task.children);
        if (found) return found;
      }
    }
    return null;
  };

  // Format the task name for display
  const displayName = formatTaskName(task.name, hideTaskPrefixes);

  // Extract key metrics for the top display
  const keyMetrics = {
    type: task.tags ? task.tags.join(" / ") : "",
    duration: task.metrics
      ? `${Math.round(task.metrics.execution_time * 1000)} ms`
      : "245 ms",
    startTime: task.start_time,
    endTime: task.end_time,
  };

  const getTaskStyle = () => {
    if (!task.tags || task.tags.length === 0)
      return {
        colorClass: "gray-300",
        icon: null,
      };

    if (task.tags.includes("tool_call"))
      return {
        colorClass: "lime-500",
        icon: (
          <img src={toolCallIcon} alt="" className="w-4 h-4 mr-1 shrink-0" />
        ),
      };

    if (task.tags.includes("llm_call"))
      return {
        colorClass: "violet-400",
        icon: (
          <img src={llmCallIcon} alt="" className="w-4 h-4 mr-1 shrink-0" />
        ),
      };

    if (task.tags.includes("complex"))
      return {
        colorClass: "sky-300",
        icon: (
          <img src={complexIcon} alt="" className="w-4 h-4 mr-1 shrink-0" />
        ),
      };

    if (task.tags.includes("manual"))
      return {
        colorClass: "amber-500",
        icon: null,
      };

    return {
      colorClass: "gray-300",
      icon: null,
    };
  };

  const { colorClass, icon } = getTaskStyle();
  const taskStyle = `bg-white p-6 mb-4 border-t-4 border-solid border-${colorClass}`;

  return (
    <div className={taskStyle}>
      <div className="text-sm text-gray-600 mb-1">
        <TaskBreadcrumbs
          task={task}
          globalTasks={globalTasks}
          setSelectedTask={setSelectedTask}
          findTaskById={findTaskById}
          hideTaskPrefixes={hideTaskPrefixes}
        />
      </div>
      <h2 className="text-xl font-semibold mb-4">{displayName}</h2>

      <div className="grid grid-cols-2 gap-4">
        <div className="flex items-start gap-2">
          <span className="p-2">{icon}</span>
          <div>
            <p className="text-sm text-gray-600">Tags</p>
            <p className="font-medium text-sm">{keyMetrics.type}</p>
          </div>
        </div>

        <div className="flex items-start gap-2">
          <span className="p-2">
            <Timer className="w-4 h-4" />
          </span>
          <div>
            <p className="text-sm text-gray-600">Duration</p>
            <p className="font-medium text-sm">{keyMetrics.duration}</p>
          </div>
        </div>

        <div className="flex items-start gap-2">
          <span className="p-2">
            <Play className="w-4 h-4" />
          </span>
          <div>
            <p className="text-sm text-gray-600">Start</p>
            <>
              <span className="block text-sm font-medium">
                {new Date(keyMetrics.startTime).toLocaleString(undefined, {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                  fractionalSecondDigits: 3,
                  hour12: false,
                })}
              </span>
              <span className="block text-sm text-gray-500">
                {new Date(keyMetrics.startTime).toLocaleString(undefined, {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                })}
              </span>
            </>
          </div>
        </div>

        <div className="flex items-start gap-2">
          <span className="p-2">
            <Pause className="w-4 h-4" />
          </span>
          <div>
            <p className="text-sm text-gray-600">End</p>
            <>
              <span className="block text-sm font-medium ">
                {new Date(keyMetrics.endTime).toLocaleString(undefined, {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                  fractionalSecondDigits: 3,
                  hour12: false,
                })}
              </span>
              <span className="block text-sm text-gray-500">
                {new Date(keyMetrics.endTime).toLocaleString(undefined, {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                })}
              </span>
            </>
          </div>
        </div>
      </div>
    </div>
  );
};

// BottomSidePanel component with tabs
const BottomSidePanel = ({ task, issues, onIssueSelect }) => {
  const [activeTab, setActiveTab] = useState("attributes");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [tabCopyContent, setTabCopyContent] = useState("");

  // Check if task has issues and set the active tab to 'issues' if it does
  useEffect(() => {
    if (task && task.issues && task.issues.length > 0 && task.showIssuesTab) {
      setActiveTab("issues");
      // Remove the flag to prevent re-triggering
      delete task.showIssuesTab;
    }
  }, [task]);

  // Add expand button to content
  const ExpandButton = () => (
    <button
      onClick={() => setIsModalOpen(true)}
      className="relative text-blue-700 hover:bg-gray-200 rounded-full"
      title="Expand view"
    >
      <svg
        className="w-6 h-6"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"
        />
      </svg>
    </button>
  );

  const CopyButton = ({ task_text }) => {
    const handleCopy = () => {
      // First try the modern Clipboard API
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard
          .writeText(JSON.stringify(task_text))
          .catch((err) => {
            console.error("Failed to copy with Clipboard API:", err);
            // Fall back to older method if Clipboard API fails
            fallbackCopyText(task_text);
          });
      } else {
        // Use fallback for non-HTTPS or unsupported browsers
        fallbackCopyText(task_text);
      }
    };

    const fallbackCopyText = (text) => {
      const textArea = document.createElement("textarea");
      textArea.value = JSON.stringify(text);
      textArea.style.position = "fixed"; // Avoid scrolling to bottom
      textArea.style.top = "0";
      textArea.style.left = "0";
      textArea.style.width = "2em";
      textArea.style.height = "2em";
      textArea.style.padding = "0";
      textArea.style.border = "none";
      textArea.style.outline = "none";
      textArea.style.boxShadow = "none";
      textArea.style.background = "transparent";

      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();

      try {
        document.execCommand("copy");
      } catch (err) {
        console.error("Failed to copy text:", err);
      }

      document.body.removeChild(textArea);
    };

    return (
      <button
        onClick={handleCopy}
        className="relative text-blue-700 hover:bg-gray-200 rounded-full"
        title="Copy"
      >
        <Copy className="w-6 h-6" />
      </button>
    );
  };

  const isDate = (key) => ["start_time", "end_time"].includes(key);

  // Shared helper functions
  const processGeneralTabData = (task) => {
    const excludedKeys = [
      "children",
      "metrics",
      "input",
      "output",
      "name",
      "ancestorIds",
      "parent_id",
      "dependent_ids",
      "ancestorTasks",
      "tags",
      "attributes",
      "verticalPosition",
      "isVisible",
      "id",
      "log_reference",
      "exceptions",
      "events",
    ];

    return Object.entries(task)
      .filter(([key]) => !excludedKeys.includes(key))
      .map(([key, value]) => {
        let val = JSON.stringify(value);
        val = val
          .replace(/^"(.*)"$/, "$1")
          .replace(/^\[(.*)\]$/, "$1")
          .replace(/^\{(.*)\}$/, "$1")
          .replace(/^\((.*)\)$/, "$1");

        if (val === "" || val === "null") return null;

        return { key, value: val };
      })
      .filter(Boolean); // Remove null entries
  };

  const processMetricsData = (metrics) => {
    if (!metrics) return [];

    return Object.entries(metrics).flatMap(([key, value]) => {
      if (typeof value === "object" && value !== null) {
        return Object.entries(value).map(([subKey, subValue]) => ({
          key: `${key}.${subKey}`,
          value: subValue,
        }));
      }
      return [{ key, value }];
    });
  };

  const processAttributesData = (task) => {
    const taskLogRef = task.log_reference || {};
    taskLogRef.task_id = task.id;
    task.input =
      task.input && task.input.inputs ? task.input.inputs : task.input;
    task.output =
      task.output && task.output.outputs ? task.output.outputs : task.output;

    return {
      attributes: task.attributes || {},
      // Either objects of plain strings are left as-is, strings which "look like" JSON (start with '{') are parsed
      input:
        task.input != null
          ? typeof task.input !== "object" &&
            task.input.length > 0 &&
            task.input[0] === "{"
            ? JSON.parse(task.input)
            : task.input
          : {},
      output:
        task.output != null
          ? typeof task.output !== "object" &&
            task.output.length > 0 &&
            task.output[0] === "{"
            ? JSON.parse(task.output)
            : task.output
          : {},
      references: taskLogRef,
    };
  };

  // Use effect to update copy content when tab or task changes
  useEffect(() => {
    if (!task) return;

    let content = "";

    switch (activeTab) {
      case "general":
        const generalData = processGeneralTabData(task);
        content = generalData
          .map(({ key, value }) => `${key}:${value}`)
          .join("\n");
        break;

      case "metrics":
        const metricsData = processMetricsData(task.metrics);
        content = metricsData
          .map(({ key, value }) => `${key}:${value}`)
          .join("\n");
        break;

      case "attributes":
        content = processAttributesData(task);
        break;

      case "issues":
        // For issues, we just provide the task ID
        content = task.issues;
        break;

      default:
        break;
    }

    setTabCopyContent(content);
  }, [task, activeTab]);

  if (!task) return null;

  const renderTabContent = () => {
    if (!task) return null;

    switch (activeTab) {
      case "general":
        return (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              {processGeneralTabData(task).map(({ key, value }) => (
                <div key={key} className="break-words">
                  <p className="text-sm text-gray-600">{key}</p>
                  <p className="font-medium">
                    {isDate(key) ? (
                      <>
                        <span className="block">
                          {new Date(value).toLocaleString(undefined, {
                            hour: "2-digit",
                            minute: "2-digit",
                            second: "2-digit",
                            fractionalSecondDigits: 3,
                            hour12: false,
                          })}
                        </span>
                        <span className="block text-sm text-gray-500">
                          {new Date(value).toLocaleString(undefined, {
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                          })}
                        </span>
                      </>
                    ) : (
                      value
                    )}
                  </p>
                </div>
              ))}
            </div>
          </div>
        );

      case "metrics":
        return (
          <div className="space-y-4 overflow-x-hidden">
            {task.metrics ? (
              <div className="w-full">
                <table className="w-full table-fixed">
                  <thead>
                    <tr className="bg-gray-50">
                      <th className="w-3/4 px-2 py-2 text-left text-sm font-medium text-gray-500 break-words">
                        Metric
                      </th>
                      <th className="w-1/4 px-2 py-2 text-right text-sm font-medium text-gray-500 break-words">
                        Value
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {processMetricsData(task.metrics).map(({ key, value }) => (
                      <tr key={key} className="border-t">
                        <td className="px-2 py-2 text-sm text-gray-900 break-words overflow-wrap-anywhere">{key}</td>
                        <td className="px-2 py-2 text-sm text-gray-600 text-right break-words overflow-wrap-anywhere">
                          {value}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-gray-500">No metrics available</p>
            )}
          </div>
        );

      case "attributes":
        const attributesData = processAttributesData(task);
        return (
          <div className="mt-4 max-w-full">
            <div className="space-y-6">
              <div>
                <h3 className="text-sm font-medium text-gray-900 mb-2">
                  Input
                </h3>
                <div className="bg-gray-50 p-3 rounded text-sm max-w-full overflow-hidden">
                  <div className="max-w-full overflow-x-auto">
                    <TreeNode
                      name="Input"
                      value={attributesData.input}
                      depth={1}
                    />
                  </div>
                </div>
              </div>

              <div>
                <h3 className="text-sm font-medium text-gray-900 mb-2">
                  Output
                </h3>
                <div className="bg-gray-50 p-3 rounded text-sm max-w-full overflow-hidden">
                  <div className="max-w-full overflow-x-auto">
                    <TreeNode
                      name="Output"
                      value={attributesData.output}
                      depth={1}
                    />
                  </div>
                </div>
              </div>

              <div>
                <h3 className="text-sm font-medium text-gray-900 mb-2">
                  General
                </h3>
                <div className="bg-gray-50 p-3 rounded text-sm max-w-full overflow-hidden">
                  <div className="max-w-full overflow-x-auto">
                    <TreeNode
                      name="Attributes"
                      value={attributesData.attributes}
                    />
                  </div>
                </div>
              </div>

              <div>
                <h3 className="text-sm font-medium text-gray-900 mb-2">IDs</h3>
                <div className="bg-gray-50 p-3 rounded text-sm max-w-full overflow-hidden">
                  <div className="max-w-full overflow-x-auto">
                    <TreeNode name="IDs" value={attributesData.references} />
                  </div>
                </div>
              </div>
            </div>
          </div>
        );

      case "issues":
        return (
          <TaskIssuesPanel
            taskId={task.element_id}
            issues={task.issues}
            onIssueSelect={onIssueSelect}
          />
        );

      default:
        return null;
    }
  };

  return (
    <div className="bg-white p-6">
      <div className="border-b border-gray-200">
        <nav className="flex space-x-2" aria-label="Tabs">
          {["attributes", "metrics", "issues"].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`
                py-4 px-2 border-b-4 font-medium text-base
                ${
                  activeTab === tab
                    ? "border-blue-500 text-black-600"
                    : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                }
              `}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
          <CopyButton task_text={tabCopyContent} />
          <ExpandButton />
        </nav>
      </div>
      <div className="mt-4 relative">{renderTabContent()}</div>

      <OverlayModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}
      >
        <div className="border-b border-gray-200">
          <nav className="flex space-x-2" aria-label="Tabs">
            {["attributes", "metrics", "issues"].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`
                  py-4 px-3 border-b-4 font-medium text-base
                  ${
                    activeTab === tab
                      ? "border-blue-500 text-black-600"
                      : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                  }
                `}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
            <CopyButton task_text={tabCopyContent} />
          </nav>
        </div>
        <div className="mt-4 relative">{renderTabContent()}</div>
      </OverlayModal>
    </div>
  );
};

// Main SidePanel container component
const SidePanel = ({
  task,
  handleTaskClick,
  setData,
  serverUrl,
  serviceName,
  issues,
  selectedIssue,
  onIssueSelect,
  selectedMetric,
  onMetricSelect,
  setActiveTab,
  hideTaskPrefixes = false,
}) => {
  if (selectedMetric && selectedMetric.length > 0) {
    return <WorkflowMetricsSidePanel metrics={selectedMetric} />;
  }
  // If an issue is selected, show issue details instead of task details
  if (selectedIssue) {
    return (
      <div className="space-y-4">
        <IssuesSidePanel
          issue={selectedIssue}
          onTaskSelect={(task) => {
            // Find task by ID and select it
            onIssueSelect(null); // Clear selected issue
            setActiveTab("tasks");
            handleTaskClick(task);
          }}
          OverlayModal={OverlayModal}
        />
      </div>
    );
  }

  if (!task) {
    return (
      <div className="bg-white p-6 mb-4 border-t-4 border-solid min-h-screen">
        Select a task or issue to view details
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <TopSidePanel
        task={task}
        globalTasks={task.ancestorTasks}
        setSelectedTask={handleTaskClick}
        hideTaskPrefixes={hideTaskPrefixes}
      />
      <BottomSidePanel
        task={task}
        issues={issues}
        onIssueSelect={onIssueSelect}
      />
    </div>
  );
};

export default SidePanel;
