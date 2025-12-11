//import { ReactComponent as YourSvg } from '.../icons/cog.svg';
import cogIcon from "../../icons/cog.svg";
import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';

const Tooltip = ({ children, text }) => {
  const [isVisible, setIsVisible] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const targetRef = useRef(null);

  const handleMouseEnter = (e) => {
    if (targetRef.current) {
      const rect = targetRef.current.getBoundingClientRect();
      setPosition({
        top: rect.top - 8, // Position above the badge
        left: rect.left + rect.width / 2, // Center horizontally
      });
    }
    setIsVisible(true);
  };

  const handleMouseLeave = () => {
    setIsVisible(false);
  };

  return (
    <>
      <div 
        ref={targetRef}
        style={{ display: 'inline-flex' }}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        {children}
      </div>
      {isVisible && (
        <div
          style={{
            position: 'fixed',
            top: `${position.top}px`,
            left: `${position.left}px`,
            transform: 'translateX(-50%) translateY(-100%)',
            backgroundColor: '#1f2937',
            color: 'white',
            padding: '6px 10px',
            borderRadius: '6px',
            fontSize: '0.75rem',
            whiteSpace: 'nowrap',
            zIndex: 9999,
            pointerEvents: 'none',
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
          }}
        >
          {text}
          <div
            style={{
              position: 'absolute',
              top: '100%',
              left: '50%',
              transform: 'translateX(-50%)',
              width: 0,
              height: 0,
              borderLeft: '5px solid transparent',
              borderRight: '5px solid transparent',
              borderTop: '5px solid #1f2937',
            }}
          />
        </div>
      )}
    </>
  );
};

// --- SVG Icons ---
// A simple "action" icon (lightning bolt for "action")
const ActionIcon = () => (
  <img src={cogIcon} alt="" className="w-4 h-4 mr-1 shrink-0" />
);

// A "call" icon (arrow style)
const CallIcon = () => (
  <svg
    width="16"
    height="16"
    viewBox="0 0 16 16"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    style={{ flexShrink: 0, marginRight: '6px', marginLeft: '2px' }}
  >
    <path
      d="M10.0002 11.3333L9.06016 10.3933L11.1135 8.33331H2.66683V6.99998H11.1135L9.06016 4.93998L10.0002 3.99998L13.3335 7.66665L10.0002 11.3333Z"
      fill="#718096"
    />
  </svg>
);


// --- Helper Functions ---

/**
 * Checks if a node is a runnable action (i.e., not start/end or a gateway).
 */
const isActionNode = (node) => {
  // FIX: Add a typeof check to prevent crash on null/undefined .type
  if (!node || typeof node.type !== 'string') return false;
  const type = node.type.toUpperCase();
  return type !== 'START' && type !== 'END' && type !== 'XOR' && type !== 'AND' && type !== 'OR';
};

/**
 * Recursively traverses the entire graph and collects all unique action nodes,
 * aggregating them by NAME.
 * - Trace count: UNION of all unique trace_ids across all instances
 * - Task count: SUM of all hits across all instances
 * - Structural properties (nestedGraph, primary_id): Based on "most outer level" principle
 * 
 * @param {object} graph - The graph data to traverse.
 * @param {Map<string, object>} allActionsMap - A Map to store unique nodes by name.
 * @param {number} currentDepth - The current recursion depth.
 */
