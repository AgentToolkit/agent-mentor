// Modified function to calculate node levels with cycle detection
const calculateNodeLevels = (graph) => {
  const levels = {};
  const nodeDependencies = {};
  const nodeMap = {};

  // Initialize
  graph.nodes.forEach((node) => {
    levels[node.id] = 0; // Default level
    nodeDependencies[node.id] = [];
    nodeMap[node.id] = node;
  });

  // Build the dependency graph (edges)
  graph.edges.forEach((edge) => {
    const sourceId = edge.source;
    const targetId = edge.target;

    // Check for self-dependency and if the dependency already exists
    if (sourceId !== targetId && !nodeDependencies[sourceId].includes(targetId)) {
      // Add the target as a dependency of the source
      nodeDependencies[sourceId].push(targetId);
    }
  });

  // Detect cycles in the graph using DFS
  const detectCycles = () => {
    const visited = {};
    const recursionStack = {};
    const cycleNodes = new Set();

    // Initialize visited and recursion stack
    Object.keys(nodeDependencies).forEach((nodeId) => {
      visited[nodeId] = false;
      recursionStack[nodeId] = false;
    });

    // DFS function to check for cycles
    const dfs = (nodeId) => {
      visited[nodeId] = true;
      recursionStack[nodeId] = true;

      // Check all dependencies of the current node
      for (const depId of nodeDependencies[nodeId]) {
        // If not visited, go deeper
        if (!visited[depId]) {
          if (dfs(depId)) {
            cycleNodes.add(nodeId);
            cycleNodes.add(depId);
            return true;
          }
        }
        // If already in recursion stack, there's a cycle
        else if (recursionStack[depId]) {
          cycleNodes.add(nodeId);
          cycleNodes.add(depId);
          return true;
        }
      }

      recursionStack[nodeId] = false;
      return false;
    };

    // Run DFS for each node
    Object.keys(nodeDependencies).forEach((nodeId) => {
      if (!visited[nodeId]) {
        dfs(nodeId);
      }
    });

    return cycleNodes;
  };

  // Get nodes involved in cycles
  const cycleNodes = detectCycles();

  // Topological sort to assign initial levels (for non-cycle nodes)
  const assignInitialLevels = () => {
    // Create a copy of dependencies to work with
    const remainingDeps = {};
    Object.keys(nodeDependencies).forEach((nodeId) => {
      remainingDeps[nodeId] = [...nodeDependencies[nodeId]];
    });

    // Find nodes with no dependencies
    const nodesWithNoDeps = Object.keys(remainingDeps).filter((nodeId) => remainingDeps[nodeId].length === 0);

    // Start with level 0
    let currentLevel = 0;
    let currentNodes = nodesWithNoDeps;

    // Process nodes level by level
    while (currentNodes.length > 0) {
      const nextNodes = [];

      // Process all nodes at the current level
      currentNodes.forEach((nodeId) => {
        levels[nodeId] = currentLevel;

        // Remove this node from the dependencies of other nodes
        Object.keys(remainingDeps).forEach((otherNodeId) => {
          const index = remainingDeps[otherNodeId].indexOf(nodeId);
          if (index !== -1) {
            remainingDeps[otherNodeId].splice(index, 1);
            if (remainingDeps[otherNodeId].length === 0) {
              nextNodes.push(otherNodeId);
            }
          }
        });
      });

      // Move to the next level
      currentLevel++;
      currentNodes = nextNodes;
    }

    // Handle remaining nodes (those in cycles)
    const remainingNodes = Object.keys(remainingDeps).filter((nodeId) => !levels[nodeId] && levels[nodeId] !== 0);

    if (remainingNodes.length > 0) {
      // Find minimum level for remaining nodes
      let minLevel = Infinity;
      remainingNodes.forEach((nodeId) => {
        nodeDependencies[nodeId].forEach((depId) => {
          if (levels[depId] !== undefined && levels[depId] < minLevel) {
            minLevel = levels[depId];
          }
        });
      });

      // If no minimum found, set to current level
      if (minLevel === Infinity) {
        minLevel = currentLevel;
      }

      // Assign levels to remaining nodes
      remainingNodes.forEach((nodeId) => {
        levels[nodeId] = minLevel + 1;
      });
    }
  };

  // Call initial level assignment
  assignInitialLevels();

  // Fine-tune levels for nodes in cycles
  let changed = true;
  let iterations = 0;
  const maxIterations = 5; // Limit iterations to prevent unbounded growth
  const maxLevelGap = 2; // Maximum allowed level difference

  while (changed && iterations < maxIterations) {
    changed = false;
    iterations++;

    // Process each node
    Object.keys(nodeDependencies).forEach((nodeId) => {
      nodeDependencies[nodeId].forEach((depId) => {
        // Only adjust if depId's level is too close to nodeId's level
        if (levels[depId] <= levels[nodeId]) {
          // Calculate new level, but limit the gap
          const newLevel = levels[nodeId] + 1;

          // Check if this is a cyclic dependency
          const isCyclicDep = cycleNodes.has(nodeId) && cycleNodes.has(depId);

          // If part of a cycle, limit the level increase to prevent large gaps
          if (isCyclicDep) {
            // If both are in a cycle, don't allow a gap of more than maxLevelGap
            levels[depId] = Math.min(newLevel, levels[nodeId] + maxLevelGap);
          } else {
            // For non-cyclic dependencies, use normal leveling
            levels[depId] = newLevel;
          }

          changed = true;
        }
      });
    });
  }

  // Post-processing to smooth out levels for better layout
  const smoothLevels = () => {
    // Get all unique levels
    const uniqueLevels = [...new Set(Object.values(levels))].sort((a, b) => a - b);

    // If there are gaps in the levels, compress them
    if (uniqueLevels.length > 1) {
      const compressedLevels = {};

      // Create a mapping from original levels to compressed levels
      uniqueLevels.forEach((level, index) => {
        compressedLevels[level] = index;
      });

      // Update the levels using the compressed mapping
      Object.keys(levels).forEach((nodeId) => {
        levels[nodeId] = compressedLevels[levels[nodeId]];
      });
    }
  };

  // Apply level smoothing
  smoothLevels();

  return levels;
};

