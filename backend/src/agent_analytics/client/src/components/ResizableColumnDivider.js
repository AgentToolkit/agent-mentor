import React, { useState, useEffect } from 'react';

/**
 * A draggable divider component that allows resizing columns
 */
const ResizableColumnDivider = ({ initialWidth, minWidth, maxWidth, onWidthChange }) => {
  const [isDragging, setIsDragging] = useState(false);

  // Start dragging
  const handleMouseDown = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  useEffect(() => {
    // Handle mouse move when dragging
    const handleMouseMove = (e) => {
      if (!isDragging) return;

      // Calculate new width based on mouse position
      const newWidth = e.clientX;

      // Constrain width between min and max
      const constrainedWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));

      // Notify parent component of width change
      onWidthChange(constrainedWidth);
    };

    // End dragging on mouse up
    const handleMouseUp = () => {
      setIsDragging(false);
    };

    // Add event listeners when dragging starts
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    // Clean up event listeners
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, minWidth, maxWidth, onWidthChange]);

  return (
    <div
      className={`absolute cursor-col-resize border-r border-gray-300 hover:border-blue-500 ${
        isDragging ? 'border-blue-500 bg-blue-100' : ''
      }`}
      style={{
        right: 0,
        top: 0,
        bottom: 0,
        width: '6px',
        zIndex: 20,
        transition: isDragging ? 'none' : 'background-color 0.15s ease',
      }}
      onMouseDown={handleMouseDown}
    />
  );
};

export default ResizableColumnDivider;
