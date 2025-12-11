from collections import defaultdict
from itertools import combinations

import pandas as pd
from ibm_agent_analytics_common.interfaces.iunits import NodeType, RelationType
from pydantic import BaseModel, Field

from agent_analytics.core.data_composite.action import BaseAction

# Assuming the import path you provided
from agent_analytics.core.data_composite.task import TaskComposite
from agent_analytics.core.data_composite.trace_workflow import BaseTraceWorkflow
from agent_analytics.core.data_composite.workflow import BaseWorkflow
from agent_analytics.core.data_composite.workflow_edge import BaseWorkflowEdge
from agent_analytics.core.data_composite.workflow_node import BaseWorkflowNode
from agent_analytics.core.data_composite.action import BaseAction
from agent_analytics.core.data_composite.metric import BaseNumericMetric
from agent_analytics.core.utilities.type_resolver import TypeResolutionUtils
from agent_analytics.core.data.trace_workflow_data import TraceWorkflowData
from agent_analytics.core.data.workflow_node_data import WorkflowNodeData
from agent_analytics.core.data.action_data import ActionData

BASE_WORKFLOW_NODE_METRIC = "base_workflow_node_metric"

class ActivityNode(BaseModel):
    """
    Model representing a single, unique activity in the process graph.
    A node is defined by the activity name and, optionally, the agent who performed it.
    """
    name: str = Field(..., description="The name of the activity.")
    agent: str | None = Field(None, description="The name of the agent who performed the activity.")

    class Config:
        frozen = True  # Makes the model hashable, so it can be used as a dictionary key.

    def __str__(self):
        """String representation used for creating human-readable variant strings."""
        if self.agent:
            return f"{self.agent}:{self.name}"
        return self.name


class ProcessVariant(BaseModel):
    """Model representing a unique path (variant) through the process."""
    variant_string: str = Field(..., description="A comma-separated sequence of activities representing the unique path.")
    case_ids: list[str] = Field(..., description="List of all case IDs that followed this exact variant.")
    frequency: int = Field(..., description="The number of times this variant occurred (i.e., the number of cases).")
    activities: list[ActivityNode] = Field(..., description="An ordered list of ActivityNode objects that make up this variant.")

    @classmethod
    def from_variant_dict(cls, variants_dict: dict[tuple[ActivityNode, ...], list[str]]) -> list['ProcessVariant']:
        """Converts a dictionary of variant tuples and case IDs into a list of ProcessVariant objects."""
        result = []
        for variant_tuple, case_ids in variants_dict.items():
            variant_str = ",".join(map(str, variant_tuple))
            result.append(cls(
                variant_string=variant_str,
                case_ids=case_ids,
                frequency=len(case_ids),
                activities=list(variant_tuple)
            ))
        return result


class RelationFrequency(BaseModel):
    """Represents a calculated relationship and its frequency between two activities."""
    from_activity: ActivityNode = Field(..., description="The source activity node in the relation.")
    to_activity: ActivityNode = Field(..., description="The target activity node in the relation.")
    relation_type: str = Field(..., description="Type of relation: causality, parallel, choice, etc.")
    frequency: int = Field(..., description="The number of times this relation was observed.")
    case_ids: set[str] = Field(default_factory=set, description="The set of unique case IDs that included this relation.")


class FootprintMatrix(BaseModel):
    """A model representing the footprint matrix, a core data structure for the Alpha Miner algorithm."""
    activities: list[ActivityNode] = Field(..., description="A list of all unique activity nodes found in the log.")
    relations: list[RelationFrequency] = Field(..., description="All discovered relations between pairs of nodes.")
    direct_successions: list[RelationFrequency] = Field(..., description="A list of all direct succession relations and their frequencies.")
    total_cases: int = Field(..., description="The total number of cases processed.")


class ProcessEdge(BaseModel):
    """Represents a directed edge in the final discovered process model graph."""
    from_activity: ActivityNode = Field(..., description="The source activity node of the edge.")
    to_activity: ActivityNode = Field(..., description="The target activity node of the edge.")
    gateway_type: RelationType | str = Field(..., description="The type of gateway this edge originates from (e.g., sequence, XOR, AND).")
    frequency: int = Field(..., description="The number of times this edge was traversed across all cases (hits).")
    trace_count: int = Field(..., description="The number of unique traces (cases) that included this edge.")
    case_ids: set[str] = Field(default_factory=set, description="The set of unique case IDs that traversed this edge.")
    support: float = Field(..., description="The percentage of total cases that included this edge (trace_count / total_cases).")


class ProcessModel(BaseModel):
    """The final output, representing the discovered process model as a graph."""
    activities: list[ActivityNode] = Field(..., description="All unique activity nodes in the process.")
    edges: list[ProcessEdge] = Field(..., description="All edges connecting the activity nodes.")
    start_activities: list[ActivityNode] = Field(..., description="Activity nodes that can start a process instance.")
    end_activities: list[ActivityNode] = Field(..., description="Activity nodes that can end a process instance.")
    total_cases: int = Field(..., description="The total number of cases analyzed.")
    total_variants: int = Field(..., description="The total number of unique variants discovered.")


