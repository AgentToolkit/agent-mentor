import json
from typing import List, Dict, Set
from agent_analytics.core.data_composite.trace_workflow import TraceWorkflowComposite
from agent_analytics.core.data_composite.workflow_edge import WorkflowEdgeComposite
from agent_analytics.core.data_composite.workflow_node import WorkflowNodeComposite
from agent_analytics.core.data_composite.workflow_edge import WorkflowEdgeComposite

async def rebuild_action_workflow_mapping(workflow: TraceWorkflowComposite):
    """
    Rebuild the action-to-workflow mapping that may be lost during aggregation.
    This creates a lookup dictionary to resolve workflows for actions.
    
    Returns:
        Dict mapping action element_ids to their workflow objects
    """
    actions = await workflow.get_actions()
    workflows = await workflow.workflows
    
    # Create mapping from action ID to workflow
    action_to_workflow = {}
    
    for wf in workflows:
        if wf.owner_id:
            # owner_id format is typically "Action:name" or just the action element_id
            action_to_workflow[wf.owner_id] = wf
    
    return action_to_workflow


async def get_trace_ids_for_node(node: WorkflowNodeComposite) -> Set[str]:
    """
    Extract trace IDs from the node's metrics.
    
    Returns:
        Set of unique trace IDs that passed through this node
    """
    trace_ids = set()
    
    try:
        # Get the metrics for this node
        metrics = await node.metrics
        
        for metric in metrics:
            # Look for the "Trace Count" metric
            if metric.name == "Trace Count" and hasattr(metric, 'attributes'):
                attributes = metric.attributes
                if isinstance(attributes, dict) and 'trace_ids' in attributes:
                    trace_ids_list = attributes['trace_ids']
                    if isinstance(trace_ids_list, list):
                        trace_ids.update(trace_ids_list)
    except Exception as e:
        # If we can't get metrics, fall back to empty set
        print(f"Warning: Could not get trace IDs for node {node.element_id}: {e}")
    
    return trace_ids


async def get_trace_ids_for_edge(edge: WorkflowEdgeComposite) -> Set[str]:
    """
    Extract trace IDs from the edge's metrics.
    
    Returns:
        Set of unique trace IDs that passed through this edge
    """
    trace_ids = set()
    
    try:
        # Get the metrics for this edge
        metrics = await edge.metrics
        
        for metric in metrics:
            # Look for trace-related metrics
            if hasattr(metric, 'attributes'):
                attributes = metric.attributes
                if isinstance(attributes, dict) and 'trace_ids' in attributes:
                    trace_ids_list = attributes['trace_ids']
                    if isinstance(trace_ids_list, list):
                        trace_ids.update(trace_ids_list)
    except Exception as e:
        # If we can't get metrics, fall back to empty set
        print(f"Warning: Could not get trace IDs for edge {edge.element_id}: {e}")
    
    return trace_ids


