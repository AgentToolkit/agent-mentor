import statistics
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from agent_analytics_common.interfaces.issues import IssueLevel
from agent_analytics_common.interfaces.metric import (
    AggregatedStats,
    AggregateMetric,
    BasicStatsMetric,
    DistributionMetric,
    MetricScope,
    NumericMetric,
    TimeInterval,
)

from agent_analytics.core.data.base_data_manager import DataManager
from agent_analytics.core.data_composite.base_trace import BaseTraceComposite
from agent_analytics.runtime.executor.analytics_execution_engine import (
    AnalyticsRuntimeEngine,
    ExecutionStatus,
)
from agent_analytics.runtime.registry.analytics_registry import AnalyticsRegistry


def _filter_traces_by_agent_ids(traces: list[BaseTraceComposite], agent_ids_filter: list[str] | None = None, pagination: tuple[int, int] | None = None) ->  tuple[list[BaseTraceComposite], int]:
    """Filter traces by agent IDs.
    
    Args:
        traces: List of traces to filter
        agent_ids_filter: Optional list of agent IDs to filter by. If None or empty, returns all traces.
        
    Returns:
        List of traces that contain at least one of the specified agent IDs
    """
    # Filter by agent IDs if provided
    if agent_ids_filter:
        filtered_traces = []
        agent_ids_set = set(agent_ids_filter)  # Convert to set for faster lookup

        for trace in traces:
            if trace.agent_ids and any(agent_id in agent_ids_set for agent_id in trace.agent_ids):
                filtered_traces.append(trace)
    else:
        filtered_traces = traces

    # Apply pagination if provided
    total_filtered_count = len(filtered_traces)

    if pagination is None:
        return filtered_traces, total_filtered_count

    # Sort filtered traces by start_time when pagination is needed
    sorted_traces = sorted(filtered_traces, key=lambda trace: trace.start_time or datetime.min, reverse=True)

    start_idx, end_idx = pagination
    total_traces = len(sorted_traces)

    # Handle edge cases
    if start_idx >= total_traces:
        start_idx = 0
        end_idx = min(end_idx - start_idx, total_traces)
    else:
        end_idx = min(end_idx, total_traces)

    return sorted_traces[start_idx:end_idx],total_filtered_count

def _create_trace_summary_aggregate_metric_with_agent_mapping(
    traces: list[BaseTraceComposite],
    agent_ids_filter: list[str] | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None
) -> tuple[AggregateMetric, dict[str, list[BaseTraceComposite]]]:
    """
    Creates an AggregateMetric and simultaneously builds agent-to-traces mapping in a single iteration.
    """
    from datetime import datetime

    # Initialize collections for both metric calculation and agent mapping
    durations = []
    failure_count = 0
    agent_to_traces = defaultdict(list)

    # Convert agent_ids_filter to set for faster lookup
    agent_ids_set = set(agent_ids_filter) if agent_ids_filter else set()

    # Single iteration to collect metric data AND build agent mapping
    for trace in traces:
        # Calculate duration (existing logic)
        if trace.start_time and trace.end_time:
            duration_ms = (trace.end_time - trace.start_time).total_seconds() * 1000
            durations.append(duration_ms)

        # Count failures (existing logic)
        if trace.failures:
            has_critical_error = (
                trace.failures.get(IssueLevel.ERROR, 0) > 0 or
                trace.failures.get(IssueLevel.CRITICAL, 0) > 0
            )
            if has_critical_error:
                failure_count += 1

        # Build agent mapping (new logic added to existing iteration)
        if trace.agent_ids:
            if agent_ids_filter:
                # Map only agents that are in the filter
                trace_agent_ids = set(trace.agent_ids)
                agents_to_map = trace_agent_ids.intersection(agent_ids_set)
            else:
                # Map all agents in the trace
                agents_to_map = trace.agent_ids

            for agent_id in agents_to_map:
                agent_to_traces[agent_id].append(trace)

    # Calculate duration statistics
    if durations:
        duration_stats = AggregatedStats(
            count=len(durations),
            mean=statistics.mean(durations),
            std=statistics.stdev(durations) if len(durations) > 1 else None,
            min=min(durations),
            max=max(durations),
            attributes=None
        )
    else:
        duration_stats = AggregatedStats(
            count=0,
            mean=0.0,
            std=None,
            min=None,
            max=None,
            attributes=None
        )

    # Create timestamp
    current_timestamp = datetime.now(UTC).isoformat().replace('+00:00', '') + 'Z'

    # Create scope only if we have time or agent filters
    scope = None
    if start_time is not None or (agent_ids_filter is not None and len(agent_ids_filter) > 0):
        scope_kwargs = {}

        if start_time is not None:
            scope_kwargs['time_interval'] = TimeInterval(
                lower_bound=start_time,
                upper_bound=end_time
            )

        if agent_ids_filter is not None and len(agent_ids_filter) > 0:
            scope_kwargs['agent_ids'] = agent_ids_filter

        scope = MetricScope(**scope_kwargs)

    # Create the three metrics
    duration_metric = BasicStatsMetric(
        name="duration",
        value=duration_stats,
        units="milliseconds",
        timestamp=current_timestamp
    )

    failures_metric = NumericMetric(
        name="failed_traces",
        value=float(failure_count),
        units="count",
        timestamp=current_timestamp
    )

    requests_metric = NumericMetric(
        name="requests_num",
        value=float(len(traces)),
        units="count",
        timestamp=current_timestamp
    )

    # Create the aggregate metric
    aggregate_metric = AggregateMetric(
        name="trace_agreggate_metric",
        description="Aggregate metric across traces matching filter",
        value=[duration_metric, failures_metric, requests_metric],
        timestamp=current_timestamp,
        scope=scope
    )

    return aggregate_metric, dict(agent_to_traces)