// Normalize levels (ensure they start from 0)
const normalizeLevels = (levels) => {
  const normalizedLevels = { ...levels };
  const minLevel = Math.min(...Object.values(levels));

  if (minLevel > 0) {
    Object.keys(normalizedLevels).forEach((nodeId) => {
      normalizedLevels[nodeId] = normalizedLevels[nodeId] - minLevel;
    });
  }

  return normalizedLevels;
};

// Calculate nodes at each level
const getNodesAtLevel = (graph, levels) => {
  const nodesAtLevel = {};

  // Group nodes by level
  Object.keys(levels).forEach((nodeId) => {
    const level = levels[nodeId];
    if (!nodesAtLevel[level]) {
      nodesAtLevel[level] = [];
    }
    nodesAtLevel[level].push(nodeId);
  });

  return nodesAtLevel;
};

// Calculate optimal positioning of nodes within each level to minimize edge crossings
const optimizeNodePositionsInLevel = (level, nodesAtLevel, edges, levels) => {
  // Simple implementation: sort nodes based on their dependencies
  // A more sophisticated approach would use the barycenter method

  const nodeIds = nodesAtLevel[level] || [];
  if (nodeIds.length <= 1) return nodeIds;

  // For each node at this level, calculate its "ideal" x-position based on connected nodes
  const nodePositionHints = {};

  nodeIds.forEach((nodeId) => {
    let connectedNodeCount = 0;
    let positionSum = 0;

    // Look at nodes connected from previous level
    if (level > 0 && nodesAtLevel[level - 1]) {
      const prevLevelNodeIds = nodesAtLevel[level - 1];

      edges.forEach((edge) => {
        if (edge.target.includes(nodeId)) {
          if (prevLevelNodeIds.includes(edge.source)) {
            // Find the index of the source in the previous level's nodes
            const sourceIndex = prevLevelNodeIds.indexOf(edge.source);

            // Update the sum and count
            positionSum += sourceIndex;
            connectedNodeCount++;
          }
        }
      });
    }

    // Look at nodes connected to next level
    if (nodesAtLevel[level + 1]) {
      const nextLevelNodeIds = nodesAtLevel[level + 1];

      edges.forEach((edge) => {
        if (edge.source.includes(nodeId)) {
          if (nextLevelNodeIds.includes(edge.target)) {
            // Find the index of the target in the next level's nodes
            const targetIndex = nextLevelNodeIds.indexOf(edge.target);

            // Update the sum and count
            positionSum += targetIndex;
            connectedNodeCount++;
          }
        }
      });
    }

    // Calculate average position
    nodePositionHints[nodeId] = connectedNodeCount > 0 ? positionSum / connectedNodeCount : nodeIds.indexOf(nodeId);
  });

  // Sort nodes based on position hints
  return [...nodeIds].sort((a, b) => nodePositionHints[a] - nodePositionHints[b]);
};

