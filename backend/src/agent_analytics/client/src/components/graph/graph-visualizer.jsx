import React, { useEffect, useState, useRef } from 'react';
import Cytoscape from 'cytoscape';
import CytoscapeComponent from 'react-cytoscapejs';
import dagre from 'cytoscape-dagre';
import { EDGE_COLOR_SELF_LOOP, EDGE_COLOR_SEQUENTIAL, stylesheet, EDGE_COLOR_HOVER_SELF_LOOP, EDGE_COLOR_HOVER_SEQUENTIAL} from './graph-constants';

// Register the dagre layout extension so Cytoscape can use it
Cytoscape.use(dagre);

/**
 * Creates a circular SVG data URI for edge labels.
 * @param {string} label - The text to display inside the circle.
 * @param {string} color - The background color of the circle.
 * @returns {string} - The SVG data URI.
 */
const createEdgeLabelSvg = (label, color) => {
    const radius = 12;
    const width = 24;
    const height = 24;
    const textColor = 'white';
    const borderColor = 'white';
    const borderWidth = 2;

    // SVG containing a circle with a white border and centered text
    const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" style="background: transparent;">
        <circle cx="${radius}" cy="${radius}" r="${radius - borderWidth / 2}" fill="${color}" stroke="${borderColor}" stroke-width="${borderWidth}" />
        <text x="50%" y="50%" font-family="Helvetica, Arial, sans-serif" text-anchor="middle" dominant-baseline="central" fill="${textColor}" font-size="12" font-weight="bold">${label}</text>
    </svg>`;

    return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
};

/**
 * Creates an SVG data URI for task nodes.
 * This version places the hit count in a consistent top position and the icon below it.
 */
const createTaskNodeSvg = (taskCounter, text, hasSubWorkflow, isSelected = false) => {
    const displayText = text.length > 14 ? `${text.substring(0, 11)}...` : text;

    // The icon to display for sub-workflows, placed below the hit count.
    const subWorkflowIcon = hasSubWorkflow ? `
        <g transform="translate(20, 45)" style="pointer-events: none;">
            <circle r="8" stroke="#ffffff" stroke-width="2" fill="none" opacity="0.8" />
            <line x1="5" y1="5" x2="10" y2="10" stroke="#ffffff" stroke-width="2.5" />
            <line x1="-4" y1="0" x2="4" y2="0" stroke="#ffffff" stroke-width="2" />
            <line x1="0" y1="-4" x2="0" y2="4" stroke="#ffffff" stroke-width="2" />
        </g>
    ` : '';

    // Colors - more subtly different when selected
    const grayPartColor = isSelected ? "#1F2937" : "#374151";  // Subtly darker when selected
    const bluePartColor = isSelected ? "#3B82F6" : "#93C5FD";   // More saturated blue when selected
    
    // Create the exact same paths as the main shapes for the border
    const grayPartPath = "M 0,12 A 12,12 0 0,1 12,0 H 40 V 60 H 12 A 12,12 0 0,1 0,48 Z";
    const bluePartPath = "M 40,0 H 168 A 12,12 0 0,1 180,12 V 48 A 12,12 0 0,1 168,60 H 40 Z";
    
    // Selection styling - subtle glow effect instead of harsh border
    const selectionEffect = isSelected ? `
        <defs>
            <filter id="selection-glow" x="-15%" y="-15%" width="130%" height="130%">
                <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                <feMerge> 
                    <feMergeNode in="coloredBlur"/>
                    <feMergeNode in="SourceGraphic"/>
                </feMerge>
            </filter>
        </defs>
    ` : '';
    
    // Light outline for selected state
    const selectionOutline = isSelected ? `
        <path d="${grayPartPath}" fill="none" stroke="#3B82F6" stroke-width="2" opacity="0.7"/>
        <path d="${bluePartPath}" fill="none" stroke="#3B82F6" stroke-width="2" opacity="0.7"/>
    ` : '';
    
    const textXPosition = 55;
    const hitCountYPosition = 22;

    const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="180" height="60" style="background: transparent;">
        ${selectionEffect}
        <!-- Main node shapes with subtle glow when selected -->
        <g ${isSelected ? 'filter="url(#selection-glow)"' : ''}>
            <path d="${grayPartPath}" fill="${grayPartColor}"/>
            <path d="${bluePartPath}" fill="${bluePartColor}"/>
        </g>
        
        <!-- Subtle selection outline -->
        ${selectionOutline}
        
        <!-- Text and icons -->
        <text x="20" y="${hitCountYPosition}" font-family="Helvetica, Arial, sans-serif" text-anchor="middle" dominant-baseline="central" fill="white" font-size="18" font-weight="bold">${taskCounter || 0}</text>
        ${subWorkflowIcon}
        <text x="${textXPosition}" y="30" font-family="Helvetica, Arial, sans-serif" dominant-baseline="central" fill="#161616" font-size="15" font-weight="bold">${displayText}</text>
    </svg>`;

    return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
};