def _create_metrics_per_trace(
    traces: list[BaseTraceComposite],
    llm_usage_by_trace: dict[str, dict[str, float]],
    total_filtered_traces: int,
    agent_ids_filter: list[str] | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None
) -> list[AggregateMetric]:
    """
    Creates a list of AggregateMetric from traces and LLM usage data.
    
    Args:
        traces: List of TraceData objects
        llm_usage_by_trace: Dict mapping trace_id -> {model_name: count}
    
    Returns:
        List of AggregateMetric, one per trace
    """
    aggregate_metrics_list = []

    # Create scope only if we have time or agent filters
    scope = None
    if start_time is not None or (agent_ids_filter is not None and len(agent_ids_filter) > 0):
        scope_kwargs = {}

        # Add time interval if start_time is provided
        if start_time is not None:
            scope_kwargs['time_interval'] = TimeInterval(
                lower_bound=start_time,
                upper_bound=end_time  # Can be None
            )

        # Add agent_ids if provided and not empty
        if agent_ids_filter is not None and len(agent_ids_filter) > 0:
            scope_kwargs['agent_ids'] = agent_ids_filter

        scope = MetricScope(**scope_kwargs)

    current_timestamp = datetime.now(UTC)
    total_traces_metric = NumericMetric(
        name="total_num_traces",
        value=float(total_filtered_traces),
        units="count",
        timestamp=current_timestamp.isoformat().replace('+00:00', '') + 'Z'
    )

    total_traces_aggregate = AggregateMetric(
        name="total_num_traces_metric",
        description="Total number of traces in time range and service name scope after filtering by agent IDs",
        value=[total_traces_metric],
        timestamp=current_timestamp.isoformat().replace('+00:00', '') + 'Z',
        scope=scope
    )

    # Add the total traces metric as the first item
    aggregate_metrics_list.append(total_traces_aggregate)
    # Create timestamp


    for trace in traces:
        # Calculate duration in seconds
        duration_ms = (trace.end_time - trace.start_time).total_seconds() * 1000
        timestamp = trace.start_time if trace.start_time is not None else current_timestamp
        # Create duration metric
        duration_metric = NumericMetric(
            name="duration",
            value=duration_ms,
            units="milliseconds",
            related_to_ids=[trace.element_id],
            timestamp=timestamp.isoformat().replace('+00:00', '') + 'Z'
        )

        # Convert issues dict from int to float for DistributionMetric
        issues_distribution = {k: float(v) for k, v in trace.failures.items()}

        # Create issues distribution metric
        issues_metric = DistributionMetric(
            name="issues",
            value=issues_distribution,
            units="count",
            related_to_ids=[trace.element_id],
            timestamp=timestamp.isoformat().replace('+00:00', '') + 'Z'
        )

        # Get LLM usage for this trace (use empty dict if not found)
        llm_usage_distribution = llm_usage_by_trace.get(trace.element_id, {})

        # Create LLM usage distribution metric
        llm_usage_metric = DistributionMetric(
            name="llm_usage",
            value=llm_usage_distribution,
            units="count",
            related_to_ids=[trace.element_id],
            timestamp=timestamp.isoformat().replace('+00:00', '') + 'Z'
        )


        aggregate_metric = AggregateMetric(
            name=f"trace_metrics_{trace.element_id}",
            description="Statistical metrics per trace",
            value=[duration_metric, issues_metric, llm_usage_metric],
            timestamp=timestamp.isoformat().replace('+00:00', '') + 'Z',
            scope=scope,
            related_to_ids=[trace.element_id]  # Related to this specific trace
        )

        aggregate_metrics_list.append(aggregate_metric)

    return aggregate_metrics_list