const collectAllActions = (graph, allActionsMap, currentDepth = 0) => {
  if (!graph || !graph.nodes) return;

  for (const node of graph.nodes) {
    // Only process action nodes
    if (isActionNode(node)) {
      if (!allActionsMap.has(node.name)) {
        // First time seeing this action name. Create a new aggregated entry.
        allActionsMap.set(node.name, {
          name: node.name,
          parent_id: node.parent_id,
          hits: node.hits || 0, // Task count - will be summed
          trace_ids: new Set(node.trace_ids || []), // Unique trace IDs - will be unioned
          all_ids: new Set([node.id]),
          nestedGraph: node.nestedGraph,
          primary_id: node.id,
          depth: currentDepth
        });
      } else {
        // Action name already exists. Get existing entry.
        const existing = allActionsMap.get(node.name);

        // ALWAYS aggregate the counts regardless of depth
        existing.hits += (node.hits || 0); // SUM all task counts
        
        // Union trace IDs to get unique traces across all instances
        const newTraceIds = node.trace_ids || [];
        if (Array.isArray(newTraceIds)) {
          newTraceIds.forEach(id => existing.trace_ids.add(id));
        }
        
        existing.all_ids.add(node.id);

        // Update structural properties based on "most outer level" principle
        if (currentDepth < existing.depth) {
          // This new node is at a *shallower* level (it's "more outer").
          // Use its structural properties (nestedGraph, primary_id, etc.)
          existing.parent_id = node.parent_id;
          existing.nestedGraph = node.nestedGraph;
          existing.primary_id = node.id;
          existing.depth = currentDepth;
        }
      }
    }

    // Recurse into nested graphs, incrementing depth
    if (node.nestedGraph) {
      collectAllActions(node.nestedGraph, allActionsMap, currentDepth + 1);
    }
  }
};

/**
 * Helper function to find the path to a selected node in the graph hierarchy.
 * This is still needed for auto-expanding to a selected L2+ node.
 */
const findNodePath = (graph, targetNodeId, currentPath = []) => {
  if (!graph || !graph.nodes) return null;

  for (const node of graph.nodes) {
    // Only search through valid action/gateway nodes
    if (node.type !== 'START' && node.type !== 'END') {
      const newPath = [...currentPath, node.id];

      if (node.id === targetNodeId) {
        return newPath;
      }

      if (node.nestedGraph) {
        const foundPath = findNodePath(node.nestedGraph, targetNodeId, newPath);
        if (foundPath) return foundPath;
      }
    }
  }

  return null;
};

/**
 * Recursively builds tree nodes for L2 ("invocations") and deeper.
 * @param {object} graph - The graph to build nodes from (e.g., node.nestedGraph).
 * @param {function} onNodeSelect - Callback for when a node is clicked.
 * @param {string} selectedNodeId - The currently selected node ID.
 * @param {Set<string>} expandedNodeIds - Set of IDs for expanded nodes.
 * @param {string} currentPath - The path to the current graph level.
 * @param {number} depth - Current depth in the tree.
 */
const buildChildTreeNodes = (graph, onNodeSelect, selectedNodeId, expandedNodeIds, currentPath, depth) => {
  if (!graph || !graph.nodes) {
    return [];
  }

  // Filter out start/end/gateways and sort alphabetically
  const childNodes = graph.nodes
    .filter(isActionNode)
    .sort((a, b) => a.name.localeCompare(b.name));

  return childNodes.map(node => (
    <TreeNode
      key={node.id}
      node={node}
      isLevelOne={false} // These are explicitly L2+ nodes
      isSelected={node.id === selectedNodeId}
      onNodeSelect={onNodeSelect}
      selectedNodeId={selectedNodeId}
      initialGraph={node.nestedGraph}
      currentPath={currentPath ? `${currentPath}/${node.id}` : node.id}
      expandedNodeIds={expandedNodeIds}
      depth={depth}
    />
  ));
};

/**
 * Component for a single node in the tree (L1 Action or L2 Invocation).
 */