const CytoscapeTooltip = ({ nodeData, position }) => {
    if (!nodeData || !position) return null;

    const isReference = nodeData.isReference === true;
    const isClickableReference = isReference && nodeData.referenceTo;

    const dynamicStyles = {
        left: `${position.x}px`,
        top: `${position.y}px`,
        transform: 'translateX(25px) translateY(-50%)', // Move right and vertically center
    };

    const arrowStyle = {
        position: 'absolute',
        top: '50%',
        left: '-10px',
        transform: 'translateY(-50%)',
        width: 0,
        height: 0,
        borderTop: '10px solid transparent',
        borderBottom: '10px solid transparent',
        borderRight: '10px solid #374151', // Points left
    };

    return (
        <div 
            className="absolute bg-gray-700 text-white px-3 py-2 rounded text-xs font-sans min-w-50 text-left pointer-events-none z-50 opacity-95 transition-opacity duration-200 ease-in-out"
            style={dynamicStyles}
        >
            <div>{`Name: ${nodeData.name}`}</div>
            <div className="mt-1">{`ID: ${nodeData.id} | Hits: ${nodeData.hits}`}</div>
            {isReference && (
                <div className="mt-1 text-orange-500 font-bold">
                    {`References: ${nodeData.referenceTo}${isClickableReference ? " (clickable)" : ""}`}
                </div>
            )}
            <div style={arrowStyle} />
        </div>
    );
};

// --- Constants defined outside the component to prevent re-creation on re-renders ---
// UPDATED: Reduced margins for better screen usage
const dagreLayout = {
    name: 'dagre',
    rankDir: 'TB',
    spacingFactor: 1, 
    nodeSep: 60, 
    rankSep: 60,
    edgeSep: 10, 
    marginX: 5,    // Reduced from 15
    marginY: 10,   // Reduced from 35
};

const presetLayout = { name: 'preset' };
const cytoscapeComponentStyle = { width: '100%', height: '100%' };

// Constants for the split-click logic
const TASK_NODE_WIDTH = 180;
const TASK_NODE_SPLIT_WIDTH = 40;

/**
 * A graph visualizer component using Cytoscape.js with dramatic 3D popping effect for nested levels.
 */