async def transform_workflow(workflow: TraceWorkflowComposite):
    # Create lookup dictionaries for easier access
    actions = await workflow.get_actions()
    actions_by_id = { action.element_id: action for action in actions}
    # CRITICAL FIX: Build action-to-workflow mapping for aggregated views
    action_to_workflow_map = await rebuild_action_workflow_mapping(workflow)
    workflow_nodes = await workflow.workflow_nodes
    workflow_nodes_by_id = {n.element_id: n for n in workflow_nodes}

    # Group workflow nodes by parent workflow
    nodes_by_workflow = {}
    entry_nodes = {}
    for node in workflow_nodes:
        if node.parent_id:
            workflow_id = node.parent_id
            if workflow_id not in nodes_by_workflow:
                nodes_by_workflow[workflow_id] = []
            nodes_by_workflow[workflow_id].append(node)
        else:
            entry_nodes[node.element_id] = node

    # Group workflow edges by parent workflow
    edges_by_workflow = {}
    workflow_edges = await workflow.workflow_edges
    for edge in workflow_edges:
        if edge.parent_id:
            workflow_id = edge.parent_id
            if workflow_id not in edges_by_workflow:
                edges_by_workflow[workflow_id] = []
            edges_by_workflow[workflow_id].append(edge)

    # Function to get action name from ID
    def get_action_name(action_id):
        if action_id in actions_by_id:
            return actions_by_id[action_id].name
        # Extract name part from ID (format: "Action:name")
        return action_id.split(":")[-1] if ":" in action_id else action_id

    # Track all processed action IDs to avoid duplicating nested graphs
    processed_actions = {}

    # Function to build a nested graph for a workflow
    async def build_nested_graph(workflow_id, visited_workflows=None, parent_id=None):
        if visited_workflows is None:
            visited_workflows = set()

        # Prevent infinite recursion
        if workflow_id in visited_workflows:
            return None
        visited_workflows.add(workflow_id)

        # Get nodes for this workflow
        workflow_nodes: list[WorkflowNodeComposite] = nodes_by_workflow.get(workflow_id, [])
        if not workflow_nodes:
            return None

        output_nodes = []

        # Create output nodes
        for node in workflow_nodes:
            action_id = node.action_id
            
            # Get trace IDs for this specific node
            node_trace_ids = await get_trace_ids_for_node(node)
            
            if action_id not in actions_by_id:
                output_node = {
                    "id": node.element_id,
                    "parentId": parent_id,
                    "name": action_id.split(':'),  # Capitalize first letter #[-1],
                    "hits": node.task_counter,
                    "traces": len(node_trace_ids),  # Count of unique traces
                    "trace_ids": list(node_trace_ids),  # Store the actual trace IDs
                    "nestedGraph": None,
                    "type": node.type if node.type else 'task' 
                }
                output_nodes.append(output_node)
                continue

            action = actions_by_id[action_id]
            node_name = action.name

            # Check if this action has already been processed
            nested_graph = None
            is_reference = False
            
            # CRITICAL FIX: Check if this action has a nested workflow using the mapping
            nested_workflow_id = None
            
            # First try the direct relationship
            try:
                workflow_obj = await action.workflow
                if workflow_obj is not None:
                    nested_workflow_id = workflow_obj.element_id
            except:
                pass
            
            # FALLBACK: Use the manual mapping if direct relationship fails
            if nested_workflow_id is None and action_id in action_to_workflow_map:
                workflow_obj = action_to_workflow_map[action_id]
                nested_workflow_id = workflow_obj.element_id if workflow_obj is not None else None
            
            reference_to = None
            if nested_workflow_id:
                if action_id in processed_actions:
                    # This action has been processed before, create a reference
                    is_reference = True
                    # Set the reference to the original node
                    reference_to = processed_actions[action_id]
                else:
                    # First time seeing this action, process its nested graph
                    new_visited = visited_workflows.copy()
                    nested_graph = await build_nested_graph(nested_workflow_id, new_visited, action_id)
                    # Store this action as processed
                    processed_actions[action_id] = node_name

            # Create the output node
            output_node = {
                "id": node.element_id,
                "parentId": parent_id,
                "name": node_name.capitalize() if node_name else "",
                "hits": node.task_counter,
                "traces": len(node_trace_ids),  # Count of unique traces
                "trace_ids": list(node_trace_ids),  # Store the actual trace IDs
                "nestedGraph": nested_graph,
                "type": node.type if node.type else 'task'
            }

            # Add reference information if this is a reference node
            if is_reference:
                output_node["isReference"] = True
                output_node["referenceTo"] = reference_to

            output_nodes.append(output_node)

        # Create output edges with arrays for sources and targets
        output_edges = []
        current_workflow_edges: list[WorkflowEdgeComposite] = edges_by_workflow.get(workflow_id, [])

        for edge in current_workflow_edges:
            source_node_ids = edge.source_ids
            destination_node_ids = edge.destination_ids
            
            # Get trace IDs for this edge
            edge_trace_ids = await get_trace_ids_for_edge(edge)

            # Create individual edges for every source-to-target combination
            for source_id in source_node_ids:
                if source_id not in workflow_nodes_by_id: continue
                source_action_id = source_id

                for dest_id in destination_node_ids:
                    if dest_id not in workflow_nodes_by_id: continue
                    dest_action_id = dest_id

                    # Create one edge for this specific pair
                    output_edge = {
                        "source": source_action_id,
                        "target": dest_action_id,
                        # Rename 'hits' to 'weight' to match Cytoscape component's expectation
                        "weight": int(edge.weight) if isinstance(edge.weight, (int, float)) else 0,
                        "hits": int(edge.weight) if isinstance(edge.weight, (int, float)) else 0,
                        "traces": len(edge_trace_ids),  # Count of unique traces
                        "trace_ids": list(edge_trace_ids)  # Store the actual trace IDs
                    }
                    output_edges.append(output_edge)

        return {
            "id": workflow_id,
            "nodes": output_nodes,
            "edges": output_edges
        }

    # Find the root workflow
    root_workflow = None
    workflows = await workflow.workflows
    for workflow_item in workflows:
        if workflow_item.name and "_ROOT" in workflow_item.name:
            root_workflow = workflow_item
            break

    if not root_workflow:
        return {"id": "empty", "nodes": [], "edges": []}

    # Generate the output starting from the root workflow
    output = await build_nested_graph(root_workflow.element_id)
    return output if output else {"id": "empty-root", "nodes": [], "edges": []}