# ==============================================================================
# Part 2: Process Discovery Pipeline (Alpha Miner - Verbose)
# ==============================================================================

def _find_agent_in_hierarchy(task_id: str, tasks_by_id: dict[str, 'TaskComposite'], visited: set[str]) -> str | None:
    """
    Recursively traverses up the parent task hierarchy to find an assigned agent role.
    """
    if task_id in visited or task_id not in tasks_by_id:
        return None
    visited.add(task_id)
    task = tasks_by_id[task_id]
    if 'LangGraph Node' in task.tags:
        return task.name.split(':')[-1]
    if task.attributes and (agent_name := task.attributes.get('crewai.agent.role')):
        return agent_name
    if task.parent_id:
        return _find_agent_in_hierarchy(task.parent_id, tasks_by_id, visited)
    return None


async def tasks_to_eventlog_async(tasks: list[TaskComposite]) -> pd.DataFrame:
    """
    Converts a list of rich TaskComposite objects to a flat pandas DataFrame event log.
    This ASYNC version uses the 'task.executor' property to get the definitive activity name.

    Args:
        tasks: A list of TaskComposite objects from the application runtime.

    Returns:
        A pandas DataFrame formatted as an event log, ready for process mining.
    """
    if not tasks:
        return pd.DataFrame(columns=['case_id', 'activity', 'agent', 'timestamp', 'action_id', 'parent_id'])

    tasks_by_id = {task.id: task for task in tasks}
    eventlog_data = []
    for task in tasks:
        # Get the definitive activity name and ID from the live executor object.
        action = await task.executor

        eventlog_data.append({
            'case_id': task.root_id or f"process_{task.id}",
            'activity': action.name,
            'agent': _find_agent_in_hierarchy(task.id, tasks_by_id, visited=set()),
            'timestamp': task.start_time,
            'action_id': action.element_id,
            'parent_id': task.parent_id  # Add parent_id to event log
        })

    df = pd.DataFrame(eventlog_data)
    df = df.sort_values(['case_id', 'timestamp']).reset_index(drop=True)

    # Standardize data types for consistency.
    if not df.empty and not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['agent'] = df['agent'].astype(pd.StringDtype())

    return df


def get_variants_for_workflow(df: pd.DataFrame, workflow_key: str, use_agent_in_analysis: bool = False,
                             case_col: str = 'case_id', activity_col: str = 'activity',
                             agent_col: str = 'agent', timestamp_col: str = 'timestamp') -> list[ProcessVariant]:
    """
    Extracts all unique process variants from a structured event log for a specific workflow.
    """
    if df.empty:
        return []

    # Filter to only tasks belonging to this workflow
    workflow_df = df[df['workflow_key'] == workflow_key].copy()

    if workflow_df.empty:
        return []

    workflow_df[agent_col] = workflow_df[agent_col].fillna(value=pd.NA).astype(pd.StringDtype())
    sorted_df = workflow_df.sort_values(by=[case_col, timestamp_col])

    def create_activity_nodes(group: pd.DataFrame) -> tuple[ActivityNode, ...]:
        """Creates a tuple of ActivityNode objects for a single case."""
        nodes = []
        for _, row in group.iterrows():
            # Conditionally include the agent based on the analysis flag.
            agent = row[agent_col] if use_agent_in_analysis and pd.notna(row[agent_col]) else None
            nodes.append(ActivityNode(name=row[activity_col], agent=agent))
        return tuple(nodes)

    # Group events by case, apply the helper to get a trace, and then find unique traces.
    variant_series = sorted_df.groupby(case_col).apply(create_activity_nodes)
    variant_map = {}
    for case_id, variant_tuple in variant_series.items():
        variant_map.setdefault(variant_tuple, []).append(case_id)

    return ProcessVariant.from_variant_dict(variant_map)