const GraphVisualizer = ({ graphData, onNodeClick, onNodeMetricsClick, selectedNodeId, onNodeHover, navigationPath = []}) => {
    const [elements, setElements] = useState([]);
    const [graphKey, setGraphKey] = useState(0);
    const cyRef = useRef(null);
    const [tooltip, setTooltip] = useState({ visible: false, data: null, position: null });
    const graphContainerRef = useRef(null); 

    // Calculate nesting level for 3D effect
    const nestingLevel = navigationPath ? navigationPath.length : 0;
    const isNested = nestingLevel > 0;

    // Enhanced 3D "popping out" styling
    const get3DContainerStyling = () => {
        if (!isNested) {
            // Root level - flat base with minimal padding
            return {
                background: 'linear-gradient(145deg, #f9fafb, #f3f4f6)',
                border: '1px solid #e5e7eb',
                borderRadius: '12px',
                boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
                transform: 'translateZ(0px)',
                position: 'relative',
                zIndex: 1,
                padding: '4px', // Reduced from 8px
            };
        }

        // Calculate dramatic 3D effects based on nesting level
        const elevationOffset = nestingLevel * 25; // Each level rises 25px higher
        const shadowBlur = 10 + (nestingLevel * 15); // Progressive shadow blur
        const shadowSpread = nestingLevel * 4; // Shadow spread
        const borderThickness = Math.min(3 + nestingLevel * 2, 12); // Thicker borders for deeper levels
        const scaleEffect = 1 + (nestingLevel * 0.03); // Slight scale increase
        
        return {
            background: `linear-gradient(145deg, #ffffff, #f8fafc)`,
            border: `${borderThickness}px solid #ffffff`,
            borderRadius: '16px',
            boxShadow: `
                0 ${15 + elevationOffset}px ${shadowBlur}px -3px rgba(0, 0, 0, ${0.2 + nestingLevel * 0.08}),
                0 ${8 + elevationOffset/2}px ${shadowSpread * 3}px -2px rgba(0, 0, 0, ${0.15 + nestingLevel * 0.05}),
                0 ${4 + elevationOffset/4}px ${shadowSpread * 2}px -1px rgba(0, 0, 0, ${0.1 + nestingLevel * 0.03}),
                inset 0 2px 0 rgba(255, 255, 255, 0.3),
                inset 0 -2px 0 rgba(0, 0, 0, 0.08)
            `,
            transform: `
                translateY(-${elevationOffset}px) 
                translateZ(${nestingLevel * 15}px)
                scale(${scaleEffect})
                rotateX(${nestingLevel * 1.5}deg)
            `,
            transformStyle: 'preserve-3d',
            position: 'relative',
            zIndex: 10 + nestingLevel,
            transition: 'all 0.4s cubic-bezier(0.4, 0.0, 0.2, 1)',
            padding: '8px', // Reduced from 16px
        };
    };

    // Add perspective to parent container
    const getParentContainerStyling = () => {
        const windowMargin = nestingLevel === 0 ? "0" : `${nestingLevel * 16}px`;
        const windowWidth = nestingLevel === 0 ? "100%" : `calc(100% - ${nestingLevel * 32}px)`;
        
        return {
            perspective: '1200px',
            perspectiveOrigin: '50% 50%',
            transformStyle: 'preserve-3d',
            width: windowWidth,       // Was: '100%'
            marginLeft: windowMargin,  // Add this
            marginRight: windowMargin, // Add this
            height: '100%',
            position: 'relative',
            transition: 'all 0.4s cubic-bezier(0.4, 0.0, 0.2, 1)',
        };
    };

    const containerStyling = get3DContainerStyling();

    // This effect transforms your workflow data into a format Cytoscape understands
    useEffect(() => {
        if (!graphData || !graphData.nodes) {
            setElements([]);
            return;
        }
        console.log(graphData)
        const nodes = graphData.nodes.map(node => {
            let nodeClasses = '';
            const data = { id: node.id, label: node.name, ...node };

            switch (node.type) {
                case 'start': nodeClasses = 'start-node'; data.label = 'start'; break;
                case 'end': nodeClasses = 'end-node'; data.label = 'end'; break;
                case 'XOR': case 'AND': case 'OR':
                    nodeClasses = `gateway-${node.type.toLowerCase()}`;
                    data.label = node.type;
                    break;
                default:
                    nodeClasses = 'task-node';
                    data.label = '';
                    // Create unselected SVG initially - selection will be handled separately
                    data.svg_background = createTaskNodeSvg(node.hits, node.name, !!node.nestedGraph, false);
                    data.has_sub_workflow = !!node.nestedGraph;
                    break;
            }
            return { group: 'nodes', data, classes: nodeClasses };
        });

        const edges = graphData.edges.map((edge, i) => {
            const isSelfLoop = edge.source === edge.target;
            return {
                group: 'edges',
                data: {
                    id: `e-${edge.source}-${edge.target}-${i}`,
                    source: edge.source,
                    target: edge.target,
                    label: String(edge.weight || ''),
                },
                classes: isSelfLoop ? 'edge-self-loop' : 'edge-sequential'
            };
        });

        setElements(CytoscapeComponent.normalizeElements({ nodes, edges }));
        setGraphKey(key => key + 1);
    }, [graphData]); // Only rebuild when graphData changes

    // This effect handles node selection - UPDATED: runs after layout completes
    useEffect(() => {
        if (cyRef.current && cyRef.current.nodes().length > 0) {
            // Small delay to ensure layout is complete
            const timer = setTimeout(() => {
                cyRef.current.nodes('.task-node').forEach(node => {
                    const nodeData = node.data();
                    const isSelected = selectedNodeId === nodeData.id;
                    const newSvg = createTaskNodeSvg(nodeData.hits, nodeData.name, !!nodeData.nestedGraph, isSelected);
                    
                    // Force the node to update its background
                    node.data('svg_background', newSvg);
                    node.style('background-image', newSvg);
                });
                
                // Force a redraw
                cyRef.current.forceRender();
            }, 50); // Small delay to ensure Cytoscape is ready
            
            return () => clearTimeout(timer);
        }
    }, [selectedNodeId, graphKey]);

    useEffect(() => {
        const cy = cyRef.current;
        const container = graphContainerRef.current; 
        
        if (!cy || !container) return;

        const resizeObserver = new ResizeObserver(() => {
            if (cy && !cy.destroyed) {
                cy.resize(); 
                cy.fit(null, 15); // UPDATED: Reduced fit padding from 30 to 15
            }
        });

        resizeObserver.observe(container);

        return () => resizeObserver.disconnect();
    }, [graphKey]);

    // This effect handles node selection from the parent component - UPDATED: Force SVG refresh
    useEffect(() => {
        if (cyRef.current) {
            cyRef.current.nodes('.task-node').forEach(node => {
                const nodeData = node.data();
                const isSelected = selectedNodeId === nodeData.id;
                const newSvg = createTaskNodeSvg(nodeData.hits, nodeData.name, !!nodeData.nestedGraph, isSelected);
                
                // Force the node to update its background
                node.data('svg_background', newSvg);
                node.style('background-image', newSvg);
            });
            
            // Force a redraw
            cyRef.current.forceRender();
        }
    }, [selectedNodeId]);

    // This effect runs the layout when the elements are updated.
    useEffect(() => {
        const timer = setTimeout(() => {
            if (cyRef.current) {
                cyRef.current.nodes('.edge-label').remove();
                const layout = cyRef.current.layout(dagreLayout);
                
                layout.one('layoutstop', () => {
                    cyRef.current.edges().forEach(edge => {
                        const label = edge.data('label');
                        if (label && label.trim() !== '') {
                            const mid = edge.midpoint();
                            const isSelfLoop = edge.hasClass('edge-self-loop');
                            const edgeColor = isSelfLoop ? EDGE_COLOR_SELF_LOOP : EDGE_COLOR_SEQUENTIAL;
                            cyRef.current.add({
                                group: 'nodes',
                                data: {
                                    id: `label-for-${edge.id()}`,
                                    label: label,
                                    svg_background: createEdgeLabelSvg(label, edgeColor)
                                },
                                position: { x: mid.x, y: mid.y },
                                classes: 'edge-label',
                                pannable: true,
                            });
                        }
                    });
                });

                layout.run();
                cyRef.current.fit(null, 15); // UPDATED: Reduced fit padding from 30 to 15
            }
        }, 10);
        return () => clearTimeout(timer);
    }, [elements, graphKey]);
    
    if (!elements.length && !graphData) {
        return (
            <div style={getParentContainerStyling()}>
                <div 
                    className="flex items-center justify-center h-full"
                    style={{ 
                        width: '100%', 
                        height: '100%',
                        ...containerStyling
                    }}
                >
                    <p className="text-gray-500">No graph data available.</p>
                </div>
            </div>
        );
    }

    return (
        <div style={getParentContainerStyling()}>
            {isNested && Array.from({length: nestingLevel}, (_, i) => {
                const layerIndex = nestingLevel - i - 1;
                const layerOffset = (layerIndex + 1) * 12;
                const layerOpacity = 0.6 - (layerIndex * 0.15);
                
                return (
                    <div
                        key={`bg-layer-${i}`}
                        style={{
                            position: 'absolute',
                            top: `${layerOffset}px`,
                            left: `${layerOffset}px`,
                            right: `${layerOffset}px`,
                            bottom: `${layerOffset}px`,
                            background: `linear-gradient(145deg, 
                                rgba(248, 250, 252, ${layerOpacity}), 
                                rgba(241, 245, 249, ${layerOpacity * 0.8})
                            )`,
                            borderRadius: `${14 + layerIndex * 2}px`,
                            border: `${2 + layerIndex}px solid rgba(255, 255, 255, ${layerOpacity})`,
                            boxShadow: `
                                0 ${3 + layerIndex * 3}px ${6 + layerIndex * 3}px rgba(0, 0, 0, ${0.08 + layerIndex * 0.03})
                            `,
                            zIndex: -(layerIndex + 1),
                            pointerEvents: 'none',
                            transform: `translateZ(-${(layerIndex + 1) * 5}px)`,
                        }}
                    />
                );
            })}

            <div 
                className="graph-container" 
                ref={graphContainerRef} 
                style={{ 
                    width: '100%', 
                    height: '100%',
                    overflow: 'hidden',
                    ...containerStyling
                }}
                onMouseEnter={(e) => {
                    if (isNested) {
                        const elevationOffset = nestingLevel * 25;
                        const shadowBlur = 10 + (nestingLevel * 15);
                        const shadowSpread = nestingLevel * 4;
                        const scaleEffect = 1 + (nestingLevel * 0.03);
                        
                        e.currentTarget.style.transform = `
                            translateY(-${elevationOffset + 8}px) 
                            translateZ(${nestingLevel * 15 + 8}px)
                            scale(${scaleEffect + 0.02})
                            rotateX(${nestingLevel * 1.5 + 1}deg)
                        `;
                        e.currentTarget.style.boxShadow = `
                            0 ${20 + elevationOffset}px ${shadowBlur + 8}px -3px rgba(0, 0, 0, ${0.25 + nestingLevel * 0.08}),
                            0 ${12 + elevationOffset/2}px ${shadowSpread * 4}px -2px rgba(0, 0, 0, ${0.2 + nestingLevel * 0.05}),
                            0 ${6 + elevationOffset/4}px ${shadowSpread * 3}px -1px rgba(0, 0, 0, ${0.15 + nestingLevel * 0.03}),
                            inset 0 2px 0 rgba(255, 255, 255, 0.4),
                            inset 0 -2px 0 rgba(0, 0, 0, 0.12)
                        `;
                    }
                }}
                onMouseLeave={(e) => {
                    if (isNested) {
                        const elevationOffset = nestingLevel * 25;
                        const shadowBlur = 10 + (nestingLevel * 15);
                        const shadowSpread = nestingLevel * 4;
                        const scaleEffect = 1 + (nestingLevel * 0.03);
                        
                        e.currentTarget.style.transform = `
                            translateY(-${elevationOffset}px) 
                            translateZ(${nestingLevel * 15}px)
                            scale(${scaleEffect})
                            rotateX(${nestingLevel * 1.5}deg)
                        `;
                        e.currentTarget.style.boxShadow = `
                            0 ${15 + elevationOffset}px ${shadowBlur}px -3px rgba(0, 0, 0, ${0.2 + nestingLevel * 0.08}),
                            0 ${8 + elevationOffset/2}px ${shadowSpread * 3}px -2px rgba(0, 0, 0, ${0.15 + nestingLevel * 0.05}),
                            0 ${4 + elevationOffset/4}px ${shadowSpread * 2}px -1px rgba(0, 0, 0, ${0.1 + nestingLevel * 0.03}),
                            inset 0 2px 0 rgba(255, 255, 255, 0.3),
                            inset 0 -2px 0 rgba(0, 0, 0, 0.08)
                        `;
                    }
                }}
            >
                <div 
                    style={{
                        width: '100%',
                        height: '100%',
                        position: 'relative',
                        borderRadius: isNested ? '12px' : '8px',
                        overflow: 'hidden',
                        background: isNested 
                            ? 'linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(248, 250, 252, 0.85))'
                            : '#f9f9f9',
                        backdropFilter: isNested ? 'blur(2px)' : 'none',
                    }}
                >
                    {tooltip.visible && (
                        <CytoscapeTooltip 
                            nodeData={tooltip.data} 
                            position={tooltip.position} 
                        />
                    )}
                    
                    <CytoscapeComponent
                        key={graphKey}
                        elements={elements}
                        stylesheet={[
                            ...stylesheet,
                            ...(isNested ? [{
                                selector: 'core',
                                style: {
                                    'active-bg-color': '#ffffff',
                                    'active-bg-opacity': 0.15,
                                    'selection-box-color': '#3b82f6',
                                    'selection-box-opacity': 0.4,
                                    'selection-box-border-color': '#1d4ed8',
                                    'selection-box-border-width': 2,
                                }
                            }] : [])
                        ]}
                        layout={presetLayout}
                        style={cytoscapeComponentStyle}
                        // UPDATED: Disable selection entirely at the Cytoscape level
                        autolock={false}
                        autoungrabify={false}
                        autounselectify={true}
                        boxSelectionEnabled={false}
                        selectionType='single'
                        cy={(cy) => {
                            cyRef.current = cy;
                            cy.removeAllListeners();

                            // UPDATED: Completely disable all selection behavior
                            cy.autolock(false);
                            cy.autoungrabify(false); 
                            cy.autounselectify(true);
                            cy.boxSelectionEnabled(false);

                            if (!document.getElementById('graph-cursor-styles')) {
                                const styleElement = document.createElement('style');
                                styleElement.id = 'graph-cursor-styles';
                                styleElement.innerHTML = `
                                    .cytoscape-container {
                                        position: relative;
                                        outline: none !important;
                                        border: none !important;
                                    }
                                    .cytoscape-container * {
                                        outline: none !important;
                                        border: none !important;
                                        box-shadow: none !important;
                                    }
                                    .cytoscape-container canvas {
                                        outline: none !important;
                                        border: none !important;
                                    }
                                `;
                                document.head.appendChild(styleElement);
                            }

                            cy.on('tap', 'node', (event) => {
                                const node = event.target;
                                const nodeData = node.data();

                                if (node.hasClass('task-node')) {
                                    const nodeCenterX = node.renderedPosition().x;
                                    const clickX = event.renderedPosition.x;
                                    const relativeClickX = clickX - nodeCenterX;
                                    const splitThreshold = TASK_NODE_SPLIT_WIDTH - (TASK_NODE_WIDTH / 2);
                                    
                                    if (relativeClickX < splitThreshold) {
                                        if (nodeData.nestedGraph) {
                                            onNodeClick(nodeData.id, nodeData.nestedGraph, null);
                                        }
                                    } else {
                                        if (onNodeMetricsClick) {
                                            onNodeMetricsClick(nodeData.id);
                                        }
                                    }
                                } else {
                                    onNodeClick(nodeData.id, nodeData.nestedGraph, null);
                                }
                            });

                            cy.on('mousemove', 'node', (event) => {
                                const node = event.target;
                                const nodeData = node.data();
                                
                                if (node.hasClass('task-node')) {
                                    const nodeCenterX = node.renderedPosition().x;
                                    const mouseX = event.renderedPosition.x;
                                    const relativeClickX = mouseX - nodeCenterX;
                                    const splitThreshold = TASK_NODE_SPLIT_WIDTH - (TASK_NODE_WIDTH / 2);
                                    
                                    if (relativeClickX < splitThreshold && nodeData.nestedGraph) {
                                        cy.container().style.cursor = 'pointer';
                                    } else {
                                        cy.container().style.cursor = 'default';
                                    }
                                }
                            });

                            cy.on('mouseover', 'node', (event) => {
                                onNodeHover(event.target.data().id);
                                setTooltip({ visible: true, data: event.target.data(), position: event.renderedPosition });
                            });

                            cy.on('mouseout', 'node', () => {
                                cy.container().style.cursor = 'default';
                                onNodeHover(null);
                                setTooltip({ visible: false, data: null, position: null });
                            });
                            
                            cy.on('mouseover', 'edge', (event) => {
                                event.target.addClass('hover');
                                const labelNode = cy.getElementById(`label-for-${event.target.id()}`);
                                if (labelNode.length > 0) {
                                    const isSelfLoop = event.target.hasClass('edge-self-loop');
                                    const hoverColor = isSelfLoop ? EDGE_COLOR_HOVER_SELF_LOOP : EDGE_COLOR_HOVER_SEQUENTIAL;
                                    labelNode.data('svg_background', createEdgeLabelSvg(labelNode.data('label'), hoverColor));
                                }
                            });

                            cy.on('mouseout', 'edge', (event) => {
                                event.target.removeClass('hover');
                                const labelNode = cy.getElementById(`label-for-${event.target.id()}`);
                                if (labelNode.length > 0) {
                                    const isSelfLoop = event.target.hasClass('edge-self-loop');
                                    const originalColor = isSelfLoop ? EDGE_COLOR_SELF_LOOP : EDGE_COLOR_SEQUENTIAL;
                                    labelNode.data('svg_background', createEdgeLabelSvg(labelNode.data('label'), originalColor));
                                }
                            });

                            cy.on('pan zoom drag', () => {
                                setTooltip({ visible: false, data: null, position: null });
                                cy.nodes('.edge-label').forEach(labelNode => {
                                    const edgeId = labelNode.id().replace('label-for-', '');
                                    const edge = cy.getElementById(edgeId);
                                    if (edge.length > 0) {
                                        labelNode.position(edge.midpoint());
                                    }
                                });
                            });
                        }}
                        minZoom={0.2}
                        maxZoom={2.0}
                    />
                </div>
            </div>
        </div>
    );
};

export default GraphVisualizer;