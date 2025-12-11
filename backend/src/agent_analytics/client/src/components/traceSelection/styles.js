// Animation styles for the filter panel
export const setupAnimationStyles = () => {
    const style = document.createElement('style');
    style.innerHTML = `
      @keyframes slideInFromLeft {
        0% { transform: translateX(-100%); }
        100% { transform: translateX(0); }
      }
      @keyframes slideOutToLeft {
        0% { transform: translateX(0); }
        100% { transform: translateX(-100%); }
      }
      @keyframes slideContentRight {
        0% { margin-left: 0; }
        100% { margin-left: 320px; }
      }
      @keyframes slideContentLeft {
        0% { margin-left: 320px; }
        100% { margin-left: 0; }
      }
      .filter-slide-in {
        animation: slideInFromLeft 0.3s cubic-bezier(0, 0, 0.38, 0.9) forwards;
      }
      .filter-slide-out {
        animation: slideOutToLeft 0.2s cubic-bezier(0.2, 0, 1, 0.9) forwards;
      }
      .content-slide-right {
        animation: slideContentRight 0.3s cubic-bezier(0, 0, 0.38, 0.9) forwards;
      }
      .content-slide-left {
        animation: slideContentLeft 0.2s cubic-bezier(0.2, 0, 1, 0.9) forwards;
      }
    `;
    document.head.appendChild(style);
    
    return () => {
      document.head.removeChild(style);
    };
  };