def create_matrix(variants: list[ProcessVariant]) -> FootprintMatrix:
    """Creates the footprint matrix from a list of process variants."""
    if not variants:
        return FootprintMatrix(activities=[], relations=[], direct_successions=[], total_cases=0)

    all_activities = set()
    # Store {'frequency': int, 'case_ids': set}
    direct_succession_stats = defaultdict(lambda: {'frequency': 0, 'case_ids': set()})
    total_cases = sum(v.frequency for v in variants) # Total cases is sum of variant frequencies

    # Count all direct successions across all variants.
    for variant in variants:
        all_activities.update(variant.activities)
        for i in range(len(variant.activities) - 1):
            succession = (variant.activities[i], variant.activities[i+1])
            # Add frequency (count of cases for this variant)
            direct_succession_stats[succession]['frequency'] += variant.frequency
            # Add all case_ids for this variant
            direct_succession_stats[succession]['case_ids'].update(variant.case_ids)

    activities_list = sorted(list(all_activities), key=lambda n: (n.name, n.agent or ''))
    direct_successions = [
        RelationFrequency(
            from_activity=f,
            to_activity=t,
            relation_type='direct_succession',
            frequency=stats['frequency'],
            case_ids=stats['case_ids']
        )
        for (f, t), stats in direct_succession_stats.items()
    ]

    # Determine the relationship between every pair of activities.
    relations = []
    for a in activities_list:
        for b in activities_list:
            if a == b: continue

            stats_ab = direct_succession_stats.get((a, b), {'frequency': 0, 'case_ids': set()})
            stats_ba = direct_succession_stats.get((b, a), {'frequency': 0, 'case_ids': set()})
            freq_ab = stats_ab['frequency']
            freq_ba = stats_ba['frequency']

            # Combine case_ids for parallel relation
            parallel_case_ids = stats_ab['case_ids'].intersection(stats_ba['case_ids'])

            if freq_ab > 0 and freq_ba > 0:
                relations.append(RelationFrequency(
                    from_activity=a, to_activity=b, relation_type='parallel',
                    frequency=min(freq_ab, freq_ba),
                    case_ids=parallel_case_ids
                ))
            elif freq_ab > 0:
                relations.append(RelationFrequency(
                    from_activity=a, to_activity=b, relation_type='causality',
                    frequency=freq_ab, case_ids=stats_ab['case_ids']
                ))
            elif freq_ba > 0:
                relations.append(RelationFrequency(
                    from_activity=a, to_activity=b, relation_type='reverse_causality',
                    frequency=freq_ba, case_ids=stats_ba['case_ids']
                ))
            else:
                relations.append(RelationFrequency(
                    from_activity=a, to_activity=b, relation_type='choice',
                    frequency=0, case_ids=set()
                ))

    return FootprintMatrix(
        activities=activities_list,
        relations=relations,
        direct_successions=direct_successions,
        total_cases=total_cases
    )


