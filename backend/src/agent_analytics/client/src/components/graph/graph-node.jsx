// graph-node.jsx (Add isSelected prop)
import React from 'react';
import { truncateText, getNodeColorByHits } from './graph-constants';

const GraphNode = ({
  node,
  position,
  isSelected, // <-- Added prop
  isHovered,
  nodeWidth,
  nodeHeight,
  handleNodeClick, // Change this to use the App's handler
  onMouseEnter,
  onMouseLeave,
  colors,
  graphData
}) => {
  // ... (keep existing logic like hasNestedGraph, isReference, etc.)
   const hasNestedGraph = node.nestedGraph !== null && node.nestedGraph !== undefined;
   const isReference = node.isReference === true;
   const hasReferenceTarget = isReference && node.referenceTo;
   const isClickableReference = hasReferenceTarget && findNodeWithNestedGraph(graphData, node.referenceTo);
   const isClickable = hasNestedGraph || isClickableReference;
   const nodeColor = getNodeColorByHits(node.hits);
   const hitsPanelWidth = 40;
   const getTextColor = (hits) => (hits < 20 ? '#000000' : '#ffffff');
   const textColor = getTextColor(node.hits);

  return (
    <g
      transform={`translate(${position.x - nodeWidth/2}, ${position.y - nodeHeight/2})`}
       // Use the passed handleNodeClick directly - it's now the App's handler
       onClick={() => isClickable && handleNodeClick(node.id, node.nestedGraph, null)}
      onMouseEnter={() => onMouseEnter(node.id)}
      onMouseLeave={onMouseLeave}
      style={{
        cursor: isClickable ? 'pointer' : 'default',
        transition: 'all 0.3s ease-in-out'
      }}
    >
      {/* Main node rectangle with added selection highlight */}
      <rect
        width={nodeWidth}
        height={nodeHeight}
        rx={4}
        ry={4}
        fill={nodeColor}
        // Modify stroke for selection and hover
        stroke={isSelected ? colors.link || '#0f62fe' : (isHovered ? '#ffffff' : (isReference ? '#ff6b00' : 'transparent'))}
        strokeWidth={isSelected ? 4 : (isReference ? 3 : 2)} // Thicker stroke for selected
        strokeDasharray={isReference ? '5,3' : '0'}
        filter="drop-shadow(0px 2px 3px rgba(0, 0, 0, 0.2))"
        style={{ transition: 'all 0.2s ease-in-out' }}
      />

       {/* Rest of the node content (hits panel, text, icons) */}
       {/* Left panel for hit count */}
       <rect
          width={hitsPanelWidth}
          height={nodeHeight}
          rx={4}
          ry={4}
          fill={colors.hitsBg}
          style={{ transition: 'all 0.2s ease-in-out' }}
       />
       {/* Fix for left panel corners */}
       <rect x={hitsPanelWidth - 4} width={4} height={nodeHeight} fill={colors.hitsBg} />
       {/* Hit count */}
       <text x={hitsPanelWidth / 2} y={nodeHeight / 4} textAnchor="middle" dominantBaseline="middle" fontSize={17} fontWeight="500" fill="#ffffff" style={{ transition: 'all 0.2s ease-in-out' }}>{node.hits}</text>
       {/* Node name */}
       <text x={hitsPanelWidth + 15} y={30} textAnchor="start" dominantBaseline="middle" fontSize={20} fontWeight="400" fill={textColor} style={{ transition: 'all 0.2s ease-in-out' }}>{truncateText(node.name, 20)}</text>
       {/* Reference icon */}
        {isReference && (
            <g transform={`translate(${nodeWidth - 25}, 20)`}>
                <path d="M0,0 L10,10 L0,20 Z" fill="#ff6b00" transform="rotate(270)" />
                <circle cx={0} cy={0} r={12} fill="none" stroke="#ff6b00" strokeWidth={2} strokeDasharray="5,3" />
                <text x={0} y={4} textAnchor="middle" dominantBaseline="middle" fontSize={10} fontWeight="bold" fill="#ff6b00">REF</text>
            </g>
        )}
        {/* Description */}
        {node.description && ( <text x={hitsPanelWidth + 15} y={60} textAnchor="start" dominantBaseline="middle" fontSize={15} fill={colors.textSecondary} style={{ transition: 'all 0.2s ease-in-out' }}>{truncateText(node.description, 25)}</text> )}
        {/* Nested graph icon */}
        {(hasNestedGraph || isClickableReference) && (
            <g transform={`translate(${hitsPanelWidth / 2}, ${nodeHeight - 20})`}>
                <circle r={8} stroke="#ffffff" strokeWidth="2" opacity={0.7} style={{ transition: 'all 0.2s ease-in-out' }} />
                <line x1={7} y1={7} x2={12} y2={12} stroke="#ffffff" strokeWidth={2.5} style={{ transition: 'all 0.2s ease-in-out' }} />
                <line x1={-4} y1={0} x2={4} y2={0} stroke="#ffffff" strokeWidth={2} /> <line x1={0} y1={-4} x2={0} y2={4} stroke="#ffffff" strokeWidth={2} />
            </g>
        )}

      {/* Tooltip */}
    </g>
  );
};
// Keep the helper function and Tooltip component as they were
// Helper function to find if a referenced node has a nested graph
const findNodeWithNestedGraph = (graph, nodeId) => {
  if (!graph || !graph.nodes) return false;
  const node = graph.nodes.find(n => n.id.toLowerCase() === nodeId.toLowerCase());
  if (node && node.nestedGraph) return true;
  for (const currentNode of graph.nodes) {
    if (currentNode.nestedGraph) {
      const foundInNested = findNodeWithNestedGraph(currentNode.nestedGraph, nodeId);
      if (foundInNested) return true;
    }
  }
  return false;
};

const NodeTooltip = ({ node, nodeWidth, colors, isClickableReference }) => {
    const isReference = node.isReference === true;
    return ( <g transform="translate(0, -70)" style={{ transition: 'all 0.2s ease-in-out' }}> <rect width={nodeWidth} height={isReference ? 70 : 50} rx={4} ry={4} fill="#393939" style={{ transition: 'all 0.2s ease-in-out' }} /> <text x={12} y={20} textAnchor="start" dominantBaseline="middle" fontSize={12} fill="white" style={{ transition: 'all 0.2s ease-in-out' }}>{`Name: ${node.name}`}</text> <text x={12} y={40} textAnchor="start" dominantBaseline="middle" fontSize={12} fill="white" style={{ transition: 'all 0.2s ease-in-out' }}>{`ID: ${node.id} | Hits: ${node.hits}`}</text> {isReference && ( <text x={12} y={60} textAnchor="start" dominantBaseline="middle" fontSize={12} fill="#ff6b00" fontWeight="bold" style={{ transition: 'all 0.2s ease-in-out' }}>{`References: ${node.referenceTo}${isClickableReference ? " (clickable)" : " (not clickable)"}`}</text> )} <path d="M75,0 L85,10 L65,10 Z" transform={`translate(${nodeWidth/2 - 75}, ${isReference ? 70 : 50})`} fill="#393939" style={{ transition: 'all 0.2s ease-in-out' }} /> </g> );
};


export { GraphNode, NodeTooltip };
export default GraphNode;