import React, { useState, useMemo, useEffect } from 'react';
import TaskNode from './TaskNode';
import DependencyLine from './DependencyLine';
import { taskHeight, highlightClass, selectRowClass } from './DependencyLine.js';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { formatTaskName } from './utils/taskNameUtils';

const MIN_TASK_WIDTH = 6;
const TASK_GAP = 3;

// A simpler task group component with streamlined logic
const TaskGroup = ({
  tasks,
  onTaskClick,
  parentWidth,
  globalStart,
  globalEnd,
  baseTime,
  showDependencies,
  selectedTaskId,
  ancestorIds,
  isFullMode,
  zoomLevel,
  setZoomLevel,
  setContainerWidth,
  shortestDuration,
  baseWidth,
  expandedTasks = {}, // Map of task IDs to expanded state
  onExpandAll,
  onCollapseAll,
  onExpandOneLevel,
  onCollapseOneLevel,
  nameColumnWidth = 330, // Default value for backward compatibility
  hideTaskPrefixes = false,
}) => {
  const [prevZoom, setPrevZoom] = useState(0);
  const [hoveredTask, setHoveredTask] = useState(null);
  const [hoveredRow, setHoveredRow] = useState(null);

  // Process the task hierarchy to produce a flat list for rendering
  const processedTasks = useMemo(() => {
    // Build a lookup map of all tasks
    const taskMap = new Map();
    const traverseAndCollect = (tasksToTraverse, allTasks = []) => {
      for (const task of tasksToTraverse) {
        allTasks.push(task);
        taskMap.set(task.id, task);
        if (task.children) {
          traverseAndCollect(task.children, allTasks);
        }
      }
      return allTasks;
    };

    // Collect all tasks including nested children
    const allTasks = traverseAndCollect(tasks);

    // Build a map of parent-child relationships
    const childrenByParent = new Map();
    allTasks.forEach((task) => {
      if (task.children && task.children.length > 0) {
        childrenByParent.set(task.id, task.children);
      }
    });

    // Build the flattened visible task list
    const visibleTasks = [];
    let verticalPosition = 0;

    const addTaskWithVisibleChildren = (task, level = 0) => {
      // Add the current task with its position and level
      task.level = level;
      task.verticalPosition = verticalPosition++;
      visibleTasks.push(task);

      // If this task is expanded and has children, add them too
      if (expandedTasks[task.id] && childrenByParent.has(task.id)) {
        const children = childrenByParent.get(task.id);
        // Process children in start time order
        [...children]
          .sort((a, b) => new Date(a.start_time) - new Date(b.start_time))
          .forEach((child) => {
            addTaskWithVisibleChildren(child, level + 1);
          });
      }
    };

    // Start with root tasks
    const rootTasks = tasks
      .filter((task) => !task.parent_id)
      .sort((a, b) => new Date(a.start_time) - new Date(b.start_time));

    rootTasks.forEach((task) => {
      addTaskWithVisibleChildren(task);
    });

    return visibleTasks;
  }, [tasks, expandedTasks]);

  // Effective width calculation
  const effectiveWidth = useMemo(() => {
    const totalDuration = new Date(globalEnd) - new Date(globalStart);
    const scalingFactor = (MIN_TASK_WIDTH + TASK_GAP) / shortestDuration;
    const fullModeWidth = Math.max(baseWidth, totalDuration * scalingFactor);

    if (zoomLevel === 0) return baseWidth;

    if (zoomLevel <= 100) {
      // Linear interpolation between baseWidth and fullModeWidth
      const progress = zoomLevel / 100;
      return baseWidth + (fullModeWidth - baseWidth) * progress;
    }

    // Beyond 100, scale linearly from fullModeWidth
    const additionalZoom = (zoomLevel - 100) / 100;
    return fullModeWidth * (1 + additionalZoom);
  }, [globalEnd, globalStart, shortestDuration, baseWidth, zoomLevel]);

  // Group height based on number of visible tasks
  const groupHeight = Math.max(50, processedTasks.length * taskHeight);

  // Handle container width updates
  useEffect(() => {
    if (zoomLevel >= prevZoom) {
      if (effectiveWidth > parentWidth) {
        setContainerWidth(effectiveWidth);
      }
    } else {
      if (effectiveWidth < parentWidth) {
        setContainerWidth(effectiveWidth);
      }
    }

    if (zoomLevel !== prevZoom) {
      setPrevZoom(zoomLevel);
    }
  }, [effectiveWidth, zoomLevel, prevZoom, parentWidth, setContainerWidth]);

  // Initialize dependency tracking
  const { inboundRanks, outboundRanks, inboundCount, outboundCount, sortedDependentTasks } = useMemo(() => {
    const inboundRanks = new Map();
    const outboundRanks = new Map();
    const inboundCount = new Map();
    const outboundCount = new Map();
    const sortedDependentTasks = new Map();

    processedTasks.forEach((task) => {
      if (task.dependent_ids && task.dependent_ids.length > 0) {
        task.dependent_ids.forEach((dependentId) => {
          outboundRanks.set(dependentId, (outboundRanks.get(dependentId) || 0) + 1);
          inboundRanks.set(task.id, (inboundRanks.get(task.id) || 0) + 1);

          inboundCount.set(task.id, 0);
          outboundCount.set(dependentId, 0);

          if (!sortedDependentTasks.has(task.id)) {
            sortedDependentTasks.set(task.id, []);
          }

          const dependentTask = processedTasks.find((t) => t.id === dependentId);
          if (dependentTask) {
            sortedDependentTasks.get(task.id).push(dependentTask);
          }
        });
      }
    });

    // Sort by vertical position
    sortedDependentTasks.forEach((tasks) => {
      tasks.sort((a, b) => a.verticalPosition - b.verticalPosition);
    });

    return { inboundRanks, outboundRanks, inboundCount, outboundCount, sortedDependentTasks };
  }, [processedTasks]);

  return (
    <div
      className="relative bg-gray-50 mb-4 border border-gray-200"
      style={{
        height: `${groupHeight}px`,
        minWidth: `${effectiveWidth + nameColumnWidth}px`, // Use dynamic nameColumnWidth
      }}
    >
      <div className="flex h-full">
        {/* Names column - with sticky positioning */}
        <div
          className="flex-shrink-0 border-r border-gray-200 bg-white"
          style={{
            width: `${nameColumnWidth}px`, // Use dynamic nameColumnWidth
            position: 'sticky',
            left: 0,
            zIndex: 11, // Higher than task nodes
          }}
        >
          {/* Task names */}
          <div className="flex-grow overflow-y-visible">
            {processedTasks.map((task) => {
              const hasChildren = task.children && task.children.length > 0;
              const isExpanded = expandedTasks[task.id];
              const isRowHighlighted = hoveredRow === task.id;
              const isRowSelected = selectedTaskId === task.id;

              // Format the task name based on the hideTaskPrefixes setting
              const displayName = formatTaskName(task.name, hideTaskPrefixes);

              return (
                <div
                  key={`name-${task.id}`}
                  className={`border-b border-gray-100 px-4 flex items-center truncate text-sm ${
                    isRowSelected ? selectRowClass : isRowHighlighted ? highlightClass : ''
                  }`}
                  style={{
                    height: `${taskHeight}px`,
                    paddingLeft: `${task.level * 12 + 16}px`,
                  }}
                  onMouseEnter={() => setHoveredRow(task.id)}
                  onMouseLeave={() => setHoveredRow(null)}
                >
                  {hasChildren ? (
                    <div
                      className="mr-2 flex-shrink-0 cursor-pointer hover:bg-gray-100 rounded p-1"
                      onClick={(e) => {
                        e.stopPropagation();
                        onTaskClick({ ...task, toggleExpand: true });
                      }}
                      data-testid={`expand-${task.id}`}
                    >
                      {isExpanded ? (
                        <ChevronDown className="w-4 h-4 text-gray-600" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-gray-600" />
                      )}
                    </div>
                  ) : (
                    <div className="w-6 mr-2 flex-shrink-0"></div> // Placeholder for alignment
                  )}

                  <div
                    className="truncate flex-grow cursor-pointer hover:text-blue-600"
                    onClick={() => onTaskClick(task)}
                    title={displayName}
                  >
                    {displayName}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Task timeline area with row highlights */}
        <div className="relative flex-grow h-full">
          {/* Row highlight backgrounds */}
          {processedTasks.map((task) => {
            const isRowHighlighted = hoveredRow === task.id;
            const isRowSelected = selectedTaskId === task.id;
            return isRowSelected ? (
              <div
                key={`selected-${task.id}`}
                className={`absolute ${selectRowClass}`}
                style={{
                  top: `${task.verticalPosition * taskHeight}px`,
                  height: `${taskHeight}px`,
                  width: '100%',
                  zIndex: 0,
                }}
              />
            ) : isRowHighlighted ? (
              <div
                key={`highlight-${task.id}`}
                className={`absolute ${highlightClass}`}
                style={{
                  top: `${task.verticalPosition * taskHeight}px`,
                  height: `${taskHeight}px`,
                  width: '100%',
                  zIndex: 0,
                }}
              />
            ) : null;
          })}

          {/* Task nodes */}
          {processedTasks.map((task) => {
            const minVisibleWidth = MIN_TASK_WIDTH;
            return (
              <div
                key={task.id}
                style={{
                  position: 'absolute',
                  zIndex: task.id === hoveredTask ? '10' : '5',
                }}
              >
                <TaskNode
                  task={task}
                  onClick={onTaskClick}
                  globalStart={globalStart}
                  globalEnd={globalEnd}
                  groupWidth={effectiveWidth - 12}
                  relativeStart={new Date(task.start_time) - baseTime}
                  relativeEnd={new Date(task.end_time) - baseTime}
                  isSelected={task.id === selectedTaskId}
                  isAncestor={ancestorIds.includes(task.id)}
                  isFullMode={isFullMode}
                  minWidth={minVisibleWidth}
                  taskGap={TASK_GAP}
                  zoomLevel={zoomLevel}
                  setZoomLevel={setZoomLevel}
                  setHoveredTask={setHoveredTask}
                  showTaskName={false}
                  onMouseEnter={() => setHoveredRow(task.id)}
                  onMouseLeave={() => setHoveredRow(null)}
                />
              </div>
            );
          })}

          {/* Dependency lines */}
          {showDependencies &&
            processedTasks.map((task) => {
              return (
                task.dependent_ids &&
                task.dependent_ids.length > 0 &&
                sortedDependentTasks.get(task.id)?.map((dependentTask) => {
                  if (!dependentTask) return null;

                  const dependentId = dependentTask.id;
                  const inboundIndex = inboundCount.get(task.id) || 0;
                  inboundCount.set(task.id, inboundIndex + 1);
                  const outboundIndex = outboundCount.get(dependentId) || 0;
                  outboundCount.set(dependentId, outboundIndex + 1);

                  return (
                    <div key={`${task.id}-${dependentId}`}>
                      <DependencyLine
                        startTask={dependentTask}
                        endTask={task}
                        globalStart={globalStart}
                        globalEnd={globalEnd}
                        groupWidth={effectiveWidth}
                        startIndex={outboundIndex}
                        startTotal={outboundRanks.get(dependentId) || 1}
                        endIndex={inboundIndex}
                        endTotal={inboundRanks.get(task.id) || 1}
                        isFullMode={isFullMode}
                        nameColumnOffset={nameColumnWidth} // Use dynamic nameColumnWidth
                      />
                    </div>
                  );
                })
              );
            })}
        </div>
      </div>
    </div>
  );
};

export default TaskGroup;