def alpha_miner_with_gateway_nodes(footprint_matrix: FootprintMatrix, workflow_key: str,
                                  workflow_events: list[dict], root_id: str) -> tuple[ProcessModel, list[BaseWorkflowNode], dict, dict]:
    """
    Implements the Alpha Miner algorithm to discover a process model from a footprint matrix.
    Uses timestamp-based start/end activity detection instead of edge-based detection.
    Returns:
        - ProcessModel
        - list of gateway BaseWorkflowNode objects
        - start_nodes_stats (dict mapping ActivityNode to {'frequency': int, 'case_ids': set})
        - end_nodes_stats (dict mapping ActivityNode to {'frequency': int, 'case_ids': set})
    """
    if not footprint_matrix.activities:
        return ProcessModel(activities=[], edges=[], start_activities=[], end_activities=[], total_cases=0, total_variants=0), [], {}, {}

    nodes, total_cases = footprint_matrix.activities, footprint_matrix.total_cases

    # ds_dict now stores (frequency, case_ids set)
    ds_dict = {
        (r.from_activity, r.to_activity): (r.frequency, r.case_ids)
        for r in footprint_matrix.direct_successions
    }
    rel_dict = {(r.from_activity, r.to_activity): r.relation_type for r in footprint_matrix.relations}

    # Determine incoming and outgoing relations for each node.
    incoming, outgoing = {n: set() for n in nodes}, {n: set() for n in nodes}
    for f, t in ds_dict:
        outgoing[f].add(t)
        incoming[t].add(f)

    # Use timestamp-based start/end detection
    start_nodes_stats, end_nodes_stats = get_start_end_activities_by_timestamp(workflow_events)
    start_nodes = list(start_nodes_stats.keys())
    end_nodes = list(end_nodes_stats.keys())

    # Build the edges and identify gateway nodes
    edges = []
    gateway_nodes = []

    for a_node in nodes:
        targets = list(outgoing[a_node])
        if not targets: continue

        # Case 1: Simple sequence flow.
        if len(targets) == 1:
            b_node = targets[0]
            freq, case_ids = ds_dict.get((a_node, b_node), (0, set()))
            trace_count = len(case_ids)
            edges.append(ProcessEdge(
                from_activity=a_node,
                to_activity=b_node,
                gateway_type='sequence',
                frequency=freq,
                trace_count=trace_count,
                case_ids=case_ids,
                support=trace_count / total_cases if total_cases > 0 else 0.0
            ))
        # Case 2: A split gateway - create gateway node.
        else:
            # If all targets are parallel with each other, it's an AND split.
            is_and = all(rel_dict.get((t1, t2)) == 'parallel' for t1, t2 in combinations(targets, 2))
            gateway_type = RelationType.AND if is_and else RelationType.XOR

            # Get stats for all outgoing edges
            outgoing_stats = [ds_dict.get((a_node, t), (0, set())) for t in targets]

            # Aggregate stats for the gateway
            gateway_hits = sum(stats[0] for stats in outgoing_stats)
            gateway_case_ids = set().union(*(stats[1] for stats in outgoing_stats))
            gateway_traces = len(gateway_case_ids)

            # Create gateway node
            gateway_node_id = f"Gateway:{workflow_key}#{a_node.name}_split_{gateway_type.value}#{root_id}"
            gateway_node = BaseWorkflowNode(
                element_id=gateway_node_id,
                root_id=workflow_key,  # Will be updated later
                name=gateway_node_id,
                description=f"Gateway node for {gateway_type.value} split from {a_node.name}",
                type=f"{gateway_type.value}",
                parent_id=f"Workflow:{workflow_key}#{root_id}",
                task_counter=gateway_hits,
                trace_counter=gateway_traces,
                action_id=f"Gateway_{gateway_type.value}_Split"
            )
            gateway_nodes.append(gateway_node)

            # Create edge from source to gateway
            edges.append(ProcessEdge(
                from_activity=a_node,
                to_activity=ActivityNode(name=gateway_node_id, agent=None),
                gateway_type='sequence',
                frequency=gateway_hits,
                trace_count=gateway_traces,
                case_ids=gateway_case_ids,
                support=gateway_traces / total_cases if total_cases > 0 else 0.0
            ))

            # Create edges from gateway to targets
            for b_node in targets:
                freq, case_ids = ds_dict.get((a_node, b_node), (0, set()))
                trace_count = len(case_ids)
                edges.append(ProcessEdge(
                    from_activity=ActivityNode(name=gateway_node_id, agent=None),
                    to_activity=b_node,
                    gateway_type='sequence',
                    frequency=freq,
                    trace_count=trace_count,
                    case_ids=case_ids,
                    support=trace_count / total_cases if total_cases > 0 else 0.0
                ))

    # Handle JOIN patterns - create gateway nodes for multiple incoming edges
    for dest_node in nodes:
        incoming_edges = [e for e in edges if e.to_activity == dest_node]
        if len(incoming_edges) <= 1:
            continue

        source_nodes = [e.from_activity for e in incoming_edges]

        # Check if it's a JOIN pattern (multiple incoming edges from parallel nodes)
        is_join = all(
            rel_dict.get((s1, s2)) == 'parallel' for s1, s2 in combinations(source_nodes, 2)
            if s1.name.startswith("Gateway:") is False and s2.name.startswith("Gateway:") is False # Avoid checking gateways
        )

        if is_join:
            # Determine JOIN type
            gateway_type = RelationType.AND  # Default to AND join

            # Aggregate stats for the join
            gateway_hits = sum(e.frequency for e in incoming_edges)
            gateway_case_ids = set().union(*(e.case_ids for e in incoming_edges))
            gateway_traces = len(gateway_case_ids)

            # Create gateway node for JOIN
            gateway_node_id = f"Gateway:{workflow_key}#{dest_node.name}_join_{gateway_type.value}#{root_id}"
            gateway_node = BaseWorkflowNode(
                element_id=gateway_node_id,
                root_id=workflow_key,  # Will be updated later
                name=gateway_node_id,
                description=f"Gateway node for {gateway_type.value} join to {dest_node.name}",
                type=f"{gateway_type.value}",
                parent_id=f"Workflow:{workflow_key}#{root_id}",
                task_counter=gateway_hits,
                trace_counter=gateway_traces,
                action_id=f"Gateway_{gateway_type.value}_Join"
            )
            gateway_nodes.append(gateway_node)

            # Update incoming edges to point to gateway instead of dest_node
            for edge in incoming_edges:
                edge.to_activity = ActivityNode(name=gateway_node_id, agent=None)

            # Create edge from gateway to original destination
            edges.append(ProcessEdge(
                from_activity=ActivityNode(name=gateway_node_id, agent=None),
                to_activity=dest_node,
                gateway_type='sequence',
                frequency=gateway_hits,
                trace_count=gateway_traces,
                case_ids=gateway_case_ids,
                support=gateway_traces / total_cases if total_cases > 0 else 0.0
            ))

    return ProcessModel(
        activities=nodes,
        edges=edges,
        start_activities=start_nodes,
        end_activities=end_nodes,
        total_cases=total_cases,
        total_variants=0 # This isn't calculated, but could be len(variants)
    ), gateway_nodes, start_nodes_stats, end_nodes_stats


def create_start_end_nodes(workflow_key: str, root_id: str) -> tuple[BaseWorkflowNode, BaseWorkflowNode]:
    """
    Creates start and end nodes for a workflow, using a consistent action_id for the type.
    """
    start_node = BaseWorkflowNode(
        # This MUST be unique to the trace to handle connections
        element_id=f"StartNode:{workflow_key}#{root_id}",
        root_id=root_id,
        name=f"Start_{workflow_key}",
        description=f"Start node for workflow {workflow_key}",
        type=NodeType.START,
        parent_id=f"Workflow:{workflow_key}#{root_id}",
        task_counter=0,  # Will be updated by create_start_end_edges
        trace_counter=0, # Will be updated by create_start_end_edges
        # This is the SAME for all start nodes, identifying its TYPE
        action_id="StartNode"
    )

    end_node = BaseWorkflowNode(
        # This MUST be unique to the trace to handle connections
        element_id=f"EndNode:{workflow_key}#{root_id}",
        root_id=root_id,
        name=f"End_{workflow_key}",
        description=f"End node for workflow {workflow_key}",
        type=NodeType.END,
        parent_id=f"Workflow:{workflow_key}#{root_id}",
        task_counter=0,  # Will be updated by create_start_end_edges
        trace_counter=0, # Will be updated by create_start_end_edges
        # This is the SAME for all end nodes, identifying its TYPE
        action_id="EndNode"
    )

    return start_node, end_node


