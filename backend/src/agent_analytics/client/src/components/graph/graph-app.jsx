import React, { useState, useEffect } from 'react';
import BreadcrumbNavigation from './breadcrumb-navigation';
import RunnablesTree from './runnables-tree';
import ActionCallGraph from './action-call-graph'
import GraphVisualizer from './graph-visualizer';
import { carbonColors } from './graph-constants';

const findNodeInHierarchy = (graph, nodeId, path = []) => {
    // FIX: Add null/undefined checks
    if (!graph || !graph.nodes || !nodeId) return null;
    
    const node = graph.nodes.find(n => n && typeof n.id === 'string' && n.id.toLowerCase() === nodeId.toLowerCase());
    if (node) {
      return { node, path: [...path] };
    }
    for (const currentNode of graph.nodes) {
      if (currentNode.nestedGraph) {
        const result = findNodeInHierarchy(
          currentNode.nestedGraph,
          nodeId,
          [...path, { id: currentNode.id, name: currentNode.name, graph: currentNode.nestedGraph }]
        );
        if (result) return result;
      }
    }
    return null;
};

const IntegratedBreadcrumbGraph = ({ navigationPath, navigateToLevel, colors, graphData, selectedNodeId, onNodeClick, onNodeMetricsClick, hoveredNodeId, onNodeHover }) => {
  const nestingLevel = navigationPath.length;
  const isNested = nestingLevel > 0;

  const getIntegratedContainerStyling = () => {
    const shadowBlur = 12 + (nestingLevel * 15);
    const shadowSpread = nestingLevel * 4;
    const borderThickness = Math.min(3 + nestingLevel * 2, 12);
    
    return {
      background: `linear-gradient(145deg, #ffffff, #f8fafc)`,
      border: `${borderThickness}px solid #ffffff`,
      borderRadius: '16px',
      boxShadow: `
        0 ${15 + nestingLevel * 8}px ${shadowBlur}px -3px rgba(0, 0, 0, ${0.1 + nestingLevel * 0.08}),
        0 ${8 + nestingLevel * 4}px ${shadowSpread * 3}px -2px rgba(0, 0, 0, ${0.08 + nestingLevel * 0.05}),
        0 ${4 + nestingLevel * 2}px ${shadowSpread * 2}px -1px rgba(0, 0, 0, ${0.05 + nestingLevel * 0.03}),
        inset 0 2px 0 rgba(255, 255, 255, 0.3),
        inset 0 -2px 0 rgba(0, 0, 0, 0.08)
      `,
      position: 'relative',
      zIndex: 10 + nestingLevel,
      transition: 'all 0.4s cubic-bezier(0.4, 0.0, 0.2, 1)',
      width: '100%',
      marginLeft: '0',
      marginRight: '0',
    };
  };

  const containerStyling = getIntegratedContainerStyling();

  const graphPadding = `${nestingLevel * 16}px`;
  return (
    <div 
      style={{
        perspective: '1200px',
        perspectiveOrigin: '50% 50%',
        transformStyle: 'preserve-3d',
        width: '100%',
        height: '100%',
        position: 'relative',
      }}
    >
      {isNested && Array.from({length: nestingLevel}, (_, i) => {
        const layerIndex = nestingLevel - i - 1;
        const layerOffset = (layerIndex + 1) * 12;
        const layerOpacity = 0.6 - (layerIndex * 0.15);
        
        return (
          <div
            key={`integrated-bg-layer-${i}`}
            style={{
              position: 'absolute',
              top: `${layerOffset}px`,
              left: `${layerOffset}px`,
              right: `${layerOffset}px`,
              bottom: `${layerOffset}px`,
              background: `linear-gradient(145deg, rgba(248, 250, 252, ${layerOpacity}), rgba(241, 245, 249, ${layerOpacity * 0.8}))`,
              borderRadius: `${16 + layerIndex * 2}px`,
              border: `${2 + layerIndex}px solid rgba(255, 255, 255, ${layerOpacity})`,
              boxShadow: `0 ${3 + layerIndex * 3}px ${6 + layerIndex * 3}px rgba(0, 0, 0, ${0.08 + layerIndex * 0.03})`,
              zIndex: -(layerIndex + 1),
              pointerEvents: 'none',
              transform: `translateZ(-${(layerIndex + 1) * 8}px)`,
            }}
          />
        );
      })}

      <div 
        style={{ 
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          ...containerStyling
        }}
        onMouseEnter={(e) => {
          const shadowBlur = 12 + (nestingLevel * 15);
          const shadowSpread = nestingLevel * 4;
          e.currentTarget.style.boxShadow = `0 ${20 + nestingLevel * 12}px ${shadowBlur + 8}px -3px rgba(0, 0, 0, ${0.15 + nestingLevel * 0.08}), 0 ${12 + nestingLevel * 6}px ${shadowSpread * 4}px -2px rgba(0, 0, 0, ${0.12 + nestingLevel * 0.05}), 0 ${6 + nestingLevel * 3}px ${shadowSpread * 3}px -1px rgba(0, 0, 0, ${0.1 + nestingLevel * 0.03}), inset 0 2px 0 rgba(255, 255, 255, 0.4), inset 0 -2px 0 rgba(0, 0, 0, 0.12)`;
        }}
        onMouseLeave={(e) => {
          const shadowBlur = 12 + (nestingLevel * 15);
          const shadowSpread = nestingLevel * 4;
          e.currentTarget.style.boxShadow = `0 ${15 + nestingLevel * 8}px ${shadowBlur}px -3px rgba(0, 0, 0, ${0.1 + nestingLevel * 0.08}), 0 ${8 + nestingLevel * 4}px ${shadowSpread * 3}px -2px rgba(0, 0, 0, ${0.08 + nestingLevel * 0.05}), 0 ${4 + nestingLevel * 2}px ${shadowSpread * 2}px -1px rgba(0, 0, 0, ${0.05 + nestingLevel * 0.03}), inset 0 2px 0 rgba(255, 255, 255, 0.3), inset 0 -2px 0 rgba(0, 0, 0, 0.08)`;
        }}
      >
        <div 
          className="breadcrumb-container"
          style={{ 
            flexShrink: 0, 
            padding: '12px 16px', 
            borderBottom: '1px solid rgba(0, 0, 0, 0.08)',
            overflowX: 'auto',
            whiteSpace: 'nowrap',
            scrollbarWidth: 'thin',
            scrollbarColor: '#cccccc #f0f0f0',
          }}>
          <BreadcrumbNavigation
            navigationPath={navigationPath}
            navigateToLevel={navigateToLevel}
            colors={colors}
          />
        </div>
        
        <div 
          style={{
            flex: 1,
            minHeight: 0,
            position: 'relative',
            paddingLeft: graphPadding,
            paddingRight: graphPadding,
            transition: 'padding 0.4s cubic-bezier(0.4, 0.0, 0.2, 1)',
          }}
        >
          <div 
            style={{
              padding: '16px',
              width: '100%',
              height: '100%',
            }}
          >
            <GraphVisualizer
              graphData={graphData}
              selectedNodeId={selectedNodeId}
              onNodeClick={onNodeClick}
              onNodeMetricsClick={onNodeMetricsClick}
              hoveredNodeId={hoveredNodeId}
              onNodeHover={onNodeHover}
              navigationPath={navigationPath}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

const GraphVisualizerApp = ({ workflowData, onNodeMetricsClick, selectedRunnableNodeId }) => {
  const [currentGraph, setCurrentGraph] = useState(workflowData);
  const [navigationPath, setNavigationPath] = useState([]);
  // FIX: Restore internal state for selection
  const [selectedNodeId, setSelectedNodeId] = useState(selectedRunnableNodeId);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [pendingSelection, setPendingSelection] = useState(null);
  const hasNestedLevels = navigationPath.length > 0;

  useEffect(() => {
    setCurrentGraph(workflowData);
    setNavigationPath([]);
    setSelectedNodeId(null);
  }, [workflowData]);

  // FIX: Add effect to sync with external prop
  useEffect(() => {
    setSelectedNodeId(selectedRunnableNodeId);
  }, [selectedRunnableNodeId]);

  useEffect(() => {
    if (pendingSelection) {
        setSelectedNodeId(pendingSelection);
        if (onNodeMetricsClick) {
            onNodeMetricsClick(pendingSelection);
        }
        setPendingSelection(null);
    }
  }, [currentGraph, pendingSelection, onNodeMetricsClick]);

  // FIX: Restore 3-argument signature and logic
const handleNavigation = (nodeId, nestedGraphFromClick, pathOrNull) => {
    
    // Block 1: Click from ActionCallGraph (tree). The third arg is a string.
    if (typeof pathOrNull === 'string') {
        const rootWorkflowId = workflowData.id;

        // Check if the '*' node was clicked (it sends "root" as the path)
        if (pathOrNull === 'root' && nodeId === rootWorkflowId) {
            setCurrentGraph(workflowData);
            setNavigationPath([]);
            setSelectedNodeId(nodeId); // Select the root
            if (onNodeMetricsClick) {
                onNodeMetricsClick(nodeId);
            }
            return;
        }

        // Check if this is an L1 action with a nested graph that we should navigate INTO
        if (nestedGraphFromClick) {
            // Find the node in the hierarchy to build the correct path
            const targetNodeInfo = findNodeInHierarchy(workflowData, nodeId);
            if (targetNodeInfo && targetNodeInfo.node) {
                // Build the path TO this node (not including it)
                const pathToNode = targetNodeInfo.path;
                
                // Now add this node to the path and navigate into its nested graph
                const newPath = [
                    ...pathToNode,
                    { id: targetNodeInfo.node.id, name: targetNodeInfo.node.name, graph: targetNodeInfo.node.nestedGraph }
                ];
                
                setNavigationPath(newPath);
                setCurrentGraph(nestedGraphFromClick);
                setSelectedNodeId(null); 
                return;
            }
        }

        // This is a click on a regular action in the tree (L2+ node or L1 without nested graph)
        setSelectedNodeId(nodeId); 
        
        if (onNodeMetricsClick) {
            onNodeMetricsClick(nodeId);
        }
        
        const targetNodeInfo = findNodeInHierarchy(workflowData, nodeId);
        if (targetNodeInfo) {
            const parentGraph = targetNodeInfo.path.length > 0
              ? targetNodeInfo.path[targetNodeInfo.path.length - 1].graph
              : workflowData;
            
            setCurrentGraph(parentGraph);
            setNavigationPath(targetNodeInfo.path);
            setPendingSelection(nodeId); // Set pending instead of immediate
        }
        return;
    }
    
    // Block 2: Click from GraphVisualizer (graph). The third arg is NOT a string (it's null).

    if (nestedGraphFromClick) {
        // Clicked a node *with* a subgraph -> dive in
        const clickedNode = currentGraph.nodes.find(n => n.id === nodeId);
        if (!clickedNode) return;
        const newPath = [
          ...navigationPath,
          { id: clickedNode.id, name: clickedNode.name, graph: currentGraph }
        ];
        setNavigationPath(newPath);
        setCurrentGraph(nestedGraphFromClick);
        setSelectedNodeId(null); 
        return;
    }
    
    // This case is now handled by handleMetricsClick.
    // We just select the node as a fallback.
    setSelectedNodeId(nodeId);
  };
  
  // FIX: Add back the handler for metrics-only clicks
  const handleMetricsClick = (nodeId) => {
    setSelectedNodeId(nodeId);
    if (onNodeMetricsClick) {
      onNodeMetricsClick(nodeId);
    }
  };

  const handleLevelNavigation = (levelIndex) => {
    if (levelIndex === -1) {
      setCurrentGraph(workflowData);
      setNavigationPath([]);
      // FIX: Select root and show its metrics
      const rootWorkflowId = workflowData.id;
      setSelectedNodeId(rootWorkflowId); 
      if (onNodeMetricsClick) {
          onNodeMetricsClick(rootWorkflowId);
      }
      return;
    }

    const targetNodeInfo = findNodeInHierarchy(workflowData, navigationPath[levelIndex].id);
    if (targetNodeInfo && targetNodeInfo.node && targetNodeInfo.node.nestedGraph) {
      const newPath = navigationPath.slice(0, levelIndex + 1);
      setCurrentGraph(targetNodeInfo.node.nestedGraph);
      setNavigationPath(newPath);
      setSelectedNodeId(null); 
    }
  };

  return (
    <div className="w-full h-full flex" style={{ overflow: 'hidden' }}>
      <style>{`
        .window-frame { display: none !important; }
        .breadcrumb-window-topbar, .graph-container { transition: all 0.4s cubic-bezier(0.4, 0.0, 0.2, 1); }
        .breadcrumb-window-container, .graph-container { transform-style: preserve-3d; }
        .breadcrumb-container::-webkit-scrollbar { height: 6px; }
        .breadcrumb-container::-webkit-scrollbar-track { background: rgba(0, 0, 0, 0.05); border-radius: 3px; }
        .breadcrumb-container::-webkit-scrollbar-thumb { background: #cccccc; border-radius: 3px; }
        .breadcrumb-container::-webkit-scrollbar-thumb:hover { background: #aaaaaa; }
      `}</style>
      
      <div className="w-[250px] h-full flex flex-col overflow-hidden border-r border-gray-300">
        <div className="flex-shrink-0">
          <h3 style={{ 
            padding: '8px 12px', 
            margin: 0, 
            fontWeight: '600', 
            borderBottom: `1px solid ${carbonColors.tileBorder || '#e0e0e0'}`,
            backgroundColor: carbonColors.breadcrumbBg || '#f4f4f4',
            ...(hasNestedLevels && {
              boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
              transform: 'translateZ(2px)',
            })
          }}>
            Action Call Graph
          </h3>
        </div>
        <div className="flex-1 overflow-auto">
          <ActionCallGraph
            graphData={workflowData}
            selectedNodeId={selectedNodeId} // FIX: Pass internal state
            navigationPath={navigationPath}
            onNodeSelect={handleNavigation}
            colors={carbonColors}
            isScrollContainer={true}
          />
        </div>
      </div>
      
      <div 
        className="flex-1 h-full"
        style={{ 
          padding: '16px',
          overflow: 'hidden',
        }}
      >
        <IntegratedBreadcrumbGraph
          navigationPath={navigationPath}
          navigateToLevel={handleLevelNavigation}
          colors={carbonColors}
          graphData={currentGraph}
          selectedNodeId={selectedNodeId} // FIX: Pass internal state
          onNodeClick={handleNavigation}
          onNodeMetricsClick={handleMetricsClick} // FIX: Pass correct handler
          hoveredNodeId={hoveredNode}
          onNodeHover={setHoveredNode}
        />
      </div>
    </div>
  );
};

export default React.memo(GraphVisualizerApp);