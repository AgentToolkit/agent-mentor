// Constants for graph visualization

// Color scheme based on the reference image
export const carbonColors = {
    background: '#ffffff',
    tileBg: '#f4f4f4',
    tileBorder: '#e0e0e0',
    tileHover: '#e5e5e5',
    text: '#000000', // White text for better contrast on blue backgrounds
    textSecondary: '#000000',
    link: '#0f62fe',
    edge: '#8d8d8d',
    edgeLabel: '#ffffff',
    edgeLabelBg: '#525252',
    nodeHeader: '#0f62fe',
    nestedIcon: '#0f62fe',
    breadcrumbBg: '#f4f4f4',
    hitsBg: '#000000', // Black background for hits counter
    nodeHighHits: '#0a3d91', // Dark blue for nodes with high hit count
    nodeMediumHits: '#2979ff', // Medium blue for nodes with medium hit count
    nodeLowHits: '#90caf9', // Light blue for nodes with low hit count
    edgeHighHits: '#0a3d91', // Dark blue for edges with high hit count
    edgeMediumHits: '#2979ff', // Medium blue for edges with medium hit count
    edgeLowHits: '#90caf9', // Light blue for edges with low hit count
  };


export const EDGE_COLOR_SEQUENTIAL = '#6B7280';
export const EDGE_COLOR_SELF_LOOP = '#6366F1';
export const EDGE_COLOR_HOVER_SEQUENTIAL = '#3B82F6';
export const EDGE_COLOR_HOVER_SELF_LOOP = '#4338CA';

export const stylesheet = [
    {
        selector: 'node:parent',
        style: {
            'font-family': 'Helvetica, Arial, sans-serif',
            'background-opacity': 0.05,
            'background-color': '#F8F9FA',
            'border-width': 2,
            'border-color': '#9CA3AF',
            'border-style': 'dashed',
            'padding': '15px',
            'label': 'data(label)', 'font-size': 14, 'font-weight': 'bold', 'color': '#374151',
            'text-valign': 'top', 'text-halign': 'center',
        }
    },
    {
        selector: '.task-node',
        style: {
            'shape': 'rectangle', 'width': 180, 'height': 60,
            'background-image': 'data(svg_background)',
            'background-fit': 'none', 'background-color': 'transparent',
            'background-opacity': 0, 'border-width': 0,
        }
    },
    {
        selector: '.start-node, .end-node',
        style: {
            'font-family': 'Helvetica, Arial, sans-serif', 'shape': 'ellipse',
            'background-color': '#000000', 'border-width': 3, 'border-color': '#333333',
            'width': 50, 'height': 50, 'color': 'white', 'font-size': 10, 'font-weight': 'bold',
            'text-valign': 'center', 'text-halign': 'center', 'label': 'data(label)',
        }
    },
    {
        selector: '.gateway-xor, .gateway-and, .gateway-or',
        style: {
            'font-family': 'Helvetica, Arial, sans-serif', 'shape': 'diamond',
            'width': 50, 'height': 50, 'color': 'white', 'font-size': 10, 'font-weight': 'bold',
            'text-valign': 'center', 'text-halign': 'center', 'label': 'data(label)',
        }
    },
    { selector: '.gateway-xor', style: { 'background-color': '#3B82F6', 'border-color': '#1D4ED8' } },
    { selector: '.gateway-and', style: { 'background-color': '#60A5FA', 'border-color': '#2563EB' } },
    { selector: '.gateway-or', style: { 'background-color': '#93C5FD', 'border-color': '#3B82F6' } },
    {
        selector: 'node:selected',
        style: {
            'outline-color': '#0f62fe', 'outline-width': 4, 'outline-offset': 2,
        }
    },
    {
        selector: 'edge',
        style: {
            'transition-property': 'line-color, target-arrow-color, width',
            'transition-duration': '0.2s',
            'transition-timing-function': 'ease-in-out',
        }
    },
    {
        selector: '.edge-label',
        style: {
            'shape': 'rectangle',
            'background-image': 'data(svg_background)',
            'background-fit': 'none',
            'background-color': 'transparent',
            'background-opacity': 0,
            'border-width': 0,
            'width': 24,
            'height': 24,
            'events': 'no',
        }
    },
    {
        selector: '.edge-sequential',
        style: {
            'width': 2.5,
            'line-color': EDGE_COLOR_SEQUENTIAL,
            'target-arrow-color': EDGE_COLOR_SEQUENTIAL,
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
        }
    },
    {
        selector: '.edge-self-loop',
        style: {
            'width': 2,
            'line-color': EDGE_COLOR_SELF_LOOP,
            'target-arrow-color': EDGE_COLOR_SELF_LOOP,
            'target-arrow-shape': 'triangle',
            'curve-style': 'unbundled-bezier',
            'control-point-distances': [40, 40],
            'control-point-weights': [0.25, 0.75],
            'loop-direction': '30deg',
            'loop-sweep': '30deg',
        }
    },
    {
        selector: 'edge.hover',
        style: {
            'width': 4,
            'line-color': EDGE_COLOR_HOVER_SEQUENTIAL,
            'target-arrow-color': EDGE_COLOR_HOVER_SEQUENTIAL,
        }
    },
    {
        selector: '.edge-self-loop.hover',
        style: {
            'line-color': EDGE_COLOR_HOVER_SELF_LOOP,
            'target-arrow-color': EDGE_COLOR_HOVER_SELF_LOOP,
        }
    }
];

  
  // Node dimensions
  export const nodeWidth = 260;
  export const nodeHeight = 75;
  
  // Node spacing
  export const nodeSpacingX = nodeWidth + 100; // Horizontal spacing
  export const nodeSpacingY = nodeHeight + 100; // Vertical spacing
  
  // Hit count scaling
  export const maxHitCount = 500; // Maximum hit count for color scaling
  export const minHitCount = 1; // Minimum hit count
  
  // Helper functions
  export const truncateText = (text, maxLength) => {
    if (!text) return '';
    return text.length <= maxLength ? text : text.substring(0, maxLength - 3) + '...';
  };
  
  // Function to determine node color based on hit count
  export const getNodeColorByHits = (hits) => {
    // Normalize hit count between 0 and 1
    const normalizedHits = Math.min(hits, maxHitCount) / maxHitCount;
    
    if (normalizedHits >= 0.7) {
      return carbonColors.nodeHighHits;
    } else if (normalizedHits >= 0.3) {
      return carbonColors.nodeMediumHits;
    } else {
      return carbonColors.nodeLowHits;
    }
  };
  
  // Function to determine edge color based on hit count
  export const getEdgeColorByHits = (hits) => {
    // Normalize hit count between 0 and 1
    const normalizedHits = Math.min(hits, maxHitCount) / maxHitCount;
    
    if (normalizedHits >= 0.7) {
      return carbonColors.edgeHighHits;
    } else if (normalizedHits >= 0.3) {
      return carbonColors.edgeMediumHits;
    } else {
      return carbonColors.edgeLowHits;
    }
  };