def _extract_model_usage_by_trace(tasks: list[dict[str, Any]], trace_ids: list[str]) -> tuple[dict[str, dict[str, float]], list[str], list[list[dict[str, Any]]]]:
    """Extract model usage statistics grouped by trace ID.
    
    Args:
        tasks: List of task model dumps
        
    Returns:
        Dict where key is trace_id, value is dict of {model_name: usage_count}
    """
    trace_model_usage = defaultdict(lambda: defaultdict(float))
    suspect_trace_ids = trace_ids # suspect of not being fully processed their tasks
    processed_tasks = []

    for task in tasks:
        # Check if task has "llm_call" tag
        tags = task.get('tags', [])
        if 'llm_call' not in tags:
            continue

        # Extract trace_id from log_reference
        log_reference = task.get('log_reference', {})
        trace_id = log_reference.get('trace_id')
        if not trace_id:
            continue

        # Extract model name from metadata
        metadata = task.get('metadata', {})
        model_name = metadata.get('gen_ai.request.model')
        if not model_name:
            continue

        processed_tasks.append(task)
        # Increment usage count for this model in this trace
        trace_model_usage[trace_id][model_name] += 1

        # if we got here - there's at least one LLM task - we can say the trace is "clear"
        if trace_id in suspect_trace_ids:
            suspect_trace_ids.remove(trace_id)

    # Convert defaultdicts to regular dicts
    return {trace_id: dict(model_dict) for trace_id, model_dict in trace_model_usage.items()}, suspect_trace_ids, processed_tasks

async def  _fetch_traces_and_filter(agent_ids_filter: list[str] | None = None,
    pagination: tuple[int, int] | None = None, traces: list[BaseTraceComposite] = [])->tuple[list[BaseTraceComposite], int]:

    filtered_traces, total_filtered_count = _filter_traces_by_agent_ids(traces,agent_ids_filter,pagination)
    return filtered_traces, total_filtered_count

async def create_combined_agent_summary_metrics_traces_optimized(
    traces: list[BaseTraceComposite],
    agent_ids_filter: list[str] | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    include_overall_metric: bool = True
) -> list[AggregateMetric]:
    """
    Creates both overall and per-agent summary metrics with maximum optimization.
    Returns len(agent_ids_filter) + 1 metrics total.
    """

    # Single fetch of all traces
    result_metrics = []

    if include_overall_metric:
    # Single iteration: create overall metric AND build agent mapping
        overall_metric, agent_to_traces = _create_trace_summary_aggregate_metric_with_agent_mapping(
            traces=traces,
            agent_ids_filter=agent_ids_filter,
            start_time=start_time,
            end_time=end_time
        )
        result_metrics.append(overall_metric)
    else:
        # Just build agent mapping without overall metric
        _, agent_to_traces = _create_trace_summary_aggregate_metric_with_agent_mapping(
            traces=traces,
            agent_ids_filter=agent_ids_filter,
            start_time=start_time,
            end_time=end_time
        )

    # Create metrics per agent using the mapping built during overall metric calculation
    if not agent_ids_filter:
        agent_ids_filter = list(agent_to_traces.keys())

    if agent_ids_filter:
        for agent_id in agent_ids_filter:
            agent_traces = agent_to_traces.get(agent_id, [])

            agent_metric = _create_agent_aggregate_metric(
                agent_id=agent_id,
                traces=agent_traces,
                agent_ids_filter=[agent_id],
                start_time=start_time,
                end_time=end_time
            )

            result_metrics.append(agent_metric)

    return result_metrics



