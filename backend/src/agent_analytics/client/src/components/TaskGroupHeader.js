import React from 'react';
import { ChevronsDown, ChevronRight, ChevronsRight, ChevronDown } from 'lucide-react';

/**
 * Header component for the names column in TaskGroup
 * Contains expansion/collapse control buttons
 */
const TaskGroupHeader = ({ onExpandAll, onCollapseAll, onExpandOneLevel, onCollapseOneLevel }) => {
  return (
    <div
      className="flex items-center justify-between px-4 py-2 bg-white border-b border-gray-200 sticky top-0 z-20"
      style={{
        width: '100%',
        height: '30px',
      }}
    >
      <div className="font-medium text-gray-700">Tasks</div>
      <div className="flex space-x-2">
        <button
          onClick={onExpandAll}
          className="p-1 rounded hover:bg-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
          title="Expand All"
        >
          <ChevronsDown className="w-4 h-4 text-gray-600" />
        </button>
        <button
          onClick={onCollapseAll}
          className="p-1 rounded hover:bg-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
          title="Collapse All"
        >
          <ChevronsRight className="w-4 h-4 text-gray-600" />
        </button>
        <button
          onClick={onExpandOneLevel}
          className="p-1 rounded hover:bg-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
          title="Expand One Level"
        >
          <ChevronDown className="w-4 h-4 text-gray-600" />
        </button>
        <button
          onClick={onCollapseOneLevel}
          className="p-1 rounded hover:bg-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
          title="Collapse One Level"
        >
          <ChevronRight className="w-4 h-4 text-gray-600" />
        </button>
      </div>
    </div>
  );
};

export default TaskGroupHeader;
