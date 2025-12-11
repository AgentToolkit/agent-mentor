// LevelConnectorArrows component to add incoming and outgoing arrows

// This component will be rendered inside the GraphVisualizer
import React from 'react';

const LevelConnectorArrows = ({ 
  graph,
  nodePositions, 
  nodeWidth, 
  nodeHeight,
  colors 
}) => {
  if (!graph || !graph.nodes || graph.nodes.length === 0) {
    return null;
  }

  // Identify top and bottom nodes based on their y-position
  const allNodes = Object.entries(nodePositions);
  if (allNodes.length === 0) return null;

  // Sort nodes by y position
  const sortedByY = [...allNodes].sort((a, b) => a[1].y - b[1].y);
  
  // Find minimum and maximum y values
  const minY = sortedByY[0][1].y;
  const maxY = sortedByY[sortedByY.length - 1][1].y;
  
  // Find nodes at the top level (smallest y)
  const topNodes = allNodes.filter(([_, pos]) => Math.abs(pos.y - minY) < 10);
  
  // Find nodes at the bottom level (largest y)
  const bottomNodes = allNodes.filter(([_, pos]) => Math.abs(pos.y - maxY) < 10);

  // Arrow marker definition
  const arrowMarkerId = "connector-arrow";
  
  return (
    <g className="level-connector-arrows">
      {/* Arrow marker definition */}
      <defs>
        <marker
          id={arrowMarkerId}
          viewBox="0 0 10 10"
          refX="10"
          refY="5"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <path 
            d="M 0 0 L 10 5 L 0 10 z" 
            fill={colors.edgeMediumHits} 
            stroke="none" 
          />
        </marker>
      </defs>
      
      {/* Top incoming arrows */}
      {topNodes.map(([nodeId, position]) => {
        const startX = position.x;
        const startY = 0; // Start from the top of the SVG or breadcrumb bottom
        const endX = position.x;
        const endY = position.y - nodeHeight/2; // Top of the node
        
        return (
          <path
            key={`top-arrow-${nodeId}`}
            d={`M ${startX} ${startY} L ${endX} ${endY}`}
            stroke={colors.edgeMediumHits}
            strokeWidth={2}
            markerEnd={`url(#${arrowMarkerId})`}
            strokeDasharray="5,5" // Optional: make it dashed for visual distinction
            fill="none"
          />
        );
      })}
      
      {/* Bottom outgoing arrows */}
      {bottomNodes.map(([nodeId, position]) => {
        const startX = position.x;
        const startY = position.y + nodeHeight/2; // Bottom of the node
        const endX = position.x;
        const endY = position.y + nodeHeight/2 + 50; // Extend 50px below
        
        return (
          <path
            key={`bottom-arrow-${nodeId}`}
            d={`M ${startX} ${startY} L ${endX} ${endY}`}
            stroke={colors.edgeMediumHits}
            strokeWidth={2}
            markerEnd={`url(#${arrowMarkerId})`}
            strokeDasharray="5,5" // Optional: make it dashed for visual distinction
            fill="none"
          />
        );
      })}
    </g>
  );
};

export default LevelConnectorArrows;