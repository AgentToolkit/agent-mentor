import { useState } from 'react';

const Base64ImageViewer = ({ imageData, alt = 'Image', initialMaxWidth = 200, initialMaxHeight = 150 }) => {
  // Track expanded state
  const [isExpanded, setIsExpanded] = useState(false);

  // Generate a unique ID for the image
  const imageId = `img-${Math.random().toString(36).substring(2, 9)}`;

  // Toggle expand/collapse
  const toggleImage = () => {
    setIsExpanded(!isExpanded);
  };

  // Calculate image styling based on expanded state
  const imageStyle = {
    maxWidth: isExpanded ? '100%' : `${initialMaxWidth}px`,
    maxHeight: isExpanded ? 'none' : `${initialMaxHeight}px`,
    cursor: 'pointer',
    transition: 'all 0.3s ease',
    objectFit: 'contain',
  };

  // Ensure the imageData has the correct prefix if needed
  const imageSource = imageData.startsWith('data:image/') ? imageData : `data:image/png;base64,${imageData}`;

  return (
    <div className="collapsible-image-container">
      <img src={imageSource} alt={alt} style={imageStyle} onClick={toggleImage} id={imageId} />
      <div className="image-expand-hint" style={{ fontSize: '0.8rem', color: '#666' }}>
        {isExpanded ? 'Click to collapse' : 'Click to expand'}
      </div>
    </div>
  );
};

export default Base64ImageViewer;