const TreeNode = ({
  node,
  isLevelOne,
  isSelected,
  onNodeSelect,
  selectedNodeId,
  initialGraph,
  currentPath,
  expandedNodeIds,
  depth = 0,
  demiChildrenData = null // Special prop for the "demi" node
}) => {
  const isDemiNode = node.isDemiNode === true;

  // Determine if this node should be expanded based on the expandedNodeIds set
  const shouldBeExpanded = useMemo(() => {
    if (isDemiNode) {
      // The demi node is expanded if its special ID is in the set
      return expandedNodeIds.has(node.primary_id);
    }
    // L1 nodes are expandable
    if (isLevelOne) {
      // L1: Check if *any* of the aggregated IDs are in the expansion set
      return [...node.all_ids].some(id => expandedNodeIds.has(id));
    }
    // L2 nodes are NOT expandable
    return false;
  }, [isDemiNode, isLevelOne, node, expandedNodeIds]);

  const [isExpanded, setIsExpanded] = useState(shouldBeExpanded);
  const [childNodes, setChildNodes] = useState([]);

  // Filter nested graph to see if there are any *renderable* children
  const hasRenderableChildren = useMemo(() => {
    if (isDemiNode) return demiChildrenData && demiChildrenData.length > 0; // Check demiChildrenData
    
    // L1 nodes are expandable if they have a nested graph with children
    if (isLevelOne) {
        if (!initialGraph || !initialGraph.nodes) return false;
        return initialGraph.nodes.some(isActionNode);
    }
    
    // L2+ nodes are NOT expandable
    return false;
  }, [isDemiNode, isLevelOne, demiChildrenData, initialGraph]);

  // Check if node has a nested graph (workflow) for navigation
  const hasNestedGraph = !isDemiNode && (initialGraph && initialGraph.nodes && initialGraph.nodes.length > 0);

  // Update expansion state when expandedNodeIds changes (e.g., from auto-expand)
  useEffect(() => {
    setIsExpanded(shouldBeExpanded);
  }, [shouldBeExpanded]);

  // Build child nodes (L2 invocations or L1 for demi) when expanded
  useEffect(() => {
    if (isExpanded && hasRenderableChildren) {
      if (isDemiNode) {
        // Build L1 nodes as *children* of the demi node.
        setChildNodes(demiChildrenData.map(action => {
          // FIX 3: Only highlight if the exact node ID matches
          const isSelected = action.primary_id === selectedNodeId;
          return (
            <TreeNode
              key={action.name}
              node={action}
              isLevelOne={false} // <-- This will cause indent
              isSelected={isSelected}
              onNodeSelect={onNodeSelect}
              selectedNodeId={selectedNodeId}
              initialGraph={action.nestedGraph}
              currentPath={action.name} 
              expandedNodeIds={expandedNodeIds}
              depth={1} // FIX 1: Set depth to 1 for demi children
            />
          );
        }));
      } else if (isLevelOne && initialGraph) { // FIX: Check for isLevelOne
        // Standard L2+ logic (Only for L1 nodes)
        setChildNodes(buildChildTreeNodes(
          initialGraph,
          onNodeSelect,
          selectedNodeId,
          expandedNodeIds,
          currentPath,
          depth + 1 // FIX 1: Pass incremented depth
        ));
      }
    } else {
      setChildNodes([]);
    }
  }, [isExpanded, hasRenderableChildren, initialGraph, onNodeSelect, selectedNodeId, expandedNodeIds, currentPath, isDemiNode, isLevelOne, demiChildrenData, depth]);

  const handleToggleExpand = useCallback((e) => {
    e.stopPropagation(); // Prevent node selection
    if (hasRenderableChildren) {
      setIsExpanded(!isExpanded);
    }
  }, [hasRenderableChildren, isExpanded]);

  const handleSelect = useCallback(() => {
    const nodeId = node.primary_id || node.id;
    
    if (isDemiNode) {
      onNodeSelect(nodeId, undefined, "root");
    } else if (isLevelOne && hasNestedGraph) {
      onNodeSelect(nodeId, initialGraph, node.name);
    } else if (isLevelOne) {
      return;
    } else {
      onNodeSelect(nodeId, undefined, currentPath);
    }
  }, [isDemiNode, isLevelOne, hasNestedGraph, node, currentPath, onNodeSelect, initialGraph]);

  // FIX 1: Use depth prop for indentation
  const indentLevel = depth;

  // Calculate display values
  const traceCount = node.trace_ids ? node.trace_ids.size : (node.traces || 0);
  const taskCount = node.hits || 0;

  return (
    <div style={{ paddingLeft: `${indentLevel * 20}px` }}>
      <div
        onClick={handleSelect}
        style={{
          display: 'flex',
          alignItems: 'center',
          cursor: 'pointer',
          padding: '5px 4px',
          backgroundColor: (!isLevelOne && isSelected) ? '#e0e0e0' : 'transparent',
          borderRadius: '4px',
          marginBottom: '2px',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
        title={node.name}
      >
        {isLevelOne ? <ActionIcon /> : <CallIcon />}

        <span
          onClick={handleToggleExpand}
          style={{
            display: 'inline-block',
            width: '18px',
            marginRight: '4px',
            textAlign: 'center',
            cursor: hasRenderableChildren ? 'pointer' : 'default',
            opacity: hasRenderableChildren ? 1 : 0,
            flexShrink: 0,
          }}
        >
          {hasRenderableChildren ? (isExpanded ? '▼' : '►') : (isLevelOne ? ' ' : ' ')}
        </span>

        <span
          className="truncate max-w-full"
          style={{ fontWeight: isLevelOne ? 500 : 400 }}
        >
          {node.name}
        </span>

        <span style={{ flexGrow: 1 }} />

        {isLevelOne && !isDemiNode && (
          <div 
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              flexShrink: 0, 
              marginLeft: '8px',
              gap: '5px'
            }}
            onClick={(e) => e.stopPropagation()} // Prevent triggering parent click
          >
            {/* Trace Count Badge with Tooltip */}
            <Tooltip text={`Unique traces: ${traceCount}`}>
              <span
                style={{
                  display: 'inline-flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  minWidth: '22px',
                  height: '20px',
                  backgroundColor: '#E0E7FF',
                  color: '#3730A3',
                  borderRadius: '4px',
                  fontSize: '0.8rem',
                  fontWeight: '500',
                  padding: '0 5px',
                  cursor: 'help',
                }}
              >
                {traceCount}
              </span>
            </Tooltip>

            {/* Task Count Badge with Tooltip */}
            <Tooltip text={`Total executions: ${taskCount}`}>
              <span
                style={{
                  display: 'inline-flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  minWidth: '22px',
                  height: '20px',
                  backgroundColor: '#F3F4F6',
                  color: '#374151',
                  borderRadius: '4px',
                  fontSize: '0.8rem',
                  fontWeight: '500',
                  padding: '0 5px',
                  cursor: 'help',
                }}
              >
                {taskCount}
              </span>
            </Tooltip>
          </div>
        )}
      </div>

      {isExpanded && childNodes.length > 0 && (
        <div className="child-nodes">
          {childNodes}
        </div>
      )}
    </div>
  );
};

