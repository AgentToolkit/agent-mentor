import { useState } from "react";
import { useAuth } from "../AuthComponents";
import { SettingsModal } from "../SettingsModal";
import { AdminModal } from "../AdminModal";
import { Menu, Settings, Users } from "lucide-react";

export const Navigation = ({
  serverUrl,
  setServerUrl,
  tenantId,
  setTenantId,
  serviceName,
  setServiceName,
  onDataReceived,
  error,
  setError,
  isEmbedded,
  setIsModalOpen,
  saveHideTaskPrefixes,
}) => {
  const { user, logout } = useAuth();
  const [showSettings, setShowSettings] = useState(false);
  const [showAdmin, setShowAdmin] = useState(false);

  return (
    <div className="flex flex-col">
      {/* Header */}
      <div className="bg-white shadow">
        <div className="max-w-9xl mx-auto px-4">
          <div className="flex justify-between h-8">
            <div className="flex items-center">
              <button onClick={() => setIsModalOpen(true)} className="p-2 hover:bg-gray-100 rounded-full">
                <Menu className="w-6 h-6" />
              </button>

              <h1 className="text-xl pl-2 font-bold text-gray-900">
                Agent Analytics <span className="text-sm pl-4 font-semibold text-gray-700">v0.17.1 (alpha)</span>
              </h1>
            </div>

            {user && (
              <div className="flex items-center">
                <span className="text-gray-500 mr-4">Welcome, {user.full_name}!</span>
                <button
                  onClick={logout}
                  className="border-blue-500 px-4 py-2 text-blue-600 hover:bg-gray-100 text-sm font-medium"
                >
                  Logout
                </button>
                <button
                  onClick={() => setShowSettings(true)}
                  className="p-2 bg-white border-blue-500 text-blue-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  <Settings className="w-4 h-4" />
                </button>
                {(user?.username === "roy" || user?.username === "dany") && (
                  <button
                    onClick={() => setShowAdmin(true)}
                    className="p-2 bg-white border-blue-500 text-blue-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 mr-12"
                  >
                    <Users className="w-4 h-4" />
                  </button>
                )}
                {/* Add spacing for the top collapse button */}
                {!(user?.username === "roy" || user?.username === "dany") && <div className="w-12"></div>}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Settings Modal */}
      {showSettings && (
        <SettingsModal
          setShowSettings={setShowSettings}
          serverUrl={serverUrl}
          setServerUrl={setServerUrl}
          tenantId={tenantId}
          setTenantId={setTenantId}
          serviceName={serviceName}
          setServiceName={setServiceName}
          setHideTaskPrefixes={saveHideTaskPrefixes}
        />
      )}
      {showAdmin && <AdminModal setShowAdmin={setShowAdmin} serverUrl={serverUrl} />}
    </div>
  );
};
