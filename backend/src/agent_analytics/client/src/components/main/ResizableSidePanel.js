import { useState, useRef, useEffect } from 'react';
import { PanelRightClose, PanelRightOpen } from 'lucide-react';
import { DEFAULT_PANEL_CONFIG } from '../constants/panelConfig';

export const ResizableSidePanel = ({
  children,
  isCollapsed,
  width,
  onWidthChange,
  onToggleCollapse,
  config = DEFAULT_PANEL_CONFIG.sidePanel,
}) => {
  const [isResizing, setIsResizing] = useState(false);
  const [displayWidth, setDisplayWidth] = useState(width); // For immediate visual feedback
  const panelRef = useRef(null);
  const rafRef = useRef(null);

  const handleMouseDown = (e) => {
    setIsResizing(true);
    e.preventDefault();
  };

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isResizing) return;

      // Cancel previous RAF if it exists
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
      }

      // Use RAF for smooth visual updates
      rafRef.current = requestAnimationFrame(() => {
        const newWidth = window.innerWidth - e.clientX;
        const clampedWidth = Math.max(config.minWidth, Math.min(config.maxWidth, newWidth));

        // Update visual width immediately via direct DOM manipulation
        if (panelRef.current) {
          panelRef.current.style.width = `${clampedWidth}px`;
        }

        // Update display state for immediate feedback
        setDisplayWidth(clampedWidth);
      });
    };

    // Throttled callback to update parent state (less frequent)
    let lastUpdate = 0;
    const throttledUpdate = (e) => {
      const now = Date.now();
      if (now - lastUpdate > 16) {
        // ~60fps throttling
        const newWidth = window.innerWidth - e.clientX;
        const clampedWidth = Math.max(config.minWidth, Math.min(config.maxWidth, newWidth));
        onWidthChange(clampedWidth);
        lastUpdate = now;
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);

      // Final update to parent state
      if (displayWidth !== width) {
        onWidthChange(displayWidth);
      }

      // Clean up RAF
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mousemove', throttledUpdate);
      document.addEventListener('mouseup', handleMouseUp);
      // Prevent text selection during resize
      document.body.style.userSelect = 'none';
      document.body.style.cursor = 'col-resize';
    } else {
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mousemove', throttledUpdate);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';

      // Clean up RAF on unmount
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, [isResizing, onWidthChange, config.minWidth, config.maxWidth, displayWidth, width]);

  // Sync displayWidth with prop width when not resizing
  useEffect(() => {
    if (!isResizing) {
      setDisplayWidth(width);
    }
  }, [width, isResizing]);

  if (isCollapsed) {
    return (
      <div className="w-8 bg-white border-l border-gray-200 flex flex-col shadow-sm transition-all duration-300">
        {/* Button stays at top when collapsed */}
        <div className="pt-2 flex justify-center">
          <button
            onClick={onToggleCollapse}
            className="p-1 bg-blue-50 hover:bg-blue-100 rounded text-blue-600 hover:text-blue-700 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 border border-blue-200"
            title="Expand side panel"
          >
            <PanelRightOpen className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={panelRef}
      className="relative bg-white border-l border-gray-200 shadow-sm transition-all duration-300"
      style={{ width: `${displayWidth}px` }}
    >
      {/* Resize handle - Pure Tailwind */}
      <div
        className={`absolute left-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-blue-500 hover:w-1.5 transition-all duration-150 z-20 ${
          isResizing ? 'bg-blue-600 w-1.5' : 'bg-transparent'
        }`}
        onMouseDown={handleMouseDown}
        title="Drag to resize"
      />

      {/* Collapse button and vertical line */}
      <div className="absolute left-[2px] top-1 z-10">
        <button
          onClick={onToggleCollapse}
          className="p-1 bg-blue-50 hover:bg-blue-100 rounded text-blue-600 hover:text-blue-700 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 border border-blue-200"
          title="Collapse side panel"
        >
          <PanelRightClose className="w-4 h-4" />
        </button>

        {/* Vertical line extending down from button - matches collapsed panel width */}
        <div
          className="absolute left-7 transform -translate-x-1/2 top-0.5 w-0.5 bg-blue-200 opacity-60"
          style={{ height: 'calc(100vh - 120px)' }}
        />
      </div>

      {/* Content */}
      <div className="h-full overflow-auto pl-9 pt-8">{children}</div>
    </div>
  );
};