def get_start_end_activities_by_timestamp(workflow_events: list[dict]) -> tuple[dict, dict]:
    """
    Determine start and end activities based on timestamps rather than edge analysis.
    This handles circular dependencies and complex patterns better.
    
    Returns:
        tuple: (start_nodes_stats, end_nodes_stats)
        Each stats dict maps ActivityNode -> {'frequency': int, 'case_ids': set[str]}
    """
    if not workflow_events:
        return {}, {}

    # Sort events by timestamp
    sorted_events = sorted(workflow_events, key=lambda x: x['timestamp'])

    # Group events by case to find start/end activities per case
    events_by_case = defaultdict(list)
    for event in sorted_events:
        events_by_case[event['case_id']].append(event)

    # Find start and end activities across all cases
    start_activities_stats = defaultdict(lambda: {'frequency': 0, 'case_ids': set()})
    end_activities_stats = defaultdict(lambda: {'frequency': 0, 'case_ids': set()})

    for case_id, case_events in events_by_case.items():
        if not case_events:
            continue

        # Sort case events by timestamp
        case_events.sort(key=lambda x: x['timestamp'])

        # First activity in case is a start activity
        first_event = case_events[0]
        start_activity_node = ActivityNode(
            name=first_event['activity'],
            agent=first_event.get('agent')
        )
        start_activities_stats[start_activity_node]['frequency'] += 1
        start_activities_stats[start_activity_node]['case_ids'].add(case_id)


        # Last activity in case is an end activity
        last_event = case_events[-1]
        end_activity_node = ActivityNode(
            name=last_event['activity'],
            agent=last_event.get('agent')
        )
        end_activities_stats[end_activity_node]['frequency'] += 1
        end_activities_stats[end_activity_node]['case_ids'].add(case_id)

    return start_activities_stats, end_activities_stats


def create_start_end_edges(workflow_key: str, root_id: str, start_node: BaseWorkflowNode,
                          end_node: BaseWorkflowNode,
                          start_activity_stats: dict[ActivityNode, dict],
                          end_activity_stats: dict[ActivityNode, dict],
                          workflow_nodes: dict[str, BaseWorkflowNode]) -> list[BaseWorkflowEdge]:
    """
    Creates edges connecting start/end nodes to the workflow.
    Also updates the start/end node counters.
    """
    edges = []
    edges_dict = {}  # Track edges to avoid duplicates

    # Update Start Node counters
    start_node.task_counter = sum(stats['frequency'] for stats in start_activity_stats.values())
    start_node.trace_counter = len(set().union(*(stats['case_ids'] for stats in start_activity_stats.values())))

    # Create edges from start node to start activities
    for start_activity, stats in start_activity_stats.items():
        start_activity_node_id = f"WorkflowNode:{workflow_key}#{start_activity.name}#{root_id}"

        if start_activity_node_id in workflow_nodes:
            edge_id = f"WorkflowEdge:{workflow_key} from {start_node.element_id} to {start_activity_node_id}#{root_id}"
            if edge_id not in edges_dict:
                edges.append(BaseWorkflowEdge(
                    element_id=edge_id,
                    name=edge_id,
                    description=f"Edge from start node to {start_activity.name}",
                    root_id=root_id,
                    type="WorkflowEdge",
                    source_category="SEQUENTIAL",
                    parent_id=f"Workflow:{workflow_key}#{root_id}",
                    source_ids=[start_node.element_id],
                    destination_ids=[start_activity_node_id],
                    destination_category="SEQUENTIAL",
                    weight=stats['frequency'],
                    trace_count=len(stats['case_ids'])
                ))
                edges_dict[edge_id] = True

    # Update End Node counters
    end_node.task_counter = sum(stats['frequency'] for stats in end_activity_stats.values())
    end_node.trace_counter = len(set().union(*(stats['case_ids'] for stats in end_activity_stats.values())))

    # Create edges from end activities to end node
    for end_activity, stats in end_activity_stats.items():
        end_activity_node_id = f"WorkflowNode:{workflow_key}#{end_activity.name}#{root_id}"

        if end_activity_node_id in workflow_nodes:
            edge_id = f"WorkflowEdge:{workflow_key} from {end_activity_node_id} to {end_node.element_id}#{root_id}"
            if edge_id not in edges_dict:
                edges.append(BaseWorkflowEdge(
                    element_id=edge_id,
                    name=edge_id,
                    description=f"Edge from {end_activity.name} to end node",
                    root_id=root_id,
                    type="WorkflowEdge",
                    source_category="SEQUENTIAL",
                    parent_id=f"Workflow:{workflow_key}#{root_id}",
                    source_ids=[end_activity_node_id],
                    destination_ids=[end_node.element_id],
                    destination_category="SEQUENTIAL",
                    weight=stats['frequency'],
                    trace_count=len(stats['case_ids'])
                ))
                edges_dict[edge_id] = True

    return edges


