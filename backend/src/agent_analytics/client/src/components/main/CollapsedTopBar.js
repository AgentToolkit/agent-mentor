import { PanelTopOpen } from 'lucide-react';
import { DEFAULT_PANEL_CONFIG } from '../constants/panelConfig';

export const CollapsedTopBar = ({
  traceId,
  serviceName,
  selectedGroup,
  onExpand,
  analyticsType,
  config = DEFAULT_PANEL_CONFIG.topPanel,
}) => {
  const formatTraceId = (traceId) => {
    if (!traceId) return '';
    return traceId.length > 8 ? `${traceId.substring(0, 6)}...` : traceId;
  };

  const displayInfo = () => {
    if (!config.showMinimalInfo) return 'Hidden';

    if (selectedGroup) {
      const groupName =
        selectedGroup.name?.length > 12 ? `${selectedGroup.name.substring(0, 12)}...` : selectedGroup.name || 'Group';

      if (analyticsType === 'group') {
        return `Group: ${groupName}`;
      } else {
        return `${groupName} > ${formatTraceId(traceId)}`;
      }
    }
    return formatTraceId(traceId) || 'No selection';
  };

  return (
    <div className="bg-white shadow-sm border-b border-gray-200 px-2 py-1 flex items-center justify-between transition-all duration-300">
      <div className="flex items-center space-x-4">
        <span className="text-sm font-medium text-gray-700">{displayInfo()}</span>
        {serviceName && config.showMinimalInfo && (
          <span className="text-xs text-gray-500">
            {serviceName.length > 20 ? `${serviceName.substring(0, 20)}...` : serviceName}
          </span>
        )}
      </div>
      <button
        onClick={onExpand}
        className="p-1 bg-blue-50 hover:bg-blue-100 rounded text-blue-600 hover:text-blue-700 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 border border-blue-200"
        title="Expand top panels"
      >
        <PanelTopOpen className="w-4 h-4" />
      </button>
    </div>
  );
};
