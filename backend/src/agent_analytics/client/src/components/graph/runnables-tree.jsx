import React, { useState, useEffect, useCallback } from 'react';

// Helper function to find the path to a selected node in the graph hierarchy
const findNodePath = (graph, targetNodeId, currentPath = []) => {
  if (!graph || !graph.nodes) return null;
  
  for (const node of graph.nodes) {
    const newPath = [...currentPath, node.id];
    
    if (node.id === targetNodeId) {
      return newPath;
    }
    
    if (node.nestedGraph) {
      const foundPath = findNodePath(node.nestedGraph, targetNodeId, newPath);
      if (foundPath) return foundPath;
    }
  }
  
  return null;
};

// Helper function to recursively build tree nodes, ensuring uniqueness
const buildTreeNodes = (graph, onNodeSelect, selectedNodeId, expandedNodeIds, currentPath = '', visitedNodes = new Set()) => {
  if (!graph || !graph.nodes) {
    return [];
  }

  const treeNodes = [];

  graph.nodes
    .filter(node => node.type !== 'start' && node.type !== 'end') // Filter out start/end nodes
    .forEach(node => {
      // Skip if this node ID is already in the visited set (shown elsewhere in the tree)
      if (visitedNodes.has(node.id)) {
        return;
      }
      
      // Mark this node as visited
      visitedNodes.add(node.id);
      
      // Check if node has remaining children after filtering out duplicates and start/end nodes
      let hasRemainingChildren = false;
      if (node.nestedGraph && node.nestedGraph.nodes) {
        // Check each child - if any aren't already visited and aren't start/end nodes, this node has children to show
        hasRemainingChildren = node.nestedGraph.nodes.some(childNode => 
          !visitedNodes.has(childNode.id) && 
          childNode.type !== 'start' && 
          childNode.type !== 'end'
        );
      }
      
      treeNodes.push(
        <TreeNode
          key={node.id}
          node={node}
          hasChildren={hasRemainingChildren}
          isSelected={node.id === selectedNodeId}
          onNodeSelect={onNodeSelect}
          selectedNodeId={selectedNodeId}
          initialGraph={node.nestedGraph}
          currentPath={currentPath ? `${currentPath}/${node.id}` : node.id}
          visitedNodes={visitedNodes}
          expandedNodeIds={expandedNodeIds}
        />
      );
    });

  return treeNodes;
};