def create_workflow_node_metrics(
    workflow_nodes: dict[str, BaseWorkflowNode],
    workflow_node_cases: dict[str, set[str]],
    all_gateway_nodes: dict[str, BaseWorkflowNode],
    start_end_nodes: dict,
    root_id: str,
    analytics_id: str,
    workflow_id: str
) -> tuple[list[BaseNumericMetric], list[str]]:
    """
    Creates trace count metrics for each workflow node, following the standard pattern.
    
    Args:
        workflow_nodes: Dictionary mapping node_id to BaseWorkflowNode (task nodes)
        workflow_node_cases: Dictionary mapping node_id to set of case_ids (trace_ids)
        all_gateway_nodes: Dictionary of gateway nodes
        start_end_nodes: Dictionary of start/end nodes per workflow
        root_id: The root trace or trace_group id
        analytics_id: The analytics plugin id
        workflow_id: The workflow element_id
        
    Returns:
        Tuple of (list of BaseNumericMetric objects, list of metric element_ids)
    """
    metrics = []
    metric_ids = []
    
    # Create metrics for task workflow nodes
    for node_id, case_ids in workflow_node_cases.items():
        if node_id not in workflow_nodes:
            continue
            
        node = workflow_nodes[node_id]
        trace_count = len(case_ids)
        trace_ids_list = sorted(list(case_ids))
        
        # Extract action_id from node_id (following workflow_metric pattern)
        # node_id format: "WorkflowNode:workflow_key#action_name#root_id"
        splits = node_id.split('#')
        action_id = f'Action:{splits[-2]}#{splits[-1]}'  # Match the Action format with capital 'A'
        
        metric_id = f"Metric:Trace_Count:{node_id}"
        metric = BaseNumericMetric(
            element_id=metric_id,
            plugin_metadata_id=analytics_id,
            root=workflow_id,  # Use workflow_id as root
            name="Trace Count",
            tags=[BASE_WORKFLOW_NODE_METRIC],
            description=f"Number of traces that passed through workflow node {node.name}",
            related_to=(
                [workflow_id, node_id, action_id],  # THREE entities
                [
                    TypeResolutionUtils.get_fully_qualified_type_name_for_type(TraceWorkflowData),
                    TypeResolutionUtils.get_fully_qualified_type_name_for_type(WorkflowNodeData),
                    TypeResolutionUtils.get_fully_qualified_type_name_for_type(ActionData)
                ]
            ),
            value=trace_count,
            units='Count',
            attributes={
                'trace_ids': trace_ids_list,
                'node_name': node.name,
                'action_id': action_id
            }
        )
        metrics.append(metric)
        metric_ids.append(metric_id)
    
    # Create metrics for gateway nodes (no action_id for gateways)
    for gateway_node in all_gateway_nodes.values():
        trace_count = gateway_node.trace_counter
        
        metric_id = f"Metric:Trace_Count:{gateway_node.element_id}"
        metric = BaseNumericMetric(
            element_id=metric_id,
            plugin_metadata_id=analytics_id,
            root=workflow_id,  # Use workflow_id as root
            name="Trace Count",
            tags=[BASE_WORKFLOW_NODE_METRIC],
            description=f"Number of traces that passed through gateway {gateway_node.name}",
            related_to=(
                [workflow_id, gateway_node.element_id],  # Only TWO for gateways (no action)
                [
                    TypeResolutionUtils.get_fully_qualified_type_name_for_type(TraceWorkflowData),
                    TypeResolutionUtils.get_fully_qualified_type_name_for_type(WorkflowNodeData)
                ]
            ),
            value=trace_count,
            units='Count',
            attributes={
                'node_name': gateway_node.name,
                'gateway_type': gateway_node.type
            }
        )
        metrics.append(metric)
        metric_ids.append(metric_id)
    
    # Create metrics for start and end nodes (no action_id for start/end)
    for workflow_key, nodes_dict in start_end_nodes.items():
        for node_type in ['start', 'end']:
            node = nodes_dict[node_type]
            trace_count = node.trace_counter
            
            metric_id = f"Metric:Trace_Count:{node.element_id}"
            metric = BaseNumericMetric(
                element_id=metric_id,
                plugin_metadata_id=analytics_id,
                root=workflow_id,  # Use workflow_id as root
                name="Trace Count",
                tags=[BASE_WORKFLOW_NODE_METRIC],
                description=f"Number of traces that passed through {node_type} node {node.name}",
                related_to=(
                    [workflow_id, node.element_id],  # Only TWO for start/end (no action)
                    [
                        TypeResolutionUtils.get_fully_qualified_type_name_for_type(TraceWorkflowData),
                        TypeResolutionUtils.get_fully_qualified_type_name_for_type(WorkflowNodeData)
                    ]
                ),
                value=trace_count,
                units='Count',
                attributes={
                    'node_name': node.name,
                    'node_type': node_type
                }
            )
            metrics.append(metric)
            metric_ids.append(metric_id)
    
    return metrics, metric_ids


