export const taskHeight = 40; // Changed from 70px
export const barHeight = 28; // Changed from 50px
export const highlightClass = 'bg-blue-50'; // Class for row highlighting
export const selectRowClass = 'bg-blue-100'; // Class for row highlighting

const DependencyLine = ({
  startTask,
  endTask,
  globalStart,
  globalEnd,
  groupWidth,
  startIndex,
  startTotal,
  endIndex,
  endTotal,
  isFullMode,
  nameColumnOffset = 0,
}) => {
  if (!startTask.isVisible || !endTask.isVisible) {
    return null;
  }

  // Calculate positions based on the effective width and name column offset
  // Fixed calculation to prevent drift by ensuring we're using the same scaling factor
  const totalDuration = new Date(globalEnd) - new Date(globalStart);
  const startTime = new Date(startTask.end_time) - new Date(globalStart);
  const endTime = new Date(endTask.start_time) - new Date(globalStart);

  // More precise calculation using the same scale factor throughout
  const scaleFactor = Math.floor((groupWidth / totalDuration) * 1000) / 1000;
  const startX = startTime * scaleFactor - 6;
  const endX = endTime * scaleFactor - 6;

  // Center of task rows for source and target (vertical center of their rows)
  const startY = startTask.verticalPosition * taskHeight + taskHeight / 2;
  const endY = endTask.verticalPosition * taskHeight + taskHeight / 2;

  // Determine if this is a mostly vertical line
  const isVertical = Math.abs(endX - startX) < 30; // && Math.abs(endY - startY) > taskHeight;

  let path;

  if (isVertical) {
    // Use S-curve for vertical lines with slight horizontal offset
    const offsetX = 10; // Slight horizontal offset for the S-curve
    path = `M${startX},${startY} 
                C${startX + offsetX + offsetX},${startY} 
                ${endX + offsetX},${startY + (endY - startY) * 0.3} 
                ${endX},${startY + (endY - startY) * 0.5} 
                C${endX - offsetX},${startY + (endY - startY) * 0.7} 
                ${endX - offsetX},${endY - 10} 
                ${endX},${endY}`;
  } else {
    // Use quadratic bezier for other lines
    const controlX = (startX + endX) / 2;
    path = `M${startX},${startY} 
                Q${controlX},${startY} 
                ${controlX},${(startY + endY) / 2} 
                Q${controlX},${endY} 
                ${endX},${endY}`;
  }

  return (
    <svg className="absolute top-0 left-0 w-full h-full pointer-events-none">
      <defs>
        <marker id="arrowhead" markerWidth="5" markerHeight="3.5" refX="1" refY="1.75" orient="0deg">
          <polygon points="0 0, 5 1.75, 0 3.5" fill="rgba(96, 96, 96, 1)" />
        </marker>
      </defs>
      <path
        d={path}
        fill="none"
        stroke="rgba(96, 96, 96, 1)"
        strokeWidth="2"
        strokeDasharray="4,4"
        markerEnd="url(#arrowhead)"
      />
    </svg>
  );
};

export default DependencyLine;
