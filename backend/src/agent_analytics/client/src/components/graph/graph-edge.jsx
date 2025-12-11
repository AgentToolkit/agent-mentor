import React, { useState } from 'react';
import { getEdgeColorByHits } from './graph-constants';

// Helper function to expand the edge into individual source-target connections
const expandEdgeToConnections = (edge) => {
  const connections = [];
  
  // For each source node, connect to each target node
  connections.push({
    sourceId: edge.source,
    targetId: edge.target,
    parentEdge: edge
  });
  
  return connections;
};

// GraphEdge component for rendering edges between nodes
const GraphEdge = ({ 
  edge, 
  index, 
  nodePositions, 
  calculateEdgePath, 
  colors 
}) => {
  // Add hover state
  const [isHovered, setIsHovered] = useState(false);
  
  // Expand the edge into individual connections
  const connections = expandEdgeToConnections(edge);
  
  // If there are no valid connections, return null
  if (connections.length === 0) return null;
  
  // Find a valid midpoint for the edge label from any valid connection
  let labelMidX = 0;
  let labelMidY = 0;
  let validPath = null;
  
  for (const conn of connections) {
    const path = calculateEdgePath(conn.sourceId, conn.targetId);
    if (path) {
      labelMidX = path.midX;
      labelMidY = path.midY;
      validPath = path;
      break;
    }
  }
  
  // If no valid path was found, don't render anything
  if (!validPath) return null;

  // Calculate hover styles  
  const edgeColor = isHovered ? colors.link : colors.edgeMediumHits;
  const edgeWidth = isHovered ? 3 : 2;
  
  return (
    <g 
      style={{ 
        transition: 'all 0.3s ease-in-out',
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Arrow definitions */}
      <defs>
        {/* Standard arrow (pointing down/right) */}
        <marker
          id={`arrow-standard-${index}${isHovered ? '-hover' : ''}`}
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="6"
          markerHeight="6"
          orient="auto"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" 
            fill={edgeColor} 
            stroke="none" 
          />
        </marker>
        
        {/* Upward arrow definition (pointing up) */}
        <marker
          id={`arrow-upward-${index}${isHovered ? '-hover' : ''}`}
          viewBox="0 0 10 10"
          refX="1"
          refY="5"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" 
            fill={edgeColor} 
            stroke="none" 
          />
        </marker>
      </defs>
      
      {/* Render each connection as a separate curved path */}
      {connections.map((conn, connIndex) => {
        const path = calculateEdgePath(conn.sourceId, conn.targetId);
        if (!path) return null;
        
        // Choose the appropriate arrow marker based on direction
        const arrowMarkerId = path.isUpwardEdge ? 
          `arrow-upward-${index}${isHovered ? '-hover' : ''}` : 
          `arrow-standard-${index}${isHovered ? '-hover' : ''}`;
        
        return (
          // Use a hover state to manage stacking order
          <path
            key={`edge-${index}-conn-${connIndex}`}
            d={path.path}
            fill="none"
            stroke={edgeColor}
            strokeWidth={edgeWidth}
            strokeDasharray={edge.type === 'join' ? '5,5' : '0'}
            markerEnd={`url(#${arrowMarkerId})`}
            style={{ 
              transition: 'all 0.3s ease-in-out',
              cursor: 'pointer',
              // Use inline style to set z-index dynamically for SVG elements
              zIndex: isHovered ? 50 : 10
            }}
          />
        );
      })}
      
      {/* Hit count label - in a separate group for better z-index control */}
      <g style={{ zIndex: isHovered ? 100 : 20 }}>
        <EdgeLabel 
          midX={labelMidX} 
          midY={labelMidY} 
          hits={edge.hits} 
          colors={colors} 
          isHovered={isHovered}
        />
      </g>
    </g>
  );
};

// EdgeLabel component for displaying hit counts on edges
const EdgeLabel = ({ midX, midY, hits, colors, isHovered }) => {
  // Get color based on hit count and hover state
  const baseColor = getEdgeColorByHits(hits);
  const labelBgColor = isHovered ? colors.link : baseColor;
  
  // No scaling, just change colors and stroke width
  return (
    <g transform={`translate(${midX}, ${midY})`}>
      {/* Shadow/glow effect when hovered (optional) */}
      {isHovered && (
        <circle
          r={18}
          fill="none"
          stroke={colors.link}
          strokeWidth={2}
          strokeOpacity={0.3}
          style={{ transition: 'all 0.2s ease-in-out' }}
        />
      )}
      
      {/* Main circle */}
      <circle
        r={15}
        fill={labelBgColor}
        stroke="#ffffff"
        strokeWidth={isHovered ? 3 : 2}
        style={{ transition: 'all 0.2s ease-in-out' }}
      />
      
      {/* Text */}
      <text
        x={0}
        y={0}
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize={12}
        fontWeight={isHovered ? '700' : '600'}
        fill="#ffffff"
        style={{ transition: 'all 0.2s ease-in-out' }}
      >
        {hits}
      </text>
    </g>
  );
};

export { GraphEdge, EdgeLabel, expandEdgeToConnections };
export default GraphEdge;