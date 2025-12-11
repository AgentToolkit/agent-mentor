export const SettingsModal = ({
  setShowSettings,
  serverUrl,
  setServerUrl,
  tenantId,
  setTenantId,
  serviceName,
  setServiceName,
  hideTaskPrefixes,
  setHideTaskPrefixes,
}) => {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50">
      <div className="bg-white p-6 w-96">
        <h3 className="text-lg font-medium mb-4">Settings</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Server URL</label>
            <input
              type="text"
              value={serverUrl}
              onChange={(e) => setServerUrl(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Tenant ID</label>
            <input
              type="text"
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          <div>
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={hideTaskPrefixes}
                onChange={(e) => setHideTaskPrefixes(e.target.checked)}
                className="form-checkbox h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <span className="text-sm font-medium text-gray-700">Hide task prefix</span>
            </label>
            <p className="text-xs text-gray-500 mt-1">Hide the numeric prefix (e.g., "0.0.1:") from task names</p>
          </div>

          {/* <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Instana Server URL
                </label>
                <input
                  type="text"
                  value={serviceName}
                  onChange={(e) => setServiceName(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                />
              </div> */}
          {/* <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Instana Service Name
                </label>
                <input
                  type="text"
                  value={serviceName}
                  onChange={(e) => setServiceName(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                />
              </div> */}
        </div>
        <div className="mt-6 flex justify-end space-x-3">
          <button
            onClick={() => setShowSettings(false)}
            className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
          >
            Cancel
          </button>
          <button
            onClick={() => {
              setShowSettings(false);
            }}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
};
