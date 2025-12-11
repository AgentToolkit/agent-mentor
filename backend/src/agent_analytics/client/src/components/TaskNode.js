import complexIcon from '../icons/complex.svg';
import llmCallIcon from '../icons/llm_call.svg';
import toolCallIcon from '../icons/tool_call.svg';
import { taskHeight } from './DependencyLine.js';
import { AlertTriangle } from 'lucide-react';
import { useEffect, useRef } from 'react';

const TaskNode = ({
  task,
  onClick,
  globalStart,
  globalEnd,
  groupWidth,
  relativeStart,
  relativeEnd,
  isSelected,
  isAncestor,
  minWidth = 4, // Minimum width of 4px for all tasks
  isFullMode,
  zoomLevel,
  setZoomLevel,
  setHoveredTask,
  showTaskName = true,
  onMouseEnter,
  onMouseLeave,
}) => {
  const nodeRef = useRef(null);

  // Use useEffect to scroll into view when a task becomes selected
  useEffect(() => {
    if (isSelected && nodeRef.current) {
      // Add a small delay to ensure DOM is ready and tab switching is complete
      setTimeout(() => {
        // Scroll the task into view with a smooth behavior and some vertical alignment
        nodeRef.current.scrollIntoView({
          behavior: 'smooth',
          block: 'nearest', // Center the element vertically in the visible area
        });
      }, 150); // Small delay to ensure tab switch is complete
    }
  }, [isSelected]);

  const duration = new Date(task.end_time) - new Date(task.start_time);
  const start = new Date(task.start_time) - new Date(globalStart);
  const totalDuration = new Date(globalEnd) - new Date(globalStart);

  // Calculate width based on zoom level and duration
  const rawWidth = (duration / totalDuration) * groupWidth;
  // Always ensure a minimum width
  const width = Math.max(rawWidth - 8, minWidth);

  const left = (start / totalDuration) * groupWidth + 4;

  // Only show start time if there's enough space
  const durationStr = (duration / 1000).toFixed(2) + 's';

  // Determine color and icon based on tags
  const getTaskStyle = () => {
    if (!task.tags || task.tags.length === 0)
      return {
        colorClass: 'gray-300',
        icon: null,
      };

    if (task.tags.includes('tool_call'))
      return {
        colorClass: 'lime-500',
        icon: <img src={toolCallIcon} alt="" className="w-4 h-4 mr-1 shrink-0" />,
      };

    if (task.tags.includes('llm_call'))
      return {
        colorClass: 'violet-400',
        icon: <img src={llmCallIcon} alt="" className="w-4 h-4 mr-1 shrink-0" />,
      };

    if (task.tags.includes('complex'))
      return {
        colorClass: 'sky-300',
        icon: <img src={complexIcon} alt="" className="w-4 h-4 mr-1 shrink-0" />,
      };

    if (task.tags.includes('manual'))
      return {
        colorClass: 'amber-500',
        icon: null,
      };

    return {
      colorClass: 'gray-300',
      icon: null,
    };
  };

  const { colorClass, icon } = getTaskStyle();

  // Check if task has issues
  const hasIssues = task.issues && task.issues.length > 0;

  // Base styles for the task node with reduced height (h-6 = 24px)
  const baseStyles = 'absolute h-6 rounded cursor-pointer flex items-center px-1 text-black text-xs overflow-hidden';

  // Different style variations based on state
  const nodeStyles = isSelected
    ? `${baseStyles} bg-${colorClass}`
    : isAncestor
    ? `${baseStyles} bg-${colorClass} bg-stripes`
    : `${baseStyles} bg-white border-b-4 border-solid border-${colorClass}`;

  // Always mark task as visible - we're showing all tasks now
  task.isVisible = true;

  // Handle mouse events for row highlighting
  const handleMouseEnter = () => {
    setHoveredTask(task.id);
    if (onMouseEnter) onMouseEnter();
  };

  const handleMouseLeave = () => {
    setHoveredTask(null);
    if (onMouseLeave) onMouseLeave();
  };

  // Handle issue icon click
  const handleIssueIconClick = (e) => {
    e.stopPropagation(); // Prevent triggering the task click
    // Call onClick with task and special flag to indicate issues tab should be shown
    onClick({ ...task, showIssuesTab: task.issues[0] });
  };

  return (
    <div className="relative">
      {/* Issue alert icon above the task */}
      {hasIssues && (
        <div
          className="absolute bg-red-500 rounded-full p-px cursor-pointer"
          style={{
            left: `${left + width - 16}px`,
            top: `${task.verticalPosition * taskHeight + 12}px`,
            zIndex: 10, // Higher z-index to make sure it's clickable
          }}
          onClick={handleIssueIconClick}
          title={`${task.issues.length} issue${task.issues.length > 1 ? 's' : ''} - Click to view`}
        >
          <AlertTriangle strokeWidth={3} className="w-4 h-4 text-white p-[2px]" />
        </div>
      )}

      <div
        ref={nodeRef} // Add ref to the node for scrollIntoView
        className={nodeStyles}
        style={{
          left: `${left}px`,
          width: `${width}px`,
          top: `${10 + task.verticalPosition * taskHeight}px`, // Adjusted position for shorter rows
          zIndex: 5,
        }}
        onClick={() => onClick(task)}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        title={`${task.name} (${(duration / 1000).toFixed(3)}s)${hasIssues ? ` - ${task.issues.length} issue(s)` : ''}`}
        data-task-id={task.id} // Add data attribute for easier selection in testing
      >
        <div className="flex items-center w-full">
          {icon}
          {showTaskName && <span className="truncate ml-2 text-base">{task.name}</span>}
          {!showTaskName && <span className="text-xs">{durationStr}</span>}
        </div>
      </div>
    </div>
  );
};

export default TaskNode;
