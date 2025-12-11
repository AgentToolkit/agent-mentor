from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from agent_analytics.extensions.spans_processing.common.utils import get_unique_id


class Node(BaseModel):
    id: str = Field(description='The unique identifier of the task')
    name: str = Field(description='The unique name of the task')
    total_executions: int = Field(description='total amount of executions in the flow', default=0)
    current_execution: int = Field(description='counter marking the current execution of the node', default=1)
    incoming_nodes: list[Any] = Field(description='A list of nodes with an edge to the current node', default=[])
    outgoing_nodes: list[Any] = Field(description='A list of nodes with an edge from the current node', default=[])

    incoming_cond_nodes: list[Any] = Field(description='A list of conditional nodes with an edge to the current node', default=[])
    outgoing_cond_nodes: list[Any] = Field(description='A list of conditional nodes with an edge from the current node', default=[])
    outgoing_cond_paths: list[Any] = Field(description='A list of function names deciding the path of outgoing conditional nodes', default=[])
    outgoing_cond_path_maps: list[Any] = Field(description='A list of maps for each outgoing conditional nodes', default=[])

    metadata: dict[str, Any] = Field(description='A dictionary for additional metadata associated with the node', default={})

    def get_indegree(self):
        return np.sum(self.incoming_nodes != '__start__') + np.sum(self.incoming_cond_nodes != '__start__')

    def get_all_incoming_nodes(self):
        incm_nodes = np.array(self.incoming_nodes + self.incoming_cond_nodes)
        return np.unique([node for node in incm_nodes if node.name != '__start__'])

    def get_all_outgoing_nodes(self):
        return self.outgoing_nodes + self.outgoing_cond_nodes


class Graph(BaseModel):
    nodes: dict[str, Node] = Field(description='dictionary containing all node names and objects in the graph', default={})
    root_node: Node = Field(description='starting point of each invokation', default=None)
    id: str = Field(description='unique id of the graph', default='')
    metadata: dict[str, Any] = Field(description='A dictionary for additional metadata associated with the graph', default={})

    parent_graph_id: str | None = Field(description='unique id of the creator/parent graph', default='')
    parent_graph_node_name: str | None = Field(description='node name of creator/parent', default='')

    def add_node(self, node_name: str):
        self.nodes[node_name] = Node(id=get_unique_id(), name=node_name)
        return self.nodes[node_name]

    def fetch(self, node_name: str, create_otherwise=True):
        if node_name in self.nodes.keys():
            return self.nodes[node_name]
        if create_otherwise:
            return self.add_node(node_name)
        else:
            return None

    def update_total_executions(self):
        for node in self.nodes.values():
            node.total_executions = node.current_execution


class DependantGraphs(BaseModel):
    graphs: dict[str, Graph] = Field(description='dictionary containing graph id as keys and graph object as values', default={})

    # def add_graph(self):
    #     pass

    def get_counted_name(self, node_name: str, update_counters: bool = True):
        curr_counter = 0
        for g in self.graphs.values():
            if node_name in g.nodes.keys():
                curr_counter = g.nodes[node_name].current_execution
                if update_counters:
                    g.nodes[node_name].current_execution += 1
        return f'{node_name}_#{curr_counter}'

    def fetch_node(self, node_name: str, graph_id: str):
        return self.graphs[graph_id].nodes.get(node_name, None)

    def finalize(self):
        # TODO: update total_executions in all nodes
        pass
