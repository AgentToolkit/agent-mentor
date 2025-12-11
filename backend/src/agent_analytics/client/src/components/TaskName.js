import React from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { formatTaskName } from './utils/taskNameUtils';

const TaskName = ({ task, onClick, expandedTasks, indentLevel = 0, hideTaskPrefixes = false }) => {
  const hasChildren = task.children && task.children.length > 0;
  const isExpanded = expandedTasks[task.id];

  // Calculate indentation based on level
  const indentPx = indentLevel * 12 + 16;

  const handleExpandClick = (e) => {
    e.stopPropagation();
    onClick({ ...task, toggleExpand: true });
  };

  const handleTaskClick = () => {
    onClick(task);
  };

  // Format the task name based on the hideTaskPrefixes setting
  const displayName = formatTaskName(task.name, hideTaskPrefixes);

  return (
    <div
      className="border-b border-gray-100 px-4 flex items-center truncate text-sm"
      style={{
        height: '70px', // Using taskHeight constant
        paddingLeft: `${indentPx}px`,
      }}
    >
      {hasChildren ? (
        <div
          className="mr-2 flex-shrink-0 cursor-pointer hover:bg-gray-100 rounded p-1"
          onClick={handleExpandClick}
          data-testid={`expand-${task.id}`}
        >
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-gray-600" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-600" />
          )}
        </div>
      ) : (
        <div className="w-6 mr-2"></div> // Placeholder for alignment
      )}

      <div
        className="truncate flex-grow cursor-pointer hover:text-blue-600"
        onClick={handleTaskClick}
        title={displayName}
      >
        {displayName}
      </div>
    </div>
  );
};

export default TaskName;