/**
 * Main Action Call Graph Component.
 * Displays a L1 flat list of all unique actions and
 * allows expanding them to see L2 invocations.
 */
const ActionCallGraph = ({ graphData, selectedNodeId, navigationPath, onNodeSelect, colors, isScrollContainer }) => {
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
        for (let i = 0; i < pathToSelectedNode.length - 1; i++) {
          newExpandedIds.add(pathToSelectedNode[i]);
        }
        setExpandedNodeIds(newExpandedIds);
      }
    }
  }, [selectedNodeId, graphData]); // expandedNodeIds removed from deps to prevent re-cloning

  // Also expand based on navigation path
  useEffect(() => {
    if (navigationPath && navigationPath.length > 0) {
      const newExpandedIds = new Set(expandedNodeIds);
      navigationPath.forEach((pathItem) => {
        if (pathItem && pathItem.id) {
          newExpandedIds.add(pathItem.id);
        }
      });
      setExpandedNodeIds(newExpandedIds);
    }
  }, [navigationPath]); // expandedNodeIds removed from deps

  // Rebuild the L1 tree when the main graph data changes
  useEffect(() => {
    if (!graphData) {
      setTreeNodes([]);
      return;
    }

    // 1. Collect all unique actions from the entire graph (aggregated by name)
    const allActionsMap = new Map();
    collectAllActions(graphData, allActionsMap, 0); // Pass initial depth 0

    // 2. Convert to array and sort alphabetically
    const allActionsList = Array.from(allActionsMap.values())
      .sort((a, b) => a.name.localeCompare(b.name));
      
    // 3. Create a list of *only* root-level (depth 0) actions
    const rootActionsList = allActionsList.filter(action => action.depth === 0);

    // 4. Map to TreeNode components (Level 1)
    const l1TreeNodes = allActionsList.map(action => {
      // FIX 3: L1 nodes are never "selected" (no highlighting)
      const isSelected = false;

      return (
        <TreeNode
          key={action.name} // Use name for unique key
          node={action} // Pass the aggregated action object
          isLevelOne={true}
          isSelected={isSelected}
          onNodeSelect={onNodeSelect}
          selectedNodeId={selectedNodeId}
          initialGraph={action.nestedGraph}
          currentPath={action.name} // L1 path is its name
          expandedNodeIds={expandedNodeIds}
          depth={0} // FIX 1: L1 nodes have depth 0
        />
      );
    });

    // 5. Create the "Demi" node
    //    Counts are based on *root level actions only*
    const totalHits = rootActionsList.reduce((acc, n) => acc + (n.hits || 0), 0);
    
    // Union all trace_ids from root actions
    const allTraceIds = new Set();
    rootActionsList.forEach(action => {
      if (action.trace_ids) {
        action.trace_ids.forEach(id => allTraceIds.add(id));
      }
    });
    const totalTraces = allTraceIds.size;

    // FIX: Find the *actual* root workflow ID
    // We get the parent_id from the first root-level action.
    // This parent_id *is* the root workflow ID you specified.
    let rootWorkflowId = "DEFAULT_ROOT_ID_FALLBACK"; // Fallback
    if (rootActionsList.length > 0 && rootActionsList[0].parent_id) {
        rootWorkflowId = rootActionsList[0].parent_id;
    } else if (graphData && graphData.id) {
        // Fallback to graphData.id if no root actions are found (e.g., empty graph)
        rootWorkflowId = graphData.id;
    }

    const demiNodeId = rootWorkflowId; // This is the ID we want to navigate to

    const demiNodeData = {
      name: "* (All Actions)",
      parent_id: null,
      hits: totalHits,
      trace_ids: allTraceIds, // Store as Set
      traces: totalTraces,
      all_ids: new Set([demiNodeId]), // ID for selection matching
      nestedGraph: null, // Not used
      primary_id: demiNodeId, // This ID will be sent on click
      depth: -1, // Special depth
      isDemiNode: true // Special flag
    };

    const demiTreeNode = (
      <TreeNode
        key={demiNodeData.primary_id}
        node={demiNodeData}
        isLevelOne={true}
        isSelected={selectedNodeId === demiNodeData.primary_id} // Select if root is selected
        onNodeSelect={onNodeSelect} // Parent will get the root graph ID
        selectedNodeId={selectedNodeId}
        demiChildrenData={rootActionsList} // Pass L1 data as children data
        initialGraph={null}
        currentPath={demiNodeData.name}
        expandedNodeIds={expandedNodeIds}
        depth={0} // FIX 1: Demi node has depth 0
      />
    );

    // 6. Set the final tree nodes list
    setTreeNodes([demiTreeNode, ...l1TreeNodes]);

  }, [graphData, selectedNodeId, onNodeSelect, expandedNodeIds]);

  return (
    <div
      className="runnables-tree-content"
      style={{
        fontFamily: '"IBM Plex Sans", sans-serif',
        fontSize: '0.9rem',
        padding: '8px 4px'
      }}
    >
      {treeNodes.length > 0 ? (
        treeNodes
      ) : (
        <div style={{ padding: '5px 12px', color: '#666' }}>
          No actions found.
        </div>
      )}
    </div>
  );
};

export default ActionCallGraph;