async def discover_process_workflow_hierarchical(
    tasks: list[TaskComposite], 
    id: str, 
    use_agent_in_analysis: bool = False,
    analytics_id: str | None = None
) -> tuple[BaseTraceWorkflow, list[BaseAction], list[BaseNumericMetric], list[str]]:
    """
    Runs the full process discovery pipeline with hierarchical workflow extraction.
    FIXED: Creates NEW actions for group/aggregation views to properly establish workflow relationships.
    
    Returns:
        tuple: (
            BaseTraceWorkflow, 
            list of new BaseAction objects that need to be persisted,
            list of BaseNumericMetric objects for workflow nodes,
            list of metric element_ids
        )
    """
    if not tasks:
        raise ValueError("Cannot discover a process from an empty list of tasks.")

    tasks_by_id = {task.id: task for task in tasks}
    event_log = await tasks_to_eventlog_async(tasks)

    if event_log.empty:
        raise ValueError("Cannot generate workflow from empty event log.")

    root_id = id

    # Step 1: Collect original actions and create NEW actions for this group
    original_action_dict = {}  # name -> original action (for reference)
    new_action_dict = {}  # name -> NEW action for this group

    for task in tasks:
        action = await task.executor
        action_name = action.name

        if action_name not in original_action_dict:
            original_action_dict[action_name] = action

            # Create a NEW action instance for the group view
            # Use capital 'A' to match workflow_metric expectations
            new_action = BaseAction(
                element_id=f"Action:{action_name}#{root_id}",  # Capital 'A' - CRITICAL
                name=action_name,
                description=getattr(action, 'description', f"action for {action_name}"),
                type=getattr(action, 'type', "action"),
                tags=[tag for tag in getattr(action, 'tags', []) if tag != 'task'],
                attributes=getattr(action, 'attributes', {}),
                root=id
            )
            new_action_dict[action_name] = new_action

    # Step 2: Create workflows and workflow nodes using NEW actions
    workflow_dict = {}
    workflow_nodes = {} # Stores BaseWorkflowNode
    workflow_node_cases = defaultdict(set) # Stores case_ids for each node
    workflow_edges = {}
    all_gateway_nodes = {}
    start_end_nodes = {}
    workflow_event_logs = {}

    for task in tasks:
        if task.parent_id:
            parent_task = tasks_by_id.get(task.parent_id)
            if not parent_task:
                continue

            parent_executor = await parent_task.executor
            parent_name = parent_executor.name
            action = await task.executor
            action_name = action.name

            # Use the NEW action's element_id
            new_action = new_action_dict[action_name]
            action_id = new_action.element_id
            case_id = task.root_id or f"process_{task.id}"
            # Create Workflow
            workflow_id = f"Workflow:{parent_name}#{root_id}"
            if parent_name not in workflow_dict:
                # Get the NEW parent action
                parent_action = new_action_dict[parent_name]

                workflow_dict[parent_name] = BaseWorkflow(
                    element_id=workflow_id,
                    description=f"Workflow:{parent_name}",
                    root=root_id,
                    type="Workflow",
                    name=parent_name,
                    owner_id=parent_action.element_id,  # Points to NEW action
                    control_flow_ids=[],
                )
                workflow_event_logs[parent_name] = []

            # Create WorkflowNode
            node_id = f"WorkflowNode:{parent_name}#{action_name}#{id}"
            attributes = {}
            if task.name and ':' in task.name:
                attributes['agent_name'] = task.name.split(':')[1]

            if node_id not in workflow_nodes:
                workflow_nodes[node_id] = BaseWorkflowNode(
                    element_id=node_id,
                    root_id=root_id,
                    name=node_id,
                    description=node_id,
                    type="WorkflowNode",
                    parent_id=workflow_dict[parent_name].element_id,
                    action_id=action_id,  # Use NEW action ID
                    tags=task.tags,
                    attributes=attributes,
                    task_counter=1,
                    trace_counter=0 # Will be set below
                )
            else:
                workflow_nodes[node_id].task_counter += 1

            # Add case_id to track traces for this node
            workflow_node_cases[node_id].add(case_id)

            # Add task to workflow's event log
            workflow_event_logs[parent_name].append({
                'case_id': case_id,
                'activity': action_name,
                'agent': _find_agent_in_hierarchy(task.id, tasks_by_id, visited=set()),
                'timestamp': task.start_time,
                'action_id': action_id,
                'workflow_key': parent_name
            })

    # Set trace_counter for all task nodes
    for node_id, case_set in workflow_node_cases.items():
        if node_id in workflow_nodes:
            workflow_nodes[node_id].trace_counter = len(case_set)

    # Step 3: Apply Alpha Miner to each workflow partition
    for workflow_key, workflow_events in workflow_event_logs.items():
        if not workflow_events:
            continue

        workflow_df = pd.DataFrame(workflow_events)
        workflow_df['workflow_key'] = workflow_key

        variants = get_variants_for_workflow(workflow_df, workflow_key, use_agent_in_analysis)
        if not variants:
            continue

        footprint = create_matrix(variants)
        process_model, gateway_nodes, start_nodes_stats, end_nodes_stats = alpha_miner_with_gateway_nodes(
            footprint, workflow_key, workflow_events, root_id
        )

        # Create start and end nodes
        start_node, end_node = create_start_end_nodes(workflow_key, root_id)
        start_end_nodes[workflow_key] = {'start': start_node, 'end': end_node}

        # Create start/end edges (this also updates start/end node counters)
        start_end_edges = create_start_end_edges(
            workflow_key, root_id, start_node, end_node,
            start_nodes_stats, end_nodes_stats,
            workflow_nodes
        )

        for edge in start_end_edges:
            if edge.element_id not in workflow_edges:
                workflow_edges[edge.element_id] = edge

        # Add gateway nodes
        for gateway_node in gateway_nodes:
            gateway_node.root_id = root_id
            gateway_node.parent_id = workflow_dict[workflow_key].element_id
            all_gateway_nodes[gateway_node.element_id] = gateway_node

        # Convert ProcessEdge to BaseWorkflowEdge
        for process_edge in process_model.edges:
            def get_node_id_from_activity(activity: ActivityNode) -> str | None:
                if activity.name.startswith("Gateway:"):
                    return activity.name
                node_id = f"WorkflowNode:{workflow_key}#{activity.name}#{id}"
                if node_id in workflow_nodes:
                    return node_id
                return None

            source_id = get_node_id_from_activity(process_edge.from_activity)
            dest_id = get_node_id_from_activity(process_edge.to_activity)

            if source_id and dest_id:
                edge_id = f"WorkflowEdge:{workflow_key} from {source_id} to {dest_id}#{id}"
                relation_category = "SEQUENTIAL"
                if source_id.startswith("Gateway:"):
                    relation_category = "SPLIT"
                elif dest_id.startswith("Gateway:"):
                    relation_category = "JOIN"

                if edge_id not in workflow_edges:
                    workflow_edges[edge_id] = BaseWorkflowEdge(
                        element_id=edge_id,
                        name=edge_id,
                        description=f"Alpha Miner discovered edge: {process_edge.gateway_type}",
                        root_id=root_id,
                        type="WorkflowEdge",
                        source_category=relation_category,
                        parent_id=workflow_dict[workflow_key].element_id,
                        source_ids=[source_id],
                        destination_ids=[dest_id],
                        destination_category="SEQUENTIAL",
                        weight=process_edge.frequency,
                        trace_count=process_edge.trace_count
                    )

    # Combine all nodes
    all_nodes = list(workflow_nodes.values()) + list(all_gateway_nodes.values())
    for workflow_start_end in start_end_nodes.values():
        all_nodes.extend([workflow_start_end['start'], workflow_start_end['end']])

    # Create the trace workflow WITHOUT actions (will be set after persistence)
    trace_workflow = BaseTraceWorkflow(
        element_id=f'trace_workflow_{root_id}',
        name=f'trace_workflow_{root_id}',
        description=f'Hierarchical process model for root {root_id}',
        root=root_id,
        actions=[],  # Empty - will be set after persistence in plugin
        workflows=list(workflow_dict.values()),
        workflow_nodes=all_nodes,
        workflow_edges=list(workflow_edges.values())
    )
    
    # Create workflow node metrics if analytics_id provided
    workflow_metrics = []
    workflow_metric_ids = []
    if analytics_id:
        workflow_id = trace_workflow.element_id  # Use the trace_workflow's element_id
        workflow_metrics, workflow_metric_ids = create_workflow_node_metrics(
            workflow_nodes=workflow_nodes,
            workflow_node_cases=workflow_node_cases,
            all_gateway_nodes=all_gateway_nodes,
            start_end_nodes=start_end_nodes,
            root_id=root_id,
            analytics_id=analytics_id,
            workflow_id=workflow_id
        )
    
    # Return workflow, new actions, metrics, and metric IDs
    return trace_workflow, list(new_action_dict.values()), workflow_metrics, workflow_metric_ids

# Main entry point
async def discover_process_workflow(
    tasks: list[TaskComposite], 
    id: str, 
    use_agent_in_analysis: bool = False,
    analytics_id: str | None = None
) -> tuple[BaseTraceWorkflow, list[BaseAction], list[BaseNumericMetric], list[str]]:
    """
    Enhanced version that creates hierarchical workflows with NEW actions for group views.
    
    Returns:
        tuple: (
            BaseTraceWorkflow, 
            list of BaseAction objects that need to be persisted,
            list of BaseNumericMetric objects,
            list of metric element_ids
        )
    """
    return await discover_process_workflow_hierarchical(tasks, id, use_agent_in_analysis, analytics_id)
