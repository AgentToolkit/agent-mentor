import { useState, useEffect } from 'react';
import { storage } from '../AuthComponents';

export const usePanelState = (panelConfig) => {
  const [isTopCollapsed, setIsTopCollapsed] = useState(false);
  const [isSidePanelCollapsed, setIsSidePanelCollapsed] = useState(false);
  const [sidePanelWidth, setSidePanelWidth] = useState(() => {
    if (panelConfig.sidePanel.persistState) {
      return parseInt(storage.getItem('sidePanelWidth')) || panelConfig.sidePanel.defaultWidth;
    }
    return panelConfig.sidePanel.defaultWidth;
  });

  // Save panel width to storage if persistence is enabled
  useEffect(() => {
    if (panelConfig.sidePanel.persistState) {
      storage.setItem('sidePanelWidth', sidePanelWidth.toString());
    }
  }, [sidePanelWidth, panelConfig.sidePanel.persistState]);

  // Panel toggle handlers
  const handleToggleTopCollapse = () => {
    setIsTopCollapsed(!isTopCollapsed);
  };

  const handleToggleSidePanelCollapse = () => {
    setIsSidePanelCollapsed(!isSidePanelCollapsed);
  };

  const handleSidePanelWidthChange = (newWidth) => {
    setSidePanelWidth(newWidth);
  };

  return {
    isTopCollapsed,
    isSidePanelCollapsed,
    sidePanelWidth,
    handleToggleTopCollapse,
    handleToggleSidePanelCollapse,
    handleSidePanelWidthChange,
  };
};
