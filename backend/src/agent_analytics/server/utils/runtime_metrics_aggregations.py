import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from ibm_agent_analytics_common.interfaces.metric import (
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
from agent_analytics.runtime.api import TenantComponents
from agent_analytics.runtime.executor.analytics_execution_engine import (
    AnalyticsRuntimeEngine,
    ExecutionStatus,
)
from agent_analytics.runtime.registry.analytics_registry import AnalyticsRegistry
from agent_analytics.server.utils.runtime_metrics import (
    get_duration_stats_for_agents,
    get_num_failed_traces_for_agents,
    get_num_unique_traces_for_agents,
    get_overall_metrics_with_agent_filter,
    get_traces_for_agent,
)


async def _create_overall_metric(
    service_name: str,
    tenant_components: TenantComponents,
    tenant_id: str,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    agent_ids_filter: list[str] | None = None
) -> AggregateMetric:

    # Use the consolidated query that properly filters by agent_ids
    # This single query fetches all three metrics with proper agent filtering
    overall_metrics = await get_overall_metrics_with_agent_filter(
        tenant_id=tenant_id,
        tenant_components=tenant_components,
        service_name=service_name,
        start_time=start_time,
        end_time=end_time,
        agent_ids=agent_ids_filter
    )

    # Get current timestamp
    current_timestamp = datetime.now()

    # Create duration metric from the response
    aggregated_stats = AggregatedStats(
        count=overall_metrics.duration_stats.count,
        mean=overall_metrics.duration_stats.avg or 0.0,
        std=None,
        min=overall_metrics.duration_stats.min,
        max=overall_metrics.duration_stats.max,
        attributes=None
    )

    duration_metric = BasicStatsMetric(
        name="duration",
        value=aggregated_stats,
        units="milliseconds",
        timestamp=current_timestamp.isoformat().replace('+00:00', '') + 'Z'
    )

    # Create failures metric
    failures_metric = NumericMetric(
        name="failed_traces",
        value=float(overall_metrics.failed_traces),
        units="count",
        timestamp=current_timestamp.isoformat().replace('+00:00', '') + 'Z'
    )

    # Create requests metric
    requests_metric = NumericMetric(
        name="requests_num",
        value=float(overall_metrics.unique_traces),
        units="count",
        timestamp=current_timestamp.isoformat().replace('+00:00', '') + 'Z'
    )

    # Create scope to reflect what was actually queried
    # Note: The query always filters for traces with agent.id tag
    # If agent_ids_filter is provided, it filters for those specific agents
    scope = None
    if start_time is not None or agent_ids_filter is not None:
        scope_kwargs = {}

        if start_time is not None:
            scope_kwargs['time_interval'] = TimeInterval(
                lower_bound=start_time,
                upper_bound=end_time
            )

        # Always include agent_ids in scope when provided
        # When None/empty, the query filters for any trace with agent.id tag
        if agent_ids_filter is not None and len(agent_ids_filter) > 0:
            scope_kwargs['agent_ids'] = agent_ids_filter

        scope = MetricScope(**scope_kwargs)

    # Create and return AggregateMetric
    aggregate_metric = AggregateMetric(
        name="trace_agreggate_metric",
        description="Aggregate metric across traces matching filter",
        value=[duration_metric, failures_metric, requests_metric],
        timestamp=current_timestamp.isoformat().replace('+00:00', '') + 'Z',
        scope=scope
    )

    return aggregate_metric


async def fetch_agent_metrics(
    service_name: str,
    tenant_components: TenantComponents,
    tenant_id: str,
    agent_ids_filter: list[str] | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None
) -> list[AggregateMetric]:

    # Call all three agent methods concurrently for better performance
    unique_traces_response, failed_traces_response, duration_stats_response = await asyncio.gather(
        get_num_unique_traces_for_agents(
            tenant_id=tenant_id,
            tenant_components=tenant_components,
            agent_ids=agent_ids_filter,
            service_name=service_name,
            start_time=start_time,
            end_time=end_time
        ),
        get_num_failed_traces_for_agents(
            tenant_id=tenant_id,
            tenant_components=tenant_components,
            agent_ids=agent_ids_filter,
            service_name=service_name,
            start_time=start_time,
            end_time=end_time
        ),
        get_duration_stats_for_agents(
            tenant_id=tenant_id,
            tenant_components=tenant_components,
            agent_ids=agent_ids_filter,
            service_name=service_name,
            start_time=start_time,
            end_time=end_time
        )
    )

    # Parse the JSON responses
    unique_traces_agents = unique_traces_response.agents
    failed_traces_agents = failed_traces_response.agents
    duration_stats_agents = duration_stats_response.agents

    # Create dictionaries for quick lookup by agent_id
    unique_traces_dict = {agent.agent_id: agent.unique_traces for agent in unique_traces_agents}
    failed_traces_dict = {agent.agent_id: agent.failed_traces for agent in failed_traces_agents}
    duration_stats_dict = {agent.agent_id: agent.duration_stats for agent in duration_stats_agents}

    # Get all unique agent IDs from all responses
    all_agent_ids = set()
    all_agent_ids.update(unique_traces_dict.keys())
    all_agent_ids.update(failed_traces_dict.keys())
    all_agent_ids.update(duration_stats_dict.keys())

    # Get current timestamp
    current_timestamp = datetime.now()

    # Create aggregate metrics for each agent
    result_metrics = []

    for agent_id in all_agent_ids:
        # Get data for this agent (with defaults)
        unique_traces_count = unique_traces_dict.get(agent_id, 0)
        failure_count = failed_traces_dict.get(agent_id, 0)
        duration_data = duration_stats_dict.get(agent_id, None)


        # Create AggregatedStats object
        if duration_data:
            # Create duration stats
            count = duration_data.count
            min_val = duration_data.min
            max_val = duration_data.max
            avg_val = duration_data.avg

            duration_stats = AggregatedStats(
                count=count,
                mean=avg_val or 0.0,
                std=0.0,  # Can't calculate from provided data
                min=min_val or 0.0,
                max=max_val or 0.0,
                attributes=None
            )
        else:
            duration_stats = AggregatedStats(
                count=0,
                mean=0.0,
                std=0.0,
                min=0.0,
                max=0.0,
                attributes=None
            )

        # Create the three metrics for this agent
        duration_metric = BasicStatsMetric(
            name="duration",
            value=duration_stats,
            units="milliseconds",
            timestamp=current_timestamp.isoformat().replace('+00:00', '') + 'Z'
        )

        failures_metric = NumericMetric(
            name="failed_traces",
            value=float(failure_count),
            units="count",
            timestamp=current_timestamp.isoformat().replace('+00:00', '') + 'Z'
        )

        requests_metric = NumericMetric(
            name="requests_num",
            value=float(unique_traces_count),
            units="count",
            timestamp=current_timestamp.isoformat().replace('+00:00', '') + 'Z'
        )

        scope = None
        if start_time is not None or agent_id is not None:
            scope_kwargs = {}

            # Add time interval if start_time is provided
            if start_time is not None:
                scope_kwargs['time_interval'] = TimeInterval(
                    lower_bound=start_time,
                    upper_bound=end_time  # Can be None
                )

            # Add this specific agent_id to the scope
            if agent_id is not None:
                scope_kwargs['agent_ids'] = [agent_id]  # Only this agent

            scope = MetricScope(**scope_kwargs)

        # Create the aggregate metric for this agent
        aggregate_metric = AggregateMetric(
            name=f"agent_aggregate_metric_{agent_id}",
            description=f"Aggregate metric for agent {agent_id} across filtered traces",
            value=[duration_metric, failures_metric, requests_metric],
            timestamp=current_timestamp.isoformat().replace('+00:00', '') + 'Z',
            scope=scope
        )

        result_metrics.append(aggregate_metric)

    return result_metrics

async def create_combined_agent_summary_metrics_traces_optimized(
    service_name: str,
    tenant_components: TenantComponents,
    tenant_id: str,
    agent_ids_filter: list[str] | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    include_overall_metric: bool = True
    ) -> list[AggregateMetric]:

    result_metrics = []

    if include_overall_metric:
        # Call the _create_overall_metric method with all relevant parameters
        overall_metric = await _create_overall_metric(
            service_name=service_name,
            tenant_components=tenant_components,
            tenant_id=tenant_id,
            start_time=start_time,
            end_time=end_time,
            agent_ids_filter=agent_ids_filter
        )
        result_metrics.append(overall_metric)

    if agent_ids_filter:
        # Call fetch_agent_metrics with relevant parameters
        agent_metrics = await fetch_agent_metrics(
            service_name=service_name,
            tenant_components=tenant_components,
            tenant_id=tenant_id,
            agent_ids_filter=agent_ids_filter,
            start_time=start_time,
            end_time=end_time
        )
        result_metrics.extend(agent_metrics)

    return result_metrics

async def _get_sorted_trace_ids_for_agent(
    tenant_id: str,
    tenant_components: TenantComponents,
    agent_id: str,
    service_name: str,
    start_time: datetime | None = None,
    end_time: datetime | None = None
) -> list[str]:
    """
    Gets trace IDs for an agent, sorted by start time (most recent first).
    
    Returns:
        List of trace IDs sorted by start_time in descending order (recent first)
    """

    # Call the method to get traces data
    traces_response = await get_traces_for_agent(
        tenant_id=tenant_id,
        tenant_components=tenant_components,
        agent_id=agent_id,
        service_name=service_name,
        start_time=start_time,
        end_time=end_time
    )

    # Parse the JSON response
    traces = traces_response.traces

    # Sort traces by start_time in descending order (most recent first)
    # Convert ISO timestamp strings to datetime objects for proper sorting
    # Note: We only convert for sorting purposes, original timezone info is preserved
    sorted_traces = sorted(
        traces,
        key=lambda trace: datetime.fromisoformat(trace.start_time.replace('Z', '+00:00')),
        reverse=True  # Most recent first
    )

    # Extract and return just the trace IDs
    trace_ids = [trace.trace_id for trace in sorted_traces]

    return trace_ids

async def create_detailed_metrics_traces(
    data_manager: DataManager,
    registry: AnalyticsRegistry,
    execution_engine: AnalyticsRuntimeEngine,
    task_analytics_name: str,
    service_name: str,
    tenant_components: TenantComponents,
    tenant_id: str,
    agent_ids_filter: list[str] | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    pagination: tuple[int, int] | None = None,
) -> list[AggregateMetric]:

    result_metrics = []

    # If agent_ids_filter is provided, process each agent individually
    if agent_ids_filter:
        for agent_id in agent_ids_filter:
            # Call method that handles single agent processing
            agent_metrics = await _create_detailed_metrics_for_single_agent(
                data_manager=data_manager,
                registry=registry,
                execution_engine=execution_engine,
                task_analytics_name=task_analytics_name,
                service_name=service_name,
                tenant_id=tenant_id,
                tenant_components=tenant_components,
                agent_id=agent_id,
                start_time=start_time,
                end_time=end_time,
                pagination=pagination
            )
            result_metrics.extend(agent_metrics)
    else:
        # If no agent filter, do not do anything
        return result_metrics

    return result_metrics

def _extract_model_usage_by_trace(tasks: list[dict[str, Any]], trace_ids: list[str]) -> tuple[dict[str, dict[str, float]], list[str], list[list[dict[str, Any]]]]:
    """Extract model usage statistics grouped by trace ID.
    
    Args:
        tasks: List of task model dumps
        
    Returns:
        Dict where key is trace_id, value is dict of {model_name: usage_count}
    """
    trace_model_usage = defaultdict(lambda: defaultdict(float))
    suspect_trace_ids = trace_ids.copy() # suspect of not being fully processed their tasks
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

async def _create_detailed_metrics_for_single_agent(
    data_manager: DataManager,
    registry: AnalyticsRegistry,
    execution_engine: AnalyticsRuntimeEngine,
    task_analytics_name: str,
    service_name: str,
    tenant_id:str,
    tenant_components: TenantComponents,
    agent_id: str,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    pagination: tuple[int, int] | None = None,
) -> list[AggregateMetric]:

    # Fetch the traces for this agent, sorted by their timestamps - from recent to oldest
    agent_trace_ids = await _get_sorted_trace_ids_for_agent(
        tenant_id=tenant_id,
        tenant_components=tenant_components,
        agent_id=agent_id,
        service_name=service_name,
        start_time=start_time,
        end_time=end_time
    )
    total_traces_count = len(agent_trace_ids)

    # Apply pagination if provided
    if pagination:
        start_index, end_index = pagination
        # Filter traces according to pagination: from start_index (including) to end_index (excluding)
        filtered_trace_ids = agent_trace_ids[start_index:end_index]
    else:
        filtered_trace_ids = agent_trace_ids

    # Process filtered_trace_ids to create detailed metrics for this agent
    traces_needing_processing = []
    existing_task_list = []

    for trace_id in filtered_trace_ids:
        tasks = await BaseTraceComposite.get_tasks_for_trace(data_manager, trace_id)
        if tasks:
            # Tasks already exist, add their dumps to task_list
            existing_task_list.extend([task.model_dump() for task in tasks])
        else:
            # No tasks exist, add to processing list
            traces_needing_processing.append(trace_id)

    existing_models_usage_dict, suspect_trace_ids, existing_task_list = _extract_model_usage_by_trace(existing_task_list, filtered_trace_ids)

    # process tasks again for traces that have previously failed?
    traces_needing_processing.extend(suspect_trace_ids)

    # Only run plugin if there are traces that need processing
    task_list = []  # Start with empty tasks

    if traces_needing_processing:
        #run the plugin and calculate tasks
        input_model_class = await registry.get_pipeline_input_model(task_analytics_name)
        traces_needing_processing = list(set(traces_needing_processing))  # deduplicate
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

    agent_metrics = []
    metrics = await _create_metrics_per_trace(data_manager,filtered_trace_ids,models_usage_dict,total_traces_count,[agent_id],start_time=start_time,end_time=end_time)
    agent_metrics.extend(metrics)
    return agent_metrics

async def _create_metrics_per_trace(
    data_manager: DataManager,
    filtered_trace_ids: list[str],
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


    for trace_id in filtered_trace_ids:
        trace = await BaseTraceComposite.get_by_id(data_manager,id=trace_id)
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