def merge_workflows(workflow_list):
    """
    Merge multiple workflow representations into a single workflow.
    
    Args:
        workflow_list: List of workflow objects, each with a 'workflow' field containing 'nodes' and 'edges'
        
    Returns:
        A merged workflow object with combined nodes and edges
    """
    if not workflow_list:
        return {"workflow": {"nodes": [], "edges": []}}

    # Initialize the merged result
    merged_result = {
        "workflow": {
            "nodes": [],
            "edges": []
        }
    }

    # Maps to track merged nodes and edges
    # Key: (parent_path, node_name, node_type) -> merged_node
    merged_nodes_map = {}
    # Key: (parent_path, source_name, target_name, edge_type) -> merged_edge
    merged_edges_map = {}
    # Map to track ID mappings: original_id -> merged_node for current workflow
    id_to_merged_node = {}

    # Process each workflow
    for workflow in workflow_list:
        id_to_merged_node.clear()  # Clear for each workflow
        process_graph(workflow, None, "", merged_nodes_map, merged_edges_map,
                     id_to_merged_node, merged_result["workflow"])

    return merged_result


def process_graph(graph, parent_node, parent_path, merged_nodes_map, merged_edges_map,
                 id_to_merged_node, result_graph):
    """
    Recursively process a graph structure, merging nodes and edges based on name and path.
    
    Args:
        graph: The current graph level to process
        parent_node: The parent node of this graph (None for top level)
        parent_path: String path representing the location in the hierarchy
        merged_nodes_map: Map of (parent_path, node_name, node_type) to merged nodes
        merged_edges_map: Map of edge keys to merged edges
        id_to_merged_node: Map of original IDs to merged nodes for current workflow
        result_graph: The graph where we're adding results
    """
    if not graph:
        return

    # Create result structures if they don't exist
    if "nodes" not in result_graph:
        result_graph["nodes"] = []
    if "edges" not in result_graph:
        result_graph["edges"] = []

    # Process all nodes in this graph
    for node in graph.get("nodes", []):
        node_name = node["name"]
        node_type = node.get("type", "task")
        
        # Use deterministic ID based on path, name, and type
        deterministic_id = f"MergedNode:{parent_path}:{node_name}:{node_type}" if parent_path else f"MergedNode:{node_name}:{node_type}"
        
        # Create node key including type to distinguish nodes with same name but different types
        node_key = (parent_path, node_name, node_type)
        
        # Check if we've seen this node (by name, path, and type) before
        if node_key in merged_nodes_map:
            # Update existing node's hit count and merge trace IDs
            existing_node = merged_nodes_map[node_key]
            existing_node["hits"] += node["hits"]
            
            # Merge trace IDs as sets to avoid duplicates
            existing_trace_ids = set(existing_node.get("trace_ids", []))
            new_trace_ids = set(node.get("trace_ids", []))
            merged_trace_ids = existing_trace_ids.union(new_trace_ids)
            
            existing_node["trace_ids"] = list(merged_trace_ids)
            existing_node["traces"] = len(merged_trace_ids)  # Update count to reflect unique traces
            
            # Map the original ID to the existing merged node
            id_to_merged_node[node["id"]] = existing_node

            # If the node has a nested graph, process it recursively
            if node.get("nestedGraph") and existing_node.get("nestedGraph"):
                new_parent_path = f"{parent_path}:{node_name}" if parent_path else node_name
                process_graph(
                    node["nestedGraph"],
                    existing_node,
                    new_parent_path,
                    merged_nodes_map,
                    merged_edges_map,
                    id_to_merged_node,
                    existing_node["nestedGraph"]
                )
        else:
            # Create a new merged node with deterministic ID and preserve all original attributes
            import uuid
            new_node_id = f"Merged-{str(uuid.uuid4())}"

            new_node = {
                "id": deterministic_id,
                "parentId": parent_node["id"] if parent_node else None,
                "name": node_name,
                "hits": node["hits"],
                "traces": node.get("traces", 0),
                "trace_ids": node.get("trace_ids", []),  # Store trace IDs
                "type": node_type,
                "originalId": node.get("id"),
                "isReference": node.get("isReference", False),
                "referenceTo": node.get("referenceTo")
            }

            # Add to merged nodes map
            merged_nodes_map[node_key] = new_node

            # Map the original ID to the new merged node
            id_to_merged_node[node["id"]] = new_node

            # Add to result
            result_graph["nodes"].append(new_node)

            # Process nested graph if it exists
            if node.get("nestedGraph"):
                new_node["nestedGraph"] = {"nodes": [], "edges": []}
                new_parent_path = f"{parent_path}:{node_name}" if parent_path else node_name
                process_graph(
                    node["nestedGraph"],
                    new_node,
                    new_parent_path,
                    merged_nodes_map,
                    merged_edges_map,
                    id_to_merged_node,
                    new_node["nestedGraph"]
                )
            else:
                new_node["nestedGraph"] = None

            # Handle reference nodes
            if node.get("isReference"):
                new_node["isReference"] = True
                new_node["referenceTo"] = node.get("referenceTo")

    # Process all edges in this graph after all nodes are processed
    for edge in graph.get("edges", []):
        # Handle both old format (single source/target) and new format (arrays)
        source_ids = edge["source"] if isinstance(edge["source"], list) else [edge["source"]]
        target_ids = edge["target"] if isinstance(edge["target"], list) else [edge["target"]]
        
        # Get the source and target node names by looking up their IDs
        source_names = []
        target_names = []
        
        for source_id in source_ids:
            if source_id in id_to_merged_node:
                source_names.append(id_to_merged_node[source_id]["name"])
        
        for target_id in target_ids:
            if target_id in id_to_merged_node:
                target_names.append(id_to_merged_node[target_id]["name"])

        if not source_names or not target_names:
            continue  # Skip if we can't resolve the node names

        # Create edge key based on names and path
        source_names_key = tuple(sorted(source_names))
        target_names_key = tuple(sorted(target_names))
        edge_type = edge.get("type", "default")
        edge_key = (parent_path, source_names_key, target_names_key, edge_type)

        # Check if this edge already exists
        if edge_key in merged_edges_map:
            # Update hit count and weight, merge trace IDs
            existing_edge = merged_edges_map[edge_key]
            existing_edge["hits"] += edge.get("hits", 0)
            existing_edge["weight"] += edge.get("weight", 0)
            
            # Merge trace IDs as sets to avoid duplicates
            existing_trace_ids = set(existing_edge.get("trace_ids", []))
            new_trace_ids = set(edge.get("trace_ids", []))
            merged_trace_ids = existing_trace_ids.union(new_trace_ids)
            
            existing_edge["trace_ids"] = list(merged_trace_ids)
            existing_edge["traces"] = len(merged_trace_ids)  # Update count to reflect unique traces
        else:
            # Create new edge with merged node IDs
            source_merged_ids = [id_to_merged_node[sid]["id"] for sid in source_ids 
                               if sid in id_to_merged_node]
            target_merged_ids = [id_to_merged_node[tid]["id"] for tid in target_ids 
                               if tid in id_to_merged_node]

            new_edge = {
                "source": source_merged_ids[0] if len(source_merged_ids) == 1 else source_merged_ids,
                "target": target_merged_ids[0] if len(target_merged_ids) == 1 else target_merged_ids,
                "type": edge_type,
                "hits": edge.get("hits", 0),
                "weight": edge.get("weight", 0),
                "traces": edge.get("traces", 0),
                "trace_ids": edge.get("trace_ids", [])  # Store trace IDs
            }

            merged_edges_map[edge_key] = new_edge
            result_graph["edges"].append(new_edge)


def merge_workflow_objects(workflow_object_list):
    """
    Wrapper function that extracts the workflow field from each object
    and passes the list to merge_workflows.
    
    Args:
        workflow_object_list: List of objects, each potentially containing a 'workflow' field
        
    Returns:
        A merged workflow object
    """
    # Extract the workflow field from each object
    workflow_list = []
    for obj in workflow_object_list:
        if isinstance(obj, dict) and "workflow" in obj:
            workflow_list.append(obj["workflow"])

    # Merge the workflows
    merged = {
        "workflow": merge_workflows(workflow_list)["workflow"]
    }
    
    return merged