// Calculate hierarchical layout for nodes
export const calculateNodePositions = (
  currentGraph,
  dimensions,
  svgSize,
  nodeWidth,
  nodeHeight,
  nodeSpacingX,
  nodeSpacingY,
  leftPadding = 0
) => {
  if (!currentGraph || !currentGraph.nodes || currentGraph.nodes.length === 0) {
    return {};
  }

  const positions = {};

  // Calculate node levels
  const levels = calculateNodeLevels(currentGraph);
  const normalizedLevels = normalizeLevels(levels);

  // Group nodes by level
  const nodesAtLevel = getNodesAtLevel(currentGraph, normalizedLevels);

  // Calculate the maximum level
  const maxLevel = Math.max(...Object.keys(nodesAtLevel).map(Number));

  // Calculate positions for each level
  for (let level = 0; level <= maxLevel; level++) {
    // Optimize the order of nodes at this level
    const nodeIdsAtLevel = optimizeNodePositionsInLevel(level, nodesAtLevel, currentGraph.edges, normalizedLevels);
    const nodeCount = nodeIdsAtLevel.length;

    if (nodeCount > 0) {
      // Calculate total width needed for this level
      const levelWidth = nodeCount * nodeWidth + (nodeCount - 1) * (nodeSpacingX - nodeWidth);

      // Calculate starting x-position to center the level
      const startX = (svgSize.width - levelWidth) / 2 + leftPadding;

      // Calculate y-position for this level
      const y = 100 + level * nodeSpacingY;

      // Position each node at this level
      nodeIdsAtLevel.forEach((nodeId, index) => {
        const x = startX + index * nodeSpacingX;
        positions[nodeId] = { x, y };
      });
    }
  }

  return positions;
};

// Calculate edge path between nodes with curved paths
export const calculateEdgePath = (
  sourceId,
  targetId,
  nodePositions,
  nodeWidth,
  nodeHeight,
  nodeSpacingX,
  nodeSpacingY
) => {
  const source = nodePositions[sourceId];
  const target = nodePositions[targetId];

  if (!source || !target) return null;

  // Determine if this is an upward-pointing edge
  const isUpwardEdge = target.y < source.y;

  // Handle self-referencing edges
  if (sourceId === targetId) {
    const x = source.x;
    const y = source.y;

    // Create a looping path on the right side of the node
    const radius = nodeWidth / 8;
    const startX = x + nodeWidth / 2;
    const startY = y - 10;
    const endX = x + nodeWidth / 2;
    const endY = y + 10;

    // Create a circular path that loops on the right side of the node
    const path = `M${startX},${startY} 
                 C${startX + radius * 1.5},${startY - radius} 
                  ${startX + radius * 1.5},${startY + radius} 
                  ${endX},${endY}`;

    // Calculate midpoint for the hit count label
    const midX = x + nodeWidth / 2 + radius;
    const midY = y;

    return { startX, startY, endX, endY, midX, midY, path, isUpwardEdge };
  }

  // Default spacing values if not provided
  const spacingY = nodeSpacingY || 150;

  // Calculate the direction vector
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const distance = Math.sqrt(dx * dx + dy * dy);

  if (distance === 0) return null;

  // Normalize the direction vector
  const nx = dx / distance;
  const ny = dy / distance;

  // Calculate start and end points (on node boundaries)
  const halfHeight = nodeHeight / 2;

  let startX, startY, endX, endY;

  // Determine which side of the source node the edge starts from
  if (isUpwardEdge) {
    // For upward edges, start from the top of the source node
    startX = source.x;
    startY = source.y - halfHeight;

    // End at the bottom of the target node with extra offset
    endX = target.x;
    endY = target.y + halfHeight + 15;
  } else {
    // For downward or horizontal edges, use the standard calculation
    startX = source.x + (nx / Math.abs(ny || 0.001)) * halfHeight;
    startY = source.y + (ny > 0 ? halfHeight : -halfHeight);

    endX = target.x - (nx / Math.abs(ny || 0.001)) * halfHeight;
    endY = target.y - (ny > 0 ? halfHeight : -halfHeight);
  }

  // Calculate path and control points
  let path = "";
  let cx1, cy1, cx2, cy2;

  if (isUpwardEdge) {
    // For upward edges, create a path that climbs up first, then curves to approach from below
    // Distance-based offset to ensure the curve is proportional to the distance
    const verticalOffset = Math.min(Math.abs(dy) * 0.5, 100);

    // First control point - go straight up from source
    cx1 = startX;
    cy1 = startY - verticalOffset;

    // Second control point - approach target from below
    cx2 = endX;
    cy2 = endY + verticalOffset * 0.5;

    path = `M${startX},${startY} C${cx1},${cy1} ${cx2},${cy2} ${endX},${endY}`;
  } else {
    // For downward edges, use the existing logic
    const isDirectVertical = Math.abs(startX - endX) < 10;
    const isLongEdge = distance > spacingY * 1.5;

    if (isDirectVertical) {
      // Straight vertical line
      path = `M${startX},${startY} L${endX},${endY}`;
    } else if (isLongEdge) {
      // For longer edges, use a more pronounced curve
      const controlPointOffset = Math.min(Math.abs(endY - startY) * 0.5, 100);

      cx1 = startX;
      cy1 = startY + controlPointOffset;
      cx2 = endX;
      cy2 = endY - controlPointOffset;

      path = `M${startX},${startY} C${cx1},${cy1} ${cx2},${cy2} ${endX},${endY}`;
    } else {
      // Default curved edge
      const controlPointOffset = Math.min(Math.abs(endY - startY) * 0.3, 50);

      cx1 = startX;
      cy1 = startY + controlPointOffset;
      cx2 = endX;
      cy2 = endY - controlPointOffset;

      path = `M${startX},${startY} C${cx1},${cy1} ${cx2},${cy2} ${endX},${endY}`;
    }
  }

  // Calculate position for the hit count label
  // For downward edges, position at 1/3 from the top
  // For upward edges, position at 1/3 from the bottom
  let t = isUpwardEdge ? 0.33 : 0.33; // Parameter along the path (0 to 1)

  // Given a cubic Bezier curve with points P0, P1, P2, P3 and parameter t (0 to 1),
  // the point on the curve is given by:
  // B(t) = (1-t)³P0 + 3(1-t)²tP1 + 3(1-t)t²P2 + t³P3
  const p0 = { x: startX, y: startY };
  const p1 = { x: cx1, y: cy1 };
  const p2 = { x: cx2, y: cy2 };
  const p3 = { x: endX, y: endY };

  // If this is a straight line, use simple linear interpolation
  if (!cx1 && !cy1 && !cx2 && !cy2) {
    const midX = startX + (endX - startX) * t;
    const midY = startY + (endY - startY) * t;
    return { startX, startY, endX, endY, midX, midY, path, isUpwardEdge };
  }

  // Calculate the position of the hit count label using the cubic Bezier formula
  const mt = 1 - t;
  const midX = mt * mt * mt * p0.x + 3 * mt * mt * t * p1.x + 3 * mt * t * t * p2.x + t * t * t * p3.x;
  const midY = mt * mt * mt * p0.y + 3 * mt * mt * t * p1.y + 3 * mt * t * t * p2.y + t * t * t * p3.y;

  return { startX, startY, endX, endY, midX, midY, path, isUpwardEdge };
};

// Helper function to validate and get the first valid source and target from arrays
export const getValidNodeIds = (edge, nodePositions) => {
  let validSourceId = null;
  let validTargetId = null;

  // Find first valid source node ID
  for (const sourceId of edge.source) {
    if (nodePositions[sourceId]) {
      validSourceId = sourceId;
      break;
    }
  }

  // Find first valid target node ID
  for (const targetId of edge.target) {
    if (nodePositions[targetId]) {
      validTargetId = targetId;
      break;
    }
  }

  return { sourceId: validSourceId, targetId: validTargetId };
};

// Helper function to calculate SVG size based on hierarchical layout
export const calculateSvgSize = (
  currentGraph,
  dimensions,
  nodeSpacingX,
  nodeSpacingY,
  navigationPathLength = 0 // Add parameter for nesting level
) => {
  if (!currentGraph || !currentGraph.nodes || currentGraph.nodes.length === 0) {
    return {
      width: dimensions.width,
      height: 400, // Ensure minimum height for empty graphs
    };
  }

  // Calculate node levels
  const levels = calculateNodeLevels(currentGraph);
  const normalizedLevels = normalizeLevels(levels);

  // Group nodes by level
  const nodesAtLevel = getNodesAtLevel(currentGraph, normalizedLevels);

  // Calculate the maximum level
  const maxLevel = Math.max(...Object.keys(nodesAtLevel).map(Number));

  // Calculate maximum number of nodes at any level
  let maxNodesInLevel = 0;
  for (let level = 0; level <= maxLevel; level++) {
    const nodeCount = (nodesAtLevel[level] || []).length;
    maxNodesInLevel = Math.max(maxNodesInLevel, nodeCount);
  }

  // Calculate minimum SVG size needed
  // Only make SVG wider than container if we have multiple nodes that won't fit
  const shouldExpandWidth = maxNodesInLevel > 1 && maxNodesInLevel * nodeSpacingX > dimensions.width;

  // Adjust width based on nesting level
  // For deeper levels, we want the SVG to fit within the narrower container
  const widthAdjustment = navigationPathLength > 0 ? 1 - navigationPathLength * 0.05 : 1;

  const minWidth = shouldExpandWidth
    ? Math.max(dimensions.width * widthAdjustment, maxNodesInLevel * nodeSpacingX * widthAdjustment)
    : dimensions.width * widthAdjustment;

  // Ensure there's enough height for all levels plus extra space for incoming/outgoing arrows
  // Add more padding at the bottom for the outgoing arrows
  const minHeight = (maxLevel + 1) * nodeSpacingY + 200;

  return {
    width: minWidth,
    height: minHeight,
  };
};