async def create_detailed_metrics_traces(data_manager: DataManager,
                                         registry: AnalyticsRegistry,
                                         execution_engine: AnalyticsRuntimeEngine,
                                         task_analytics_name :str,
                                         traces: list[BaseTraceComposite],
                                         agent_ids_filter: list[str] | None = None,
                                         start_time: datetime | None = None,
                                         end_time: datetime | None = None,
                                         pagination: tuple[int, int] | None = None,
    )-> list[AggregateMetric]:

    filtered_traces, total_filtered_count = await _fetch_traces_and_filter(agent_ids_filter,pagination,traces)
    filtered_traces_ids = [trace.element_id for trace in filtered_traces]

    # Check which traces already have tasks and which need processing
    traces_needing_processing = []
    existing_task_list = []

    for trace_id in filtered_traces_ids:
        tasks = await BaseTraceComposite.get_tasks_for_trace(data_manager, trace_id)
        if tasks:
            # Tasks already exist, add their dumps to task_list
            existing_task_list.extend([task.model_dump() for task in tasks])
        else:
            # No tasks exist, add to processing list
            traces_needing_processing.append(trace_id)

    existing_models_usage_dict, suspect_trace_ids, existing_task_list = _extract_model_usage_by_trace(existing_task_list, filtered_traces_ids)

    # process tasks again for traces that have previously failed?
    traces_needing_processing.extend(suspect_trace_ids)

    # Only run plugin if there are traces that need processing
    task_list = []  # Start with empty tasks

    if traces_needing_processing:
        #run the plugin and calculate tasks
        input_model_class = await registry.get_pipeline_input_model(task_analytics_name)
        input_model = input_model_class(trace_ids=traces_needing_processing)
        try:
            result = await execution_engine.execute_analytics(
                    task_analytics_name,
                    input_model
                )

            if result.status == ExecutionStatus.SUCCESS:
                print("Pipeline executed successfully!")
                task_list.extend(result.output_result['task_list'])  # Add new tasks to existing ones
            else:
                if result.error != None:
                    print(result.error.message)
                    print(result.error.stacktrace)

                    raise Exception(result.error.message)
                else:
                    raise Exception("Error returned from task analytics for trace_ids: ", traces_needing_processing)
        except Exception as e:
               raise type(e)(f"Error calculating metrics for traces: {str(e)}") from e
    else:
        print("All traces already have tasks, no processing needed!")

    models_usage_dict, suspect_trace_ids, task_list = _extract_model_usage_by_trace(task_list, traces_needing_processing)
    if suspect_trace_ids:
        print(f"WARNING: Having traces without any LLM tasks: {suspect_trace_ids}")

    task_list.extend(existing_task_list)
    models_usage_dict = models_usage_dict | existing_models_usage_dict # union dicts
    aggregate_metrics_per_trace = _create_metrics_per_trace(filtered_traces,models_usage_dict,total_filtered_count,agent_ids_filter=agent_ids_filter,start_time=start_time,end_time=end_time)
    return aggregate_metrics_per_trace

def _create_agent_aggregate_metric(
    agent_id: str,
    traces: list[BaseTraceComposite],
    agent_ids_filter: list[str] | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None
) -> AggregateMetric:
    """
    Creates an AggregateMetric for a specific agent based on traces containing that agent.
    
    Args:
        agent_id: The agent ID this metric is for
        traces: List of traces containing this agent
        agent_ids_filter: Original agent IDs filter (for scope)
        start_time: Optional start time for the scope time interval
        end_time: Optional end time for the scope time interval
        
    Returns:
        AggregateMetric containing duration statistics, failure count, and trace count for this agent
    """
    # Single iteration to collect all needed data
    durations = []
    failure_count = 0

    for trace in traces:
        # Calculate duration
        if trace.start_time and trace.end_time:
            duration_ms = (trace.end_time - trace.start_time).total_seconds() * 1000
            durations.append(duration_ms)

        # Count failures
        if trace.failures:
            has_critical_error = (
                trace.failures.get(IssueLevel.ERROR, 0) > 0 or
                trace.failures.get(IssueLevel.CRITICAL, 0) > 0
            )
            if has_critical_error:
                failure_count += 1

    # Calculate duration statistics
    if durations:
        duration_stats = AggregatedStats(
            count=len(durations),
            mean=statistics.mean(durations),
            std=statistics.stdev(durations) if len(durations) > 1 else None,
            min=min(durations),
            max=max(durations),
            attributes=None
        )
    else:
        # No valid durations found
        duration_stats = AggregatedStats(
            count=0,
            mean=0.0,
            std=None,
            min=None,
            max=None,
            attributes=None
        )

    # Create timestamp
    current_timestamp = datetime.now(UTC).isoformat().replace('+00:00', '') + 'Z'

    # Create scope only if we have time or agent filters
    scope = None
    if start_time is not None or (agent_ids_filter is not None and len(agent_ids_filter) > 0):
        scope_kwargs = {}

        # Add time interval if start_time is provided
        if start_time is not None:
            scope_kwargs['time_interval'] = TimeInterval(
                lower_bound=start_time,
                upper_bound=end_time  # Can be None
            )

        # Add agent_ids if provided and not empty
        if agent_ids_filter is not None and len(agent_ids_filter) > 0:
            scope_kwargs['agent_ids'] = agent_ids_filter

        scope = MetricScope(**scope_kwargs)

    # Create the three metrics
    duration_metric = BasicStatsMetric(
        name="duration",
        value=duration_stats,
        units="milliseconds",
        timestamp=current_timestamp
    )

    failures_metric = NumericMetric(
        name="failed_traces",
        value=float(failure_count),
        units="count",
        timestamp=current_timestamp
    )

    requests_metric = NumericMetric(
        name="requests_num",
        value=float(len(traces)),
        units="count",
        timestamp=current_timestamp
    )

    # Create the aggregate metric
    aggregate_metric = AggregateMetric(
        name=f"agent_aggregate_metric_{agent_id}",
        description=f"Aggregate metric for agent {agent_id} across filtered traces",
        value=[duration_metric, failures_metric, requests_metric],
        timestamp=current_timestamp,
        scope=scope
    )

    return aggregate_metric


