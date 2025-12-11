CARBON_THEME_CSS = """
    /* Carbon Design System Color Overrides for Jaeger */
    
    /* Main background and text colors - targeting actual Jaeger classes */
    body, 
    .ant-layout,
    .Page--content,
    .TracePage,
    .TracePageHeader,
    .TraceDiffHeader,
    .SearchPage {
        background-color: #f4f4f4 !important; /* Gray 10 */
        color: #161616 !important; /* Gray 100 */
    }
    
    /* Header and navigation - minimal styling, keep original look */
    .TracePageHeader,
    .TracePageHeader--titleRow,
    .TracePage--headerSection,
    .Tracepage--headerSection {
        background-color: #ffffff !important; /* White */
        border-bottom: 1px solid #e0e0e0 !important; /* Gray 30 */
    }
    
    /* Timeline and main viewing areas */
    .TraceTimelineViewer,
    .VirtualizedTraceView,
    .VirtualizedTraceView--spans,
    .TimelineHeaderRow {
        background-color: #ffffff !important; /* White */
    }
    
    /* Span bars - using Carbon blue palette */
    .SpanBar--bar {
        background: #0f62fe !important; /* Blue 60 */
    }
    
    .SpanBar--bar:hover {
        background: #0043ce !important; /* Blue 70 */
    }
    
    /* Left pane service name color bars */
    .span-name {
        border-color: #0f62fe !important; /* Blue 60 - matches the span bars */
    }
    
    /* Critical path bars - make them more visible with bright gray */
    .SpanBar--criticalPath {
        background: #c6c6c6 !important; /* Gray 40 - much more visible than black */
    }
    
    /* Expanded row styling - targeting elements with inline styles */
    .detail-row,
    .detail-row-expanded-accent {
        background-color: #ffffff !important; /* White */
        color: #1677ff9c !important;
        border-top: 1px solid #e0e0e0 !important; /* Gray 30 */
    }
    
    .detail-info-wrapper {
        background-color: #f4f4f4 !important; /* Gray 10 */
        color: #0833a9f0 !important; /* Gray 100 */
        padding: 16px !important;
    }
    
    /* Key-Value table styling */
    .KeyValueTable--valueColumn {
        background-color: #ffffff !important; /* White */
        color: #0958d9 !important; /* Gray 100 */
    }
    
    .KeyValueTable--keyColumn {
        background-color: #f5f5f5 !important; 
        color: rgba(0, 0, 0, 0.88) !important; 
    }    
    
    /* JSON markup styling */
    .json-markup-string {
        color: #0958d9 !important; 
    }
    
    .json-markup-key {
        color: rgba(0, 0, 0, 0.88) !important;
    }
    
    .json-markup-number {
        color: #fa4d56 !important; 
    }
    
    .json-markup-bool {
        color: #8a3ffc !important; /* Purple 60 - for booleans */
    }
    
    /* Different services get different Carbon colors */
    .span-name[style*="border-color: rgb(23, 184, 190)"] ~ * .SpanBar--bar,
    .span-name[style*="23, 184, 190"] ~ * .SpanBar--bar {
        background: #0f62fe !important; /* Blue 60 */
    }
    
    /* Service differentiation - you can add more specific service targeting here */
    .span-svc-name:contains("service-1") ~ * .SpanBar--bar {
        background: #0f62fe !important; /* Blue 60 */
    }
    
    .span-svc-name:contains("service-2") ~ * .SpanBar--bar {
        background: #198038 !important; /* Green 60 */
    }
    
    .span-svc-name:contains("service-3") ~ * .SpanBar--bar {
        background: #fa4d56 !important; /* Red 50 */
    }
    
    .span-svc-name:contains("service-4") ~ * .SpanBar--bar {
        background: #f1c21b !important; /* Yellow 30 */
    }
    
    .span-svc-name:contains("service-5") ~ * .SpanBar--bar {
        background: #8a3ffc !important; /* Purple 60 */
    }
    
    /* Collapse/Expand buttons in left pane - all buttons styled consistently */
    .TimelineCollapser svg,
    .TimelineCollapser--btn,
    .TimelineCollapser--btn-expand,
    .TimelineCollapser--btn-size {
        color: #0f62fe !important; /* Blue 60 */
        cursor: pointer !important;
        transition: color 0.2s ease !important;
    }
    
    .TimelineCollapser svg:hover,
    .TimelineCollapser--btn:hover,
    .TimelineCollapser--btn-expand:hover,
    .TimelineCollapser--btn-size:hover {
        color: #0043ce !important; /* Blue 70 */
    }
    
    .TimelineCollapser {
        background-color: transparent !important;
        border: none !important;
        padding: 4px !important;
    }
    
    /* Tables */
    .ant-table,
    .KeyValuesTable,
    .TraceSpanView--table {
        background-color: #ffffff !important;
        border: 1px solid #e0e0e0 !important; /* Gray 30 */
    }
    
    .ant-table-thead > tr > th,
    .KeyValuesTable--header {
        background-color: #f4f4f4 !important; /* Gray 10 */
        border-bottom: 1px solid #e0e0e0 !important; /* Gray 30 */
        color: #161616 !important; /* Gray 100 */
    }
    
    .ant-table-tbody > tr:hover > td {
        background-color: #e8f4fd !important; /* Blue 10 */
    }
    
    /* Keep original form input styling */
    
    /* Timeline and spans */
    .TimelineHeaderRow,
    .TimelineCollapser {
        background-color: #f4f4f4 !important; /* Gray 10 */
        border-bottom: 1px solid #e0e0e0 !important; /* Gray 30 */
    }
    
    /* Service badges */
    .SpanTreeOffset--indentGuide {
        border-left: 1px solid #e0e0e0 !important; /* Gray 30 */
    }
    
    /* Dropdown menus */
    .ant-dropdown-menu,
    .ant-select-dropdown {
        background-color: #ffffff !important;
        border: 1px solid #e0e0e0 !important; /* Gray 30 */
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15) !important;
    }
    
    .ant-dropdown-menu-item:hover,
    .ant-select-item-option:hover {
        background-color: #e8f4fd !important; /* Blue 10 */
    }
    
    /* Loading and progress indicators */
    .ant-spin-dot-item {
        background-color: #0f62fe !important; /* Blue 60 */
    }
    
    .ant-progress-bg {
        background-color: #0f62fe !important; /* Blue 60 */
    }
    
    /* Error states */
    .ant-alert-error {
        background-color: #fff1f1 !important; /* Red 10 */
        border-color: #fa4d56 !important; /* Red 50 */
    }
    
    /* Success states */
    .ant-alert-success {
        background-color: #defbe6 !important; /* Green 10 */
        border-color: #198038 !important; /* Green 60 */
    }
    
    /* Info states */
    .ant-alert-info {
        background-color: #e8f4fd !important; /* Blue 10 */
        border-color: #0f62fe !important; /* Blue 60 */
    }
    
    /* Scrollbars (Webkit) */
    ::-webkit-scrollbar {
        width: 12px;
        height: 12px;
    }
    
    ::-webkit-scrollbar-track {
        background-color: #f4f4f4 !important; /* Gray 10 */
    }
    
    ::-webkit-scrollbar-thumb {
        background-color: #c6c6c6 !important; /* Gray 40 */
        border-radius: 6px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background-color: #a8a8a8 !important; /* Gray 50 */
    }
    """
    
CARBON_THEME_JS = """
    document.addEventListener('DOMContentLoaded', function() {
        // Remove inline styles that interfere with Carbon theming
        function removeInlineStyles() {
            const elements = document.querySelectorAll('.detail-row, .detail-row-expanded-accent, .detail-info-wrapper');
            elements.forEach(el => {
                el.style.removeProperty('border-color');
                el.style.removeProperty('border-top-color');
            });
        }
        
        // Run initially
        removeInlineStyles();
        
        // Re-run when new elements are added (for dynamically expanded rows)
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                mutation.addedNodes.forEach(function(node) {
                    if (node.nodeType === 1) { // Element node
                        const detailElements = node.querySelectorAll ? 
                            node.querySelectorAll('.detail-row, .detail-row-expanded-accent, .detail-info-wrapper') : [];
                        detailElements.forEach(el => {
                            el.style.removeProperty('border-color');
                            el.style.removeProperty('border-top-color');
                        });
                    }
                });
            });
        });
        observer.observe(document.body, { childList: true, subtree: true });
    });    
    """