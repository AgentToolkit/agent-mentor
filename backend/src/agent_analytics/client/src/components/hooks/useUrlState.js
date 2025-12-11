import { useEffect } from 'react';
import { getUrlParams, setupHistoryListener } from '../utils/urlUtils';

export const useUrlState = ({
  serverUrl,
  serviceName,
  activeTab,
  tabs,
  selectedGroup,
  groupTraces,
  traceId,
  saveServiceName,
  setIsModalOpen,
  setActiveTab,
  handleGroupSelect,
  handleTraceNavigation,
  fetchStorageTraceDetails,
  setSelectedGroup,
  setGroupTraces,
  setWorkflowData,
  setTrajectoryData,
  setData,
  setProcessedData,
  authFetch,
}) => {
  // Handle initial URL parameters
  useEffect(() => {
    const handleUrlParams = async () => {
      const params = getUrlParams();
      console.log('Initial URL params:', params);

      // Keep track if we're loading data from URL
      let dataLoaded = false;

      // If we have query parameters, set initial state accordingly
      if (params.serviceName) {
        saveServiceName(params.serviceName);

        // If only serviceName is present, show the modal
        if (!params.groupId && !params.traceId) {
          setIsModalOpen(true);
          return;
        }
      }

      // If we have a groupId, load the group
      if (params.groupId && params.serviceName) {
        try {
          await handleGroupSelect({ id: params.groupId }, params.serviceName);
          dataLoaded = true;
          setActiveTab('workflow');

          // If a specific traceId is provided, select that trace from the group
          if (params.traceId) {
            const groupResponse = await authFetch(
              `${serverUrl}/storage/${params.serviceName}/groups/${params.groupId}/traces`
            );

            if (groupResponse.ok) {
              const traces = await groupResponse.json();
              if (traces && traces.traces) {
                const traceIndex = traces.traces.findIndex((trace) => trace.id === params.traceId);
                if (traceIndex >= 0) {
                  await handleTraceNavigation(traceIndex);
                }
              }
            }
          }
        } catch (error) {
          console.error('Error loading group from URL:', error);
          // setError(`Failed to load group: ${error.message}`);
        }
      }
      // If we have a traceId but no groupId, load the trace directly
      else if (params.traceId && params.serviceName) {
        try {
          setIsModalOpen(false); // Don't show modal since we're loading trace directly
          dataLoaded = true;
          await fetchStorageTraceDetails(params.traceId, params.serviceName);
        } catch (error) {
          console.error('Error loading trace from URL:', error);
          // setError(`Failed to load trace: ${error.message}`);
        }
      }

      // If we have a tabName, set the active tab
      if (params.tabName && tabs.includes(params.tabName)) {
        setActiveTab(params.tabName);
      }

      // If no data was loaded but we have a serviceName, show the modal
      if (!dataLoaded) {
        setIsModalOpen(true);
      }
    };

    handleUrlParams();
  }, [serverUrl]); // eslint-disable-line react-hooks/exhaustive-deps

  // Handle browser history changes
  useEffect(() => {
    const historyStateHandler = async (params) => {
      console.log('Navigation state changed:', params);

      // If we go back to just having a serviceName (no trace/group), show the modal
      if (params.serviceName && !params.traceId && !params.groupId) {
        // Reset states
        setSelectedGroup(null);
        setGroupTraces([]);
        setWorkflowData([]);
        setTrajectoryData([]);
        setData([]);
        setProcessedData(null);

        // Show the modal
        setIsModalOpen(true);

        // Don't trigger an automatic fetch here
        // Just update the service name and let the modal handle it
        if (params.serviceName !== serviceName) {
          saveServiceName(params.serviceName);
        }

        return;
      }

      // Handle service name change
      if (params.serviceName !== serviceName) {
        saveServiceName(params.serviceName || '');
      }

      // Handle tab change
      if (params.tabName && params.tabName !== activeTab) {
        setActiveTab(params.tabName);
      }

      if (params.serviceName && (params.traceId || params.groupId)) {
        setIsModalOpen(false);
      }

      // Handle trace/group changes
      if (params.groupId !== (selectedGroup ? selectedGroup.id : null)) {
        // Group has changed
        if (params.groupId && params.serviceName) {
          try {
            const response = await authFetch(
              `${serverUrl}/storage/${params.serviceName}/groups/${params.groupId}/traces`
            );
            if (response.ok) {
              const groupData = await response.json();
              await handleGroupSelect(groupData, params.serviceName);
              setIsModalOpen(false);

              // If there's also a traceId, navigate to that trace
              if (params.traceId) {
                const traceIndex = groupTraces.findIndex((trace) => trace.id === params.traceId);
                if (traceIndex >= 0) {
                  await handleTraceNavigation(traceIndex);
                }
              }
            }
          } catch (error) {
            console.error('Error loading group from history:', error);
          }
        } else if (!params.groupId) {
          // Group was removed
          setSelectedGroup(null);
          setGroupTraces([]);
        }
      } else if ((params.groupId || params.traceId) && params.serviceName) {
        if (params.traceId) {
          try {
            await fetchStorageTraceDetails(params.traceId, params.serviceName);
            setIsModalOpen(false);
          } catch (error) {
            console.error('Error loading trace from history:', error);
          }
        } else {
          // Trace was removed but we still have a group
          if (selectedGroup && params.groupId) {
            // setAnalyticsType('group');
          } else {
            // No trace or group, show the modal
            setIsModalOpen(true);
          }
        }
      }
    };

    const cleanup = setupHistoryListener(historyStateHandler);
    return cleanup;
  }, [serviceName, activeTab, traceId, selectedGroup]); // eslint-disable-line react-hooks/exhaustive-deps
};