// Component for a single node in the tree
const TreeNode = ({ 
  node, 
  hasChildren, 
  isSelected, 
  onNodeSelect, 
  selectedNodeId, 
  initialGraph, 
  currentPath,
  visitedNodes,
  expandedNodeIds
}) => {
  // Determine if this node should be expanded based on the expandedNodeIds set
  const shouldBeExpanded = expandedNodeIds.has(node.id);
  const [isExpanded, setIsExpanded] = useState(shouldBeExpanded);
  const [childNodes, setChildNodes] = useState([]);

  // Update expansion state when expandedNodeIds changes
  useEffect(() => {
    setIsExpanded(shouldBeExpanded);
  }, [shouldBeExpanded]);

  // Build child nodes when expanded
  useEffect(() => {
    if (isExpanded && hasChildren && initialGraph) {
      // Use the same visitedNodes Set to maintain uniqueness across the entire tree
      setChildNodes(buildTreeNodes(
        initialGraph, 
        onNodeSelect, 
        selectedNodeId, 
        expandedNodeIds,
        currentPath, 
        visitedNodes
      ));
    } else {
      setChildNodes([]);
    }
  }, [isExpanded, hasChildren, initialGraph, onNodeSelect, selectedNodeId, currentPath, visitedNodes, expandedNodeIds]);

  const handleToggleExpand = useCallback((e) => {
    e.stopPropagation(); // Prevent node selection when clicking expand icon
    if (hasChildren) {
      setIsExpanded(!isExpanded);
    }
  }, [hasChildren, isExpanded]);

  const handleSelect = useCallback(() => {
    // When selecting a node in the tree, we want to:
    // 1. Find the node in the graph
    // 2. Navigate to its parent graph if needed
    // 3. Select it (but not navigate into it)
    
    // Pass the node ID but not its nested graph - this tells the handler
    // to select the node but not navigate into it
    onNodeSelect(node.id, node.parent_id, currentPath);
  }, [node.id, node.parent_id, currentPath, onNodeSelect]);

  // Calculate indent level from the path
  const pathSegments = currentPath.split('/');
  const indentLevel = pathSegments.length - 1;
  const isNodeSelected = isSelected || node.id === selectedNodeId;

  return (
    <div style={{ paddingLeft: `${indentLevel * 15}px` }}>
      <div
        onClick={handleSelect}
        style={{
          display: 'flex',
          alignItems: 'center',
          cursor: 'pointer',
          padding: '4px 2px',
          backgroundColor: isNodeSelected ? '#e0e0e0' : 'transparent',
          borderRadius: '3px',
          marginBottom: '2px',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
        title={node.name} // Tooltip for full name
      >
        {/* Expand/Collapse Icon - only show if hasChildren is true */}
        <span
          onClick={handleToggleExpand}
          style={{
            display: 'inline-block',
            width: '15px',
            marginRight: '5px',
            textAlign: 'center',
            cursor: hasChildren ? 'pointer' : 'default',
            opacity: hasChildren ? 1 : 0, // Hide if no children
          }}
        >
          {hasChildren ? (isExpanded ? '▼' : '►') : ''}
        </span>

        {/* Hit Count Badge */}
        <span
          style={{
            display: 'inline-flex',
            justifyContent: 'center',
            alignItems: 'center',
            width: '20px',
            height: '20px',
            backgroundColor: '#000',
            color: '#fff',
            borderRadius: '3px',
            fontSize: '0.8rem',
            marginRight: '6px',
          }}
        >
          {node.hits || 0}
        </span>
        
        {/* Node Name */}
        <span className="truncate max-w-full">{node.name}</span>
        
        {/* Reference indicator */}
        {node.isReference && (
          <span style={{ 
            marginLeft: '5px', 
            color: '#ff6b00', 
            fontSize: '0.8em', 
            fontWeight: 'bold',
            flexShrink: 0
          }}>
            (ref)
          </span>
        )}
        
        {/* Nested graph indicator */}
        {node.nestedGraph && (
          <span style={{ 
            marginLeft: '5px', 
            color: '#0f62fe', 
            fontSize: '1.2em',
            flexShrink: 0
          }}>
            ⊕
          </span>
        )}
      </div>
      
      {/* Render Child Nodes if Expanded */}
      {isExpanded && childNodes.length > 0 && (
        <div className="child-nodes">
          {childNodes}
        </div>
      )}
    </div>
  );
};

// Main RunnablesTree Component - now with auto-expansion for selected nodes
const RunnablesTree = ({ graphData, selectedNodeId, navigationPath, onNodeSelect, colors, isScrollContainer }) => {
  const [treeNodes, setTreeNodes] = useState([]);
  const [expandedNodeIds, setExpandedNodeIds] = useState(new Set());
  
  // Auto-expand to show the selected node whenever selection changes
  useEffect(() => {
    if (selectedNodeId && graphData) {
      // Find the path to the selected node in the graph hierarchy
      const pathToSelectedNode = findNodePath(graphData, selectedNodeId);
      
      if (pathToSelectedNode) {
        // Expand all parent nodes in the path (except the selected node itself)
        const newExpandedIds = new Set(expandedNodeIds);
        
        // Add each parent node in the path to the expanded set
        for (let i = 0; i < pathToSelectedNode.length - 1; i++) {
          newExpandedIds.add(pathToSelectedNode[i]);
        }
        
        setExpandedNodeIds(newExpandedIds);
      }
    }
  }, [selectedNodeId, graphData]);

  // Also expand based on navigation path
  useEffect(() => {
    if (navigationPath && navigationPath.length > 0) {
      const newExpandedIds = new Set(expandedNodeIds);
      
      // Add each node in the navigation path to the expanded set
      navigationPath.forEach((pathItem) => {
        if (pathItem && pathItem.id) {
          newExpandedIds.add(pathItem.id);
        }
      });
      
      setExpandedNodeIds(newExpandedIds);
    }
  }, [navigationPath]);
  
  // Rebuild the tree when the main graph data changes, selection changes, or expansion state changes
  useEffect(() => {
    const visitedNodes = new Set(); // Track visited nodes globally for this render pass
    setTreeNodes(buildTreeNodes(graphData, onNodeSelect, selectedNodeId, expandedNodeIds, '', visitedNodes));
  }, [graphData, selectedNodeId, onNodeSelect, expandedNodeIds]);

  return (
    <div 
      className="runnables-tree-content" 
      style={{ 
        fontFamily: '"IBM Plex Sans", sans-serif', 
        fontSize: '0.9rem',
        padding: '8px 0'
      }}
    >
      {treeNodes.length > 0 ? (
        treeNodes
      ) : (
        <div style={{ padding: '5px 12px', color: '#666' }}>
          No runnables found.
        </div>
      )}
    </div>
  );
};

export default RunnablesTree;
