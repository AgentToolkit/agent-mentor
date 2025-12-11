import React, { useEffect, useState } from "react";
import {
  ChevronDown,
  FileText,
  FolderKanban,
  ChevronLeft,
  ChevronRight,
  CheckCircle,
  Loader,
  XCircle,
  Clock,
  Ban,
} from "lucide-react";
import TraceSelectionModal from "./traceSelection/TraceSelectionModal";
import { ANALYTICS_STATUS } from "./traceSelection/modalConstants";
import { updateUrlParams } from "./utils/urlUtils";

const TopBar = ({
  traceId,
  timestamp,
  serviceName,
  setServiceName,
  serverUrl,
  onTraceSelect,
  onTraceNavigation,
  isModalOpen,
  setIsModalOpen,
  handleJsonUpload,
  selectedGroup,
  currentTraceIndex,
  totalTraces,
  analyticsType, // 'group' or 'trace'
  analysisStatus = {}, // New prop for analysis status
  extensionsEnabled,
}) => {
  const [basicStatus, setBasicStatus] = useState(null);
  const [advancedStatus, setAdvancedStatus] = useState(null);

  // Helper to shorten the trace ID or display group name
  const formatTraceId = (traceId) => {
    if (!traceId) return "";
    return traceId.length > 10 ? `${traceId.substring(0, 8)}...${traceId.substring(traceId.length - 4)}` : traceId;
  };

  // Helper to shorten group name
  const formatGroupName = (name) => {
    if (!name) return "Selected Group";
    return name.length > 15 ? `${name.substring(0, 15)}...` : name;
  };

  // Helper to shorten service name
  const formatServiceName = (name) => {
    if (!name) return "";
    return name.length > 25 ? `${name.substring(0, 25)}...` : name;
  };

  const displayHeader = () => {
    if (selectedGroup) {
      return formatGroupName(selectedGroup.name);
    } else if (!traceId) {
      return "No trace selected";
    } else {
      return formatTraceId(traceId);
    }
  };

  const handleOpenModal = () => {
    // Save current serviceName in URL when opening modal
    if (serviceName) {
      updateUrlParams({
        serviceName,
        traceId: null,
        groupId: null,
        tabName: null,
      });
    }
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
  };

  const handlePreviousTrace = () => {
    if (onTraceNavigation && currentTraceIndex > 0) {
      onTraceNavigation(currentTraceIndex - 1);
    }
  };

  const handleNextTrace = () => {
    if (onTraceNavigation && currentTraceIndex < totalTraces - 1) {
      onTraceNavigation(currentTraceIndex + 1);
    }
  };

  // Helper function to get status color and icon for basic analysis
  const getBasicStatusInfo = () => {
    const status = analysisStatus.basic || "pending";

    switch (status) {
      case ANALYTICS_STATUS.COMPLETED:
        return {
          color: "bg-green-100 text-green-700",
          icon: <CheckCircle className="w-3 h-3 mr-1" />,
          text: "Complete",
        };
      case ANALYTICS_STATUS.FAILED:
        return {
          color: "bg-red-100 text-red-700",
          icon: <XCircle className="w-3 h-3 mr-1" />,
          text: "Failed",
        };
      case ANALYTICS_STATUS.EMPTY:
        return {
          color: "bg-black-100 text-black-700",
          icon: <Ban className="w-3 h-3 mr-1" />,
          text: "Empty",
        };
      default:
        return {
          color: "bg-gray-100 text-gray-700",
          icon: <Clock className="w-3 h-3 mr-1" />,
          text: "Pending",
        };
    }
  };

  // Helper function to get status color and icon for advanced analysis
  const getAdvancedStatusInfo = () => {
    const status = analysisStatus.advanced || ANALYTICS_STATUS.NOT_STARTED;

    switch (status) {
      case ANALYTICS_STATUS.COMPLETED:
        return {
          color: "bg-green-100 text-green-700",
          icon: <CheckCircle className="w-3 h-3 mr-1" />,
          text: "Completed",
        };
      case ANALYTICS_STATUS.RUNNING:
        return {
          color: "bg-blue-100 text-blue-700",
          icon: <Loader className="w-3 h-3 mr-1 animate-spin" />,
          text: "Running",
        };
      case ANALYTICS_STATUS.FAILED:
        return {
          color: "bg-red-100 text-red-700",
          icon: <XCircle className="w-3 h-3 mr-1" />,
          text: "Failed",
        };
      case ANALYTICS_STATUS.EMPTY:
        return {
          color: "bg-black-100 text-black-700",
          icon: <Ban className="w-3 h-3 mr-1" />,
          text: "Empty",
        };
      default:
        return {
          color: "bg-gray-100 text-gray-700",
          icon: <Clock className="w-3 h-3 mr-1" />,
          text: "Not Started",
        };
    }
  };

  useEffect(() => {
    setBasicStatus(getBasicStatusInfo());
    setAdvancedStatus(getAdvancedStatusInfo());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysisStatus]);

  return (
    <>
      <div className="flex items-center justify-between px-4 py-1 border-t-2 border-gray-200 bg-white shadow-sm">
        <div className="flex items-center space-x-8">
          {/* First section with context-dependent background */}
          <div
            className={`flex items-center py-2 px-3 rounded ${
              selectedGroup && analyticsType === "group" ? "bg-purple-50" : !selectedGroup ? "bg-blue-50" : ""
            }`}
          >
            <div className="flex flex-col justify-center">
              <div className="text-xs text-gray-500 mb-1">{selectedGroup ? "Group" : "Trace"}</div>
              <div className="flex items-center space-x-2">
                {selectedGroup && analyticsType === "group" ? (
                  <FolderKanban className="w-5 h-5 text-purple-500" />
                ) : (
                  <FolderKanban className="w-5 h-5 text-gray-500" />
                )}
                {selectedGroup ? (
                  <span
                    className="text-xl font-medium w-48 inline-block"
                    title={selectedGroup.name || "Selected Group"}
                  >
                    {displayHeader()}
                  </span>
                ) : (
                  <span className="text-xl font-medium w-48 inline-block">{displayHeader()}</span>
                )}
              </div>
            </div>
          </div>

          <div className="h-12 border-l-2 border-gray-300 mx-2 self-center flex-shrink-0"></div>

          {analyticsType === "trace" && selectedGroup && (
            <>
              <div className="bg-blue-50 py-2 px-3 rounded">
                <div className="flex flex-col justify-center">
                  <div className="text-xs text-gray-500 mb-1">Trace</div>
                  <div className="flex items-center space-x-2">
                    <FileText className="w-5 h-5 text-blue-500" />
                    <span className="text-xl font-medium w-48 inline-block">{formatTraceId(traceId)}</span>
                  </div>
                </div>
              </div>
              <div className="h-12 border-l-2 border-gray-300 mx-2 self-center flex-shrink-0"></div>
            </>
          )}

          {/* Single trace view - only highlight when not in a group */}
          {/* {!selectedGroup && traceId && (
            <>
              <div className="bg-blue-50 py-2 px-3 rounded">
                <div className="flex flex-col justify-center">
                  <div className="text-xs text-gray-500 mb-1">
                    Trace
                  </div>
                  <div className="flex items-center space-x-2">
                    <FileText className="w-5 h-5 text-blue-500" />
                    <span className="text-xl font-medium w-48 inline-block">{formatTraceId(traceId)}</span>
                  </div>
                </div>
              </div>
              <div className="h-12 border-l-2 border-gray-300 mx-2 self-center flex-shrink-0"></div>
            </>
          )} */}

          {/* Display trace navigation if we're viewing trace analytics within a group */}
          {selectedGroup && analyticsType === "trace" && (
            <div className="flex flex-col justify-center">
              <div className="text-xs text-gray-500 mb-1 text-center">Navigate</div>
              <div className="flex items-center self-center bg-gray-100 rounded-lg p-1 min-w-48">
                <button
                  onClick={handlePreviousTrace}
                  disabled={currentTraceIndex <= 0}
                  className={`px-2 py-1 rounded flex items-center ${
                    currentTraceIndex <= 0 ? "text-gray-300 cursor-not-allowed" : "text-blue-700 hover:bg-blue-100"
                  }`}
                >
                  <ChevronLeft className="w-5 h-5" />
                  <span className="hidden sm:inline ml-1 font-medium">Prev</span>
                </button>

                <span className="mx-2 text-lg font-medium w-12 text-center inline-block">
                  {currentTraceIndex + 1} / {totalTraces}
                </span>

                <button
                  onClick={handleNextTrace}
                  disabled={currentTraceIndex >= totalTraces - 1}
                  className={`px-2 py-1 rounded flex items-center ${
                    currentTraceIndex >= totalTraces - 1
                      ? "text-gray-300 cursor-not-allowed"
                      : "text-blue-700 hover:bg-blue-100"
                  }`}
                >
                  <span className="hidden sm:inline mr-1 font-medium">Next</span>
                  <ChevronRight className="w-5 h-5" />
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center space-x-6">
          <div className="flex flex-col justify-center">
            {/* <div className="text-xs text-gray-500 mb-1">Timestamp</div> */}
            <div className="text-sm text-gray-950">
              <span className="block text-sm text-gray-500">
                {new Date(timestamp).toLocaleString(undefined, {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                })}
              </span>
              <span className="block text-sm font-medium">
                {new Date(timestamp).toLocaleString(undefined, {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                  fractionalSecondDigits: 3,
                  hour12: false,
                })}
              </span>
            </div>
          </div>

          <div className="flex flex-col justify-center">
            <div className="text-xs text-gray-500 mb-1">Service</div>
            <div
              className="text-sm text-gray-950"
              title={(traceId && traceId !== "") || (selectedGroup && selectedGroup.id) ? serviceName : ""}
            >
              {(traceId && traceId !== "") || (selectedGroup && selectedGroup.id) ? formatServiceName(serviceName) : ""}
            </div>
          </div>

          {/* Replace single status with two analysis status indicators */}
          <div className="flex flex-col justify-center">
            <div className="text-xs text-gray-500 mb-1 text-center">Analyses</div>
            <div className="flex items-center space-x-2">
              <span
                className={`px-2 py-1 ${basicStatus?.color} text-xs rounded-md flex items-center`}
                title={basicStatus?.text}
              >
                {basicStatus?.icon}
                Basic
              </span>

              <span
                className={`px-2 py-1 ${advancedStatus?.color} text-xs rounded-md flex items-center`}
                title={advancedStatus?.text}
              >
                {advancedStatus?.icon}
                Advanced
              </span>
            </div>
          </div>

          <button
            className="flex items-center text-blue-600 hover:text-blue-800 self-center ml-2"
            onClick={handleOpenModal}
          >
            Change selection
            <ChevronDown className="w-4 h-4 ml-1" />
          </button>
        </div>
      </div>

      <TraceSelectionModal
        isOpen={isModalOpen}
        setIsOpen={setIsModalOpen}
        onClose={handleCloseModal}
        serverUrl={serverUrl}
        onTraceSelect={onTraceSelect}
        serviceName={serviceName}
        setServiceName={setServiceName}
        handleJsonUpload={handleJsonUpload}
        extensionsEnabled={extensionsEnabled}
      />
    </>
  );
};

export default TopBar;
