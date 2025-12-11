from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Any, Dict, Union, Set
import json

class Graph(BaseModel):
    class Node(BaseModel):
        node_name: str
        outgoing_edges: List['Graph.Edge'] = Field(default_factory=list)
        incoming_edges: List['Graph.Edge'] = Field(default_factory=list)

        def __repr__(self):
            return f"Node({self.node_name})"

    class Edge(BaseModel):
        sources: List['Graph.Node']
        destinations: List['Graph.Node']

        # Custom validator to ensure the sources and destinations are linked properly
        @model_validator(mode='after')
        def link_sources_to_destinations(self):
            for source in self.sources:
                source.outgoing_edges.append(self)  # Link source to the edge
            for destination in self.destinations:
                destination.incoming_edges.append(self)  # Link edge to the destination
            return self

        def __repr__(self):
            source_names = [node.node_name for node in self.sources]
            destination_names = [node.node_name for node in self.destinations]
            return f"Edge(sources={source_names}, destinations={destination_names})"

        def __hash__(self):
            return hash(str(id(self)))

    nodes: Dict[str, 'Graph.Node'] = Field(default_factory=dict)
    edges: Set['Graph.Edge'] = Field(default_factory=set)
    start_node: 'Graph.Node' = None
    end_node: 'Graph.Node' = None

    def __init__(self, **data):
        super().__init__(**data)
        self.start_node = self.add_node("__start__")
        self.end_node = self.add_node("__end__")

    def add_node(self, node_name: str, node_class: 'Graph.Node'=None) -> 'Graph.Node':
        """Adds a node to the graph with the given function name."""
        if node_name in self.nodes:
            raise ValueError(f"Node with function name '{node_name}' already exists.")

        node_class = node_class if node_class else Graph.Node
        new_node = node_class(node_name=node_name)
        self.nodes[node_name] = new_node
        return new_node

    def add_edge(self, source_names: Union[str, tuple[str]], destination_names: Union[str, tuple[str]]) -> 'Graph.Edge':
        """Adds an edge to the graph with the given sources and destinations."""
        sources = []
        if isinstance(source_names, str):
            sources.append(self.nodes[source_names])
        else:
            for name in source_names:
                if name not in self.nodes:
                    raise ValueError(f"Source node '{name}' not found.")
                sources.append(self.nodes[name])

        destinations = []
        if isinstance(destination_names, str):
            destinations.append(self.nodes[destination_names])
        else:
            for name in destination_names:
                if name not in self.nodes:
                    raise ValueError(f"Destination node '{name}' not found.")
                destinations.append(self.nodes[name])

        new_edge = Graph.Edge(sources=sources, destinations=destinations)
        self.edges.add(new_edge)
        return new_edge

    def get_node(self, node_name: str) -> Optional['Graph.Node']:
        """Gets a node by function name."""
        return self.nodes.get(node_name)

    def __repr__(self):
        return f"Graph with nodes: {list(self.nodes.keys())}"

    def to_dict(self):
        node_names = []
        for node in self.nodes.values():
            if node.node_name not in ["__start__", "__end__"]:
                node_names.append(node.node_name)
        edges = []
        for edge in self.edges:
            source = [node.node_name for node in edge.sources]
            destinations = [node.node_name for node in edge.destinations]
            edges.append([source, destinations])

        return {
            "nodes": node_names,
            "edges": edges
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Graph':
        graph = cls()
        if "nodes" in data:
            for node_name in data["nodes"]:
                graph.add_node(node_name)
        if "edges" in data:
            for edge_data in data["edges"]:
                graph.add_edge(edge_data[0], edge_data[1])
        return graph

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=4)

    @classmethod
    def from_json(cls, json_str: str) -> 'Graph':
        data = json.loads(json_str)
        return cls.from_dict(data)
