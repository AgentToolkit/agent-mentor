import { useState } from 'react';
import { useAuth } from '../AuthComponents';
import { buildHierarchy, buildIssuesAndMetrics } from '../utils/hierarchyUtils';
import { handleGroupMetrics } from '../utils/metricsUtils';
import { updateUrlParams } from '../utils/urlUtils';

export const useGroupManagement = ({
  serverUrl,
  setError,
  setAnalyticsMetrics,
  setIssues,
  setMetrics,
  setWorkflowData,
  setTrajectoryData,
  fetchStorageTraceDetails,
  setAnalysisStatus,
  activeTab,
  serviceName,
  analyticsMetrics,
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [selectedGroup, setSelectedGroup] = useState(null);
  const [groupTraces, setGroupTraces] = useState([]);
  const [groupTasks, setGroupTasks] = useState([]);
  const [currentTraceIndex, setCurrentTraceIndex] = useState(0);
  const [analyticsType, setAnalyticsType] = useState('trace'); // 'group' or 'trace'
  const { authFetch } = useAuth();

  const voidFunc = () => {}; // Empty function for placeholders

  // Handle group selection
  const handleGroupSelect = async (group, serviceName) => {
    setSelectedGroup(group);
    setTrajectoryData([]);

    try {
      // Fetch all traces in the group
      setIsLoading(true);
      const response = await authFetch(`${serverUrl}/storage/${serviceName}/groups/${group.id}/traces`);
      setIsLoading(false);

      if (!response.ok) {
        throw new Error(`Error fetching group traces: ${response.status}`);
      }

      const groupData = await response.json();

      if (groupData.traces && groupData.traces.length > 0) {
        setGroupTraces(groupData.traces);
        setWorkflowData(groupData.workflows);
        if (groupData.metrics)
          setAnalyticsMetrics(groupData.metrics || []);

        const [processedIssues, processedEvalMetrics] = buildIssuesAndMetrics(
          groupData.tasks,
          groupData.issues,
          groupData.metrics,
          null
        );

        setGroupTasks(buildHierarchy(groupData.tasks, voidFunc, voidFunc));
        setIssues(processedIssues);
        setCurrentTraceIndex(0);

        // Calculate and set group metrics
        const groupMetrics = handleGroupMetrics(groupTasks, groupData.traces);
        setMetrics({
          ...groupMetrics,
          issues: processedIssues.length,
        });

        // Set initial state to show group analytics
        setAnalyticsType('group');

        // Also load the first trace data
        if (groupData.traces[0]) {
          await fetchStorageTraceDetails(groupData.traces[0].id, serviceName, true);

          // Update analysis status if available
          if (groupData.traces[0].analysisStatus) {
            setAnalysisStatus(groupData.traces[0].analysisStatus);
          } else {
            // Reset analysis status if not available
            setAnalysisStatus({
              basic: null,
              advanced: null,
            });
          }
        }

        if (groupData.error) {
          setError('Some traces encountered errors: ' + groupData.error);
        }
      } else {
        setError('No traces found in this group.');
        setGroupTraces([]);
        setWorkflowData([]);
      }
    } catch (error) {
      console.error('Error handling group selection:', error);
      setError(error.message);
    }
  };

  // Handle navigation between traces in a group
  const handleTraceNavigation = async (index) => {
    if (index >= 0 && index < groupTraces.length) {
      setCurrentTraceIndex(index);

      if (groupTraces[index].analysisStatus) {
        setAnalysisStatus(groupTraces[index].analysisStatus);
      }

      updateUrlParams({
        traceId: groupTraces[index].id,
        tabName: activeTab,
      });

      await fetchStorageTraceDetails(groupTraces[index].id, serviceName);
      setAnalyticsType('trace');
    }
  };

  return {
    isLoading,
    selectedGroup,
    setSelectedGroup,
    groupTraces,
    setGroupTraces,
    groupTasks,
    setGroupTasks,
    currentTraceIndex,
    analyticsType,
    setAnalyticsType,
    handleGroupSelect,
    handleTraceNavigation,
  };
};