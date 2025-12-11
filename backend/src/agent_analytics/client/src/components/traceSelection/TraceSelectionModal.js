import React, { useState, useEffect, useRef } from "react";
import { X } from "lucide-react";
import { useAuth } from "../AuthComponents";
import { Loading, InlineNotification } from "../CarbonComponents";

// Import components
import FilterPanel from "./FilterPanel";
import TraceList from "./TraceList";
import GroupCreation from "./GroupCreation";
import { storage } from "../AuthComponents";

// Import utilities
import { MODAL_STATES, ANALYTICS_STATUS } from "./modalConstants";
import { updateUrlParams, getUrlParams } from "../utils/urlUtils";

import { setupAnimationStyles } from "./styles";
import { fetchEvaluationStatus, launchEvaluation, fetchStorageTraces, createGroup, readFileAsJSON } from "./api";

const TraceSelectionModal = ({
  isOpen,
  setIsOpen,
  onClose,
  serverUrl,
  onTraceSelect,
  serviceName,
  setServiceName,
  handleJsonUpload,
  extensionsEnabled,
}) => {
  // State variables
  const [modalState, setModalState] = useState(MODAL_STATES.TRACE_LIST);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [minSpans, setMinSpans] = useState("3"); // Default to 3, empty string means no filter
  const [tracesAndGroups, setTracesAndGroups] = useState([]);
  const [traces, setTraces] = useState([]);
  const [selectedTraces, setSelectedTraces] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [groupName, setGroupName] = useState("");
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingTitle, setLoadingTitle] = useState("");
  const [showFilter, setShowFilter] = useState(false);
  const [isFilterClosing, setIsFilterClosing] = useState(false);
  const latestRequestIdRef = useRef(0);

  const { authFetch } = useAuth();
  const fileInputRef = useRef(null);

  // Apply animation styles on component mount
  useEffect(() => {
    const removeStyles = setupAnimationStyles();
    return removeStyles;
  }, []);

  // Update traces when tracesAndGroups changes
  useEffect(() => {
    setTraces(tracesAndGroups.filter((element) => !element.isGroup));
  }, [tracesAndGroups]);

  // Reset state when modal opens and fetch data if serviceName exists
  useEffect(() => {
    if (isOpen) {
      setModalState(MODAL_STATES.TRACE_LIST);
      setSelectedTraces([]);

      // Initialize search query with any existing filters
      updateSearchQueryFromFilters();

      setShowFilter(false);
      setIsFilterClosing(false);

      // Reset the request ID counter when opening the modal
      latestRequestIdRef.current = 0;

      // Get URL parameters
      const params = getUrlParams();
      const urlServiceName = params.serviceName;

      // If URL has a service name and it's different from current, use that
      if (urlServiceName && urlServiceName !== serviceName) {
        console.log(`Modal opened with URL service ${urlServiceName}, different from prop ${serviceName}`);

        // Wait a short time to let state updates settle
        setTimeout(() => {
          handleFetchStorageTraces(null, urlServiceName);
        }, 50);
      }
      // Otherwise use the service name prop if available
      else if (serviceName) {
        console.log(`Modal opened with prop service ${serviceName}`);

        // Wait a short time to let state updates settle
        setTimeout(() => {
          handleFetchStorageTraces();
        }, 50);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  // Helper function to update the search query string from current filters
  const updateSearchQueryFromFilters = (freeText = "") => {
    let query = "";

    if (serviceName) {
      query += `service:${serviceName} `;
    }

    if (startDate) {
      query += `from:${startDate} `;
    }

    if (endDate) {
      query += `to:${endDate} `;
    }

    if (minSpans) {
      query += `minspans:${minSpans} `;
    }

    if (freeText) {
      query += freeText;
    }

    setSearchQuery(query.trim());
  };

  // Update search query when filter values change
  useEffect(() => {
    if (isOpen) {
      // Extract the free text part from current query
      const parsedQuery = parseSearchQuery(searchQuery);
      const freeText = parsedQuery.text || "";

      // Update the search query with the current filters and preserve free text
      updateSearchQueryFromFilters(freeText);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serviceName, startDate, endDate, minSpans, isOpen]);

  // Added this new effect to capture direct URL changes while modal is open
  useEffect(() => {
    // Only respond to URL changes when modal is already open
    if (isOpen) {
      const handleUrlChange = () => {
        const params = getUrlParams();
        const urlServiceName = params.serviceName;

        // If URL service name exists and differs from current
        if (urlServiceName && urlServiceName !== serviceName) {
          console.log(`URL changed to service ${urlServiceName} while modal open`);

          // Fetch with the new service name from URL
          handleFetchStorageTraces(null, urlServiceName);
        }
      };

      // Listen for popstate events (back/forward buttons)
      window.addEventListener("popstate", handleUrlChange);

      return () => {
        window.removeEventListener("popstate", handleUrlChange);
      };
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, serviceName]);

  // Evaluation status functions
  const checkEvaluationStatus = async (trace, e) => {
    if (e) e.stopPropagation(); // Prevent row click

    const status = await fetchEvaluationStatus(authFetch, serverUrl, trace.id);
    if (status) {
      setTracesAndGroups((prevTracesAndGroups) =>
        updateTraceAnalysisStatus(prevTracesAndGroups, trace.id, "advanced", status)
      );
    }

    return status;
  };

  const handleLaunchEvaluation = async (trace, e) => {
    if (e) e.stopPropagation(); // Prevent row click

    // Update state immutably to show "RUNNING" immediately for better UX
    setTracesAndGroups((prevTracesAndGroups) =>
      updateTraceAnalysisStatus(prevTracesAndGroups, trace.id, "advanced", ANALYTICS_STATUS.RUNNING)
    );

    const success = await launchEvaluation(authFetch, serverUrl, trace.id);

    if (!success) {
      // Revert to previous status on failure
      const currentStatus = await fetchEvaluationStatus(authFetch, serverUrl, trace.id);
      setTracesAndGroups((prevTracesAndGroups) =>
        updateTraceAnalysisStatus(
          prevTracesAndGroups,
          trace.id,
          "advanced",
          currentStatus || ANALYTICS_STATUS.NOT_STARTED
        )
      );
    }
  };

  // Parse a query string to extract structured filter data
  const parseSearchQuery = (query) => {
    const result = {
      service: "",
      from: "",
      to: "",
      minSpans: "",
      text: "",
    };

    if (!query) return result;

    // Extract filters using regex
    const serviceMatch = query.match(/service:([^\s]+)/i);
    if (serviceMatch) {
      result.service = serviceMatch[1];
      query = query.replace(serviceMatch[0], "").trim();
    }

    const fromMatch = query.match(/from:([^\s]+)/i);
    if (fromMatch) {
      result.from = fromMatch[1];
      query = query.replace(fromMatch[0], "").trim();
    }

    const toMatch = query.match(/to:([^\s]+)/i);
    if (toMatch) {
      result.to = toMatch[1];
      query = query.replace(toMatch[0], "").trim();
    }

    const minSpansMatch = query.match(/minspans:([^\s]+)/i);
    if (minSpansMatch) {
      result.minSpans = minSpansMatch[1];
      query = query.replace(minSpansMatch[0], "").trim();
    }

    // Remaining text is free text search
    result.text = query;

    return result;
  };

  // Handle search execution
  const handleSearchExecute = () => {
    const parsedQuery = parseSearchQuery(searchQuery);

    // Update state if filters have changed
    if (parsedQuery.service !== serviceName) {
      setServiceName(parsedQuery.service);
    }

    if (parsedQuery.from !== startDate) {
      setStartDate(parsedQuery.from);
    }

    if (parsedQuery.to !== endDate) {
      setEndDate(parsedQuery.to);
    }

    if (parsedQuery.minSpans !== minSpans) {
      setMinSpans(parsedQuery.minSpans);
    }

    // Always fetch from backend when user explicitly triggers search
    // This fixes the bug where clicking magnifying glass doesn't always re-fetch
    if (parsedQuery.service) {
      handleFetchStorageTraces(null, parsedQuery.service, parsedQuery.from, parsedQuery.to, parsedQuery.minSpans);
    }
  };

  // Helper function to update trace analysis status immutably
  const updateTraceAnalysisStatus = (tracesAndGroups, traceId, statusType, newStatus) => {
    return tracesAndGroups.map((item) => {
      if (item.id === traceId && !item.isGroup) {
        return {
          ...item,
          analysisStatus: {
            ...item.analysisStatus,
            [statusType]: newStatus,
          },
        };
      }
      return item;
    });
  };

  // Fetch traces from storage
  const handleFetchStorageTraces = async (event, inputServiceName = null, inputFrom = null, inputTo = null, inputMinSpans = null) => {
    // ALWAYS check URL parameters first for the most up-to-date service name
    const urlParams = getUrlParams();
    const urlServiceName = urlParams.serviceName;

    // Priority order: 1. Explicitly passed serviceName, 2. URL parameter, 3. Component prop
    const serviceToFetch = inputServiceName || urlServiceName || serviceName;
    const fromDate = inputFrom || startDate;
    const toDate = inputTo || endDate;
    // Use inputMinSpans if explicitly passed (including empty string), otherwise use state
    const minSpansToFetch = inputMinSpans !== null ? inputMinSpans : minSpans;

    if (!serviceToFetch) {
      setError("Please enter the service name first.");
      return;
    }

    // Log what we're actually fetching
    console.log(
      `Fetching data for service: ${serviceToFetch} (from ${
        inputServiceName ? "input" : urlServiceName ? "URL" : "prop"
      })`
    );

    // If service name differs from component prop, update it
    if (serviceToFetch !== serviceName) {
      console.log(`Updating service name from ${serviceName} to ${serviceToFetch}`);
      setServiceName(serviceToFetch);
    }

    setIsLoading(true);
    setError(null);

    // Increment the request ID using the ref
    latestRequestIdRef.current += 1;
    const thisRequestId = latestRequestIdRef.current;

    console.log(`Starting fetch request #${thisRequestId} for service: ${serviceToFetch}`);

    // Extract the free text search to preserve it
    const parsedQuery = parseSearchQuery(searchQuery);
    const freeText = parsedQuery.text;

    // Update the search query to reflect the current filters
    let newQuery = "";

    if (serviceToFetch) {
      newQuery += `service:${serviceToFetch} `;
    }

    if (fromDate) {
      newQuery += `from:${fromDate} `;
    }

    if (toDate) {
      newQuery += `to:${toDate} `;
    }

    if (minSpansToFetch) {
      newQuery += `minspans:${minSpansToFetch} `;
    }

    if (freeText) {
      newQuery += freeText;
    }

    setSearchQuery(newQuery.trim());

    try {
      // Fetch the data
      const data = await fetchStorageTraces(authFetch, serverUrl, serviceToFetch, fromDate, toDate, minSpansToFetch);

      // Check if this is still the most recent request
      if (thisRequestId !== latestRequestIdRef.current) {
        console.log(`Request #${thisRequestId} is stale, current is #${latestRequestIdRef.current}`);
        return;
      }

      console.log(`Processing results for request #${thisRequestId}`);

      // Process the response...
      data.groups.forEach(function (element) {
        element.isGroup = true;
      });

      const groups = data.groups.sort((a, b) => new Date(b.startTime) - new Date(a.startTime));
      const traces = data.traces.sort((a, b) => new Date(b.startTime) - new Date(a.startTime));

      // Check if the fetched data matches our service
      // TODO: This doesn't work in Multi tenancy without a tenancy proxy
      if (
        (groups.length > 0 && groups[0].serviceName !== serviceToFetch) ||
        (traces.length > 0 && traces[0].serviceName !== serviceToFetch)
      ) {
        console.log(`Received data for wrong service: expected ${serviceToFetch}`);
        return; // Abandon this stale data
      }

      // Get evaluation statuses for all traces
      // const traceIds = traces.map((trace) => trace.id);
      // const statusPromises = traceIds.map(async (traceId) => {
      //   const status = await fetchEvaluationStatus(authFetch, serverUrl, traceId);
      //   return { traceId, status };
      // });
      // const statuses = await Promise.all(statusPromises);
      // const statusMap = {};
      // statuses.forEach(({ traceId, status }) => {
      //   if (status) {
      //     statusMap[traceId] = status;
      //   }
      // });

      // Final check before updating state
      if (thisRequestId !== latestRequestIdRef.current) {
        console.log(`Request #${thisRequestId} became stale during status fetching, aborting`);
        return;
      }

      // Update URL to match what we actually fetched
      updateUrlParams({
        serviceName: serviceToFetch,
        // Keep other parameters unchanged
      });

      setTracesAndGroups(groups.concat(traces));
      handleCloseFilter();
    } catch (error) {
      // Only show error if this is still the current request
      if (thisRequestId === latestRequestIdRef.current) {
        console.error(`Error fetching from Storage (request #${thisRequestId}):`, error);
        setError("Error fetching from Storage. Reason: " + error.message);
      }
    } finally {
      // Only update loading state if this is still the current request
      if (thisRequestId === latestRequestIdRef.current) {
        setIsLoading(false);
      }
    }
  };

  const fetchTraces = (event, inputServiceName = null) => {
    handleFetchStorageTraces(event, inputServiceName);
  };

  // Filter panel handlers
  const handleApplyFilters = (event, inputServiceName = null, inputMinSpans = null) => {
    const updateService = inputServiceName ? inputServiceName : serviceName;
    if (!updateService) {
      alert("Please select a service");
      return;
    }

    // Update serviceName in URL
    updateUrlParams({
      serviceName: updateService,
      traceId: null, // Clear trace ID
      groupId: null, // Clear group ID
    });

    // Clear any previous trace/group selections from state
    setSelectedTraces([]);

    // Explicitly fetch traces for the current service with minSpans filter
    handleFetchStorageTraces(event, updateService, null, null, inputMinSpans !== null ? inputMinSpans : minSpans);
  };

  const handleFilterButtonClick = () => {
    setModalState(MODAL_STATES.FILTER);
    setShowFilter(true);
    setIsFilterClosing(false);
  };

  const handleCloseFilter = () => {
    setIsFilterClosing(true);
    // Wait for animation to complete before changing state
    setTimeout(() => {
      setShowFilter(false);
      setModalState(MODAL_STATES.TRACE_LIST);
      setIsFilterClosing(false);
    }, 300); // Match animation duration
  };

  // Trace selection handlers
  const handleSelectAllTraces = (e) => {
    if (e.target.checked) {
      setSelectedTraces(traces.map((trace) => trace.id));
    } else {
      setSelectedTraces([]);
    }
  };

  const handleSelectTrace = (traceId) => {
    setSelectedTraces((prev) => {
      if (prev.includes(traceId)) {
        return prev.filter((id) => id !== traceId);
      } else {
        return [...prev, traceId];
      }
    });
  };

  const handleClick = (item) => {
    // Check if it's a group or a trace and handle accordingly
    const service = item.serviceName || serviceName;

    // Add to service history if a service name exists
    if (service) {
      storage.addServiceToHistory(service);
    }

    // Update URL parameters
    if (item.isGroup) {
      updateUrlParams({
        serviceName: service,
        groupId: item.id,
        traceId: null, // Clear trace ID
        // Don't update tabName here to preserve current tab
      });
    } else {
      updateUrlParams({
        serviceName: service,
        traceId: item.id,
        groupId: null, // Clear group ID
        // Don't update tabName here to preserve current tab
      });
    }

    onTraceSelect(item, service);
    setServiceName(service);
    onClose();
  };

  // Group creation handlers
  const handleCreateGroup = () => {
    if (selectedTraces.length === 0) {
      alert("Please select at least one trace");
      return;
    }
    setModalState(MODAL_STATES.GROUP_CREATION);
  };

  const handleSaveGroup = async () => {
    setIsLoading(true);
    try {
      const data = await createGroup(authFetch, serverUrl, serviceName, groupName, selectedTraces);

      setModalState(MODAL_STATES.TRACE_LIST);
      setSelectedTraces([]);
      setGroupName("");
      data.group.isGroup = true;
      setTracesAndGroups([data.group].concat(tracesAndGroups));
      alert(`Group "${groupName}" created successfully!`);
    } catch (error) {
      console.error("Error creating group:", error);
      setError("Error creating group:. Reason: " + error.message);
    } finally {
      setIsLoading(false);
    }
  };

  function extractServiceName(logData) {
    // This regex looks for "service.name": followed by a quoted string
    const regex = /"service\.name":\s*"([^"]+)"/;

    // Execute the regex on the log data
    const match = regex.exec(logData);

    // Return the captured group (the service name) if found, otherwise return null
    return match ? match[1] : null;
  }

  // File upload handlers
  const handleFileUpload = async (event) => {
    const files = Array.from(event.target.files);
    if (files.length === 0) return;

    // Validate all files first
    for (const file of files) {
      console.log("File name:", file.name);
      if (!(file.name.toLowerCase().endsWith(".log") || file.name.toLowerCase().endsWith(".json"))) {
        setError("Please upload only .log or .json files");
        event.target.value = "";
        return; // Exit the entire function if any file is invalid
      }
    }

    setError(null); // Clear any previous errors

    // Process each file after validation
    for (const file of files) {
      // handle task file upload - currently handled only on client side - No persistence!!
      if (file.name.toLowerCase().endsWith(".json")) {
        try {
          // Fix: Use the individual file instead of the event
          const jsonData = await readFileAsJSON(file);
          // update task data
          handleJsonUpload(jsonData);
          setServiceName("");
          setIsOpen(false);
        } catch (error) {
          setError("Error parsing JSON file: " + error.message);
          event.target.value = "";
          return; // Stop processing more files if there's an error
        }
      } else {
        let extractedServiceName = null;
        try {
          // Pre-extract service name from .log files (if they contain JSON)
          if (file.name.toLowerCase().endsWith(".log")) {
            try {
              const fileText = await file.text();
              // Try to parse as JSON to extract service name
              extractedServiceName = extractServiceName(fileText);
            } catch (parseError) {
              // If it's not JSON or parsing fails, continue with normal processing
              console.log("Could not pre-extract service name from log file:", parseError.message);
            }
          }

          const formData = new FormData();
          formData.append("file", file);

          handleLoading("Processing...");
          const response = await authFetch(`${serverUrl}/process`, {
            method: "POST",
            body: formData,
          });
          handleLoading(null);

          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }

          const result = await response.json();
          if (result.error) {
            throw new Error(`${result.error}`);
          }
          if (result.warning) {
            setError(result.warning);
          }
          const data = result.traces;
          if (data.length === 0) {
            // Recovery mechanism: use extracted service name if available
            if (extractedServiceName) {
              console.log("No traces from server, but recovered service name:", extractedServiceName);
              setServiceName(extractedServiceName);
              handleApplyFilters(event, extractedServiceName);
              updateUrlParams({
                serviceName: extractedServiceName,
              });
            } else {
              setError("No traces were found for the given service name in the past week.");
            }
          } else {
            // Update URL to match what we uploaded
            updateUrlParams({
              serviceName: data[0].serviceName,
              // Keep other parameters unchanged
            });
            setServiceName(data[0].serviceName);
            handleApplyFilters(event, data[0].serviceName);
          }
        } catch (error) {
          console.error("Error processing file:", error);
          setError("Error processing file. Reason: " + error.message);
          event.target.value = "";
          return; // Stop processing more files if there's an error
        }
      }
    }
    handleCloseFilter();

    // Reset the file input value after successful processing
    event.target.value = "";
  };

  const handleLoading = (title) => {
    if (title != null && title !== "") {
      setIsLoading(true);
      setLoadingTitle(title);
    } else {
      setIsLoading(false);
      setLoadingTitle("");
    }
  };

  // Handle upload button click from the TraceList
  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 font-['IBM_Plex_Sans',_sans-serif]">
      <div className="bg-white w-[90%] h-[90%] shadow-lg flex flex-col overflow-hidden">
        <div className="px-4 py-3 border-b border-[#e0e0e0] flex justify-between items-center">
          <h2 className="text-xl font-normal text-[#161616]" data-testid="trace-modal-title">
            Trace & Group Selection
          </h2>
          <button onClick={onClose} className="text-[#525252] hover:text-[#161616]">
            <X size={20} />
          </button>
        </div>

        {/* Error Display */}
        {error && (
          <div className="px-4 pt-4">
            <InlineNotification kind="error" subtitle={error} onClose={() => setError(null)} />
          </div>
        )}

        <div className="flex-1 overflow-hidden relative">
          {modalState === MODAL_STATES.GROUP_CREATION ? (
            <GroupCreation
              serviceName={serviceName}
              groupName={groupName}
              setGroupName={setGroupName}
              selectedTraces={selectedTraces}
              tracesAndGroups={tracesAndGroups}
              setModalState={setModalState}
              handleSaveGroup={handleSaveGroup}
              MODAL_STATES={MODAL_STATES}
            />
          ) : (
            <div className="flex h-full w-full overflow-hidden">
              {/* Show filter panel when showFilter is true */}
              {(modalState === MODAL_STATES.FILTER || isFilterClosing) && showFilter && (
                <div className="flex-none">
                  <FilterPanel
                    serviceName={serviceName}
                    setServiceName={setServiceName}
                    startDate={startDate}
                    setStartDate={setStartDate}
                    endDate={endDate}
                    setEndDate={setEndDate}
                    minSpans={minSpans}
                    setMinSpans={setMinSpans}
                    handleApplyFilters={handleApplyFilters}
                    handleCloseFilter={handleCloseFilter}
                    isFilterClosing={isFilterClosing}
                    handleFileUpload={handleFileUpload}
                    updateSearchQuery={updateSearchQueryFromFilters}
                  />
                </div>
              )}

              {/* Main content area */}
              <div className="flex-1 overflow-hidden">
                <TraceList
                  searchQuery={searchQuery}
                  setSearchQuery={setSearchQuery}
                  handleFilterButtonClick={handleFilterButtonClick}
                  handleCreateGroup={handleCreateGroup}
                  selectedTraces={selectedTraces}
                  serviceName={serviceName}
                  setServiceName={setServiceName}
                  startDate={startDate}
                  setStartDate={setStartDate}
                  endDate={endDate}
                  setEndDate={setEndDate}
                  minSpans={minSpans}
                  setMinSpans={setMinSpans}
                  tracesAndGroups={tracesAndGroups}
                  handleSelectAllTraces={handleSelectAllTraces}
                  traces={traces}
                  handleSelectTrace={handleSelectTrace}
                  handleClick={handleClick}
                  handleRefreshStatus={checkEvaluationStatus}
                  handleLaunchEvaluation={handleLaunchEvaluation}
                  onClose={onClose}
                  handleUploadClick={handleUploadClick}
                  handleApplyFilters={handleApplyFilters}
                  handleSearchExecute={handleSearchExecute}
                  extensionsEnabled={extensionsEnabled}
                />
              </div>
            </div>
          )}

          {/* Loading overlay */}
          {isLoading && (
            <div className="absolute inset-0 bg-white bg-opacity-70 flex items-center justify-center z-50 transition-opacity duration-200">
              <Loading withOverlay={false} description={loadingTitle || "Loading..."} />
            </div>
          )}
        </div>

        {/* Hidden file input for upload functionality */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".log,.json"
          onChange={handleFileUpload}
          className="hidden"
          multiple
        />
      </div>
    </div>
  );
};

export default TraceSelectionModal;
