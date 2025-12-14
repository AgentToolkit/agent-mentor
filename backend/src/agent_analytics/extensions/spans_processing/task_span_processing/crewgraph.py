from collections import OrderedDict
from typing import Any

from agent_analytics_common.interfaces.graph import Graph
from pydantic import BaseModel, Field

from agent_analytics.extensions.spans_processing.common.utils import *


class CrewGraph(Graph):
    """
    A graph representation of a crew, including agents and tasks.

    This class extends the base Graph class to provide specialized functionality
    for modeling crew workflows with agents and tasks as nodes, and their
    relationships as edges.
    """

    class CrewAgent(BaseModel):
        """
        Represents an agent in the crew with its capabilities and configuration.

        An agent is an entity that can perform tasks and has specific properties
        that define its behavior and capabilities.
        """
        key: str = Field(
            description='Unique key identifying the agent within the crew',
            default=''
        )
        id: str = Field(
            description='Unique identifier for the agent',
            default=''
        )
        role: str = Field(
            description='Role or function of the agent in the crew',
            default=''
        )
        verbose: bool = Field(
            description='Whether the agent should provide verbose output',
            default=False
        )
        max_iter: int | None = Field(
            description='Maximum number of iterations the agent can perform',
            default=0
        )
        max_rpm: int | None = Field(
            description='Maximum requests per minute the agent can handle',
            default=0
        )
        function_calling_llm: bool = Field(
            description='Whether the agent can call LLM functions',
            default=False
        )
        llm: str = Field(
            description='Language model configuration for the agent',
            default=''
        )
        delegation_enabled: bool = Field(
            description='Whether the agent can delegate tasks to other agents',
            default=False
        )
        allow_code_execution: bool = Field(
            description='Whether the agent is allowed to execute code',
            default=False
        )
        max_retry_limit: int = Field(
            description='Maximum number of retries for failed operations',
            default=0
        )
        tool_names: list[str] = Field(
            description='List of tools available to the agent',
            default_factory=list
        )

    class CrewTask(Graph.Node):
        """
        Represents a task in the crew workflow.

        A task is a unit of work that can be assigned to one or more agents.
        """
        key: str = Field(
            description='Unique key identifying the task within the crew',
            default=''
        )
        id: str = Field(
            description='Unique identifier for the task',
            default=''
        )
        async_execution: bool = Field(
            description='Whether the task can be executed asynchronously',
            default=False
        )
        human_input: bool = Field(
            description='Whether the task requires human input',
            default=False
        )
        agent_role: list[str] | str = Field(
            description='Role(s) of agent(s) assigned to this task',
            default=''
        )
        tool_names: list[str] = Field(
            description='List of tools required for this task',
            default_factory=list
        )
        agents: list['CrewGraph.CrewAgent'] = Field(
            description='List of agents assigned to this task',
            default_factory=list
        )

    # Main class fields
    key: str = Field(
        description='Unique key identifying the crew',
        default=''
    )
    id: str = Field(
        description='Unique identifier of the crew',
        default=''
    )
    process_type: str = Field(
        description='Type of crew execution process: sequential or hierarchical',
        default=''
    )
    crew_agents_map: dict[str, CrewAgent] = Field(
        description='Dictionary mapping agent keys to agent objects',
        default_factory=dict
    )
    crew_agent_id_key_map: dict[str, str] = Field(
        description='Dictionary mapping agent IDs to agent keys',
        default_factory=dict
    )
    crew_tasks_map: OrderedDict[str, CrewTask] = Field(
        description='Ordered dictionary mapping task keys to task objects',
        default_factory=OrderedDict
    )
    crew_tasks_id_key_map: dict[str, str] = Field(
        description='Dictionary mapping task IDs to task keys',
        default_factory=dict
    )

    @classmethod
    def from_crew_created_span(cls, crew_span: dict[str, Any]) -> 'CrewGraph':
        """
        Creates a CrewGraph instance from a crew span dictionary.

        This method parses the crew configuration from a dictionary representation
        and constructs the graph with agents and tasks as nodes.

        Args:
            crew_span: Dictionary containing crew configuration data

        Returns:
            A fully constructed CrewGraph instance
        """
        cg = cls()
        cg.key = crew_span['crew_key']
        cg.id = crew_span['crew_id']
        cg.process_type = crew_span['crew_process']

        # Add agents
        agents_raw = json.loads(crew_span['crew_agents'])
        for agent_details in agents_raw:
            cg.add_agent(agent_details)

        # Add tasks and build relationships
        tasks_raw = json.loads(crew_span['crew_tasks'])
        prev_task = None
        for task_details in tasks_raw:
            task_node = cg._create_task_node(task_details)

            # Link tasks to agents
            cg._link_task_to_agents(task_node, task_details)

            # Add task to maps
            cg.crew_tasks_map[task_node.id] = task_node
            cg.crew_tasks_id_key_map[task_node.id] = task_node.key

            # Connect to previous task in sequence
            if prev_task:
                cg.add_edge(source_names=prev_task.id, destination_names=task_node.id)
            prev_task = task_node

        return cg

    def _create_task_node(self, task_details: dict[str, Any]) -> 'CrewTask':
        """
        Creates a task node from task details.

        Args:
            task_details: Dictionary containing task configuration

        Returns:
            A CrewTask instance
        """
        task_node = self.add_node(task_details['id'], node_class=CrewGraph.CrewTask)
        task_node.key = task_details['key']
        task_node.id = task_details['id']
        task_node.async_execution = task_details['async_execution?']
        task_node.human_input = task_details['human_input?']
        task_node.agent_role = task_details['agent_role']
        task_node.tool_names = task_details['tools_names']
        return task_node

    def _link_task_to_agents(self, task_node: 'CrewTask', task_details: dict[str, Any]) -> None:
        """
        Links a task to its assigned agents.

        Args:
            task_node: The task node to link
            task_details: Dictionary containing task configuration
        """
        if isinstance(task_details['agent_key'], str):
            relevant_agents = [self.crew_agents_map[task_details['agent_key']]]
        else:
            relevant_agents = [self.crew_agents_map[agent_key] for agent_key in task_details['agent_key']]

        task_node.agents = relevant_agents
        self.add_edge(source_names=task_node.id, destination_names=[x.key for x in relevant_agents])

    def add_agent(self, agent_det_span: dict[str, Any]) -> 'CrewAgent':
        """
        Adds an agent to the crew graph.

        This method creates a CrewAgent instance from the provided details
        and adds it to the crew graph.

        Args:
            agent_det_span: Dictionary containing agent configuration data

        Returns:
            The created CrewAgent instance
        """
        # Define mapping between agent attributes and span field names
        attr_map = {
            'key': ['key'],
            'id': ['id', 'crewai.agent.id'],
            'role': ['role', 'crewai.agent.role'],
            'verbose': ['verbose?', 'crewai.agent.verbose'],
            'max_iter': ['max_iter', 'crewai.agent.max_iter'],
            'max_rpm': ['max_rpm'],
            'function_calling_llm': ['function_calling_llm'],
            'llm': ['llm', 'crewai.agent.llm'],
            'delegation_enabled': ['delegation_enabled?', 'allow_delegation'],
            'allow_code_execution': ['allow_code_execution?', 'crewai.agent.allow_code_execution'],
            'max_retry_limit': ['max_retry_limit', 'crewai.agent.max_retry_limit'],
            'tool_names': ['tool_names', 'crewai.agent.tools']
        }

        agent = self.CrewAgent()

        # Set agent attributes from span data
        for agent_attr, attr_span_options in attr_map.items():
            for attr_span_name in attr_span_options:
                if attr_span_name in agent_det_span:
                    value = self._get_agent_attribute_value(agent_attr, agent_det_span[attr_span_name])
                    setattr(agent, agent_attr, value)
                    break

            # Generate unique ID if not provided
            if agent_attr in ['key', 'id'] and not getattr(agent, agent_attr):
                setattr(agent, agent_attr, get_unique_id())

        # Add agent to maps and graph
        self.crew_agents_map[agent.key] = agent
        self.crew_agent_id_key_map[agent.id] = agent.key
        self.add_node(agent.key)

        return agent

    def _get_agent_attribute_value(self, attr_name: str, raw_value: Any) -> Any:
        """
        Processes raw attribute values for agent properties.

        Args:
            attr_name: Name of the attribute
            raw_value: Raw value from the span data

        Returns:
            Processed value appropriate for the attribute
        """
        if attr_name in ['max_iter', 'max_rpm']:
            return int(raw_value) if isinstance(raw_value, int) else raw_value
        elif attr_name == 'function_calling_llm':
            return raw_value == 'True'
        else:
            return raw_value

    def _generate_unique_id(self) -> str:
        """
        Generates a unique identifier.

        Returns:
            A unique string identifier
        """
        # Import here to avoid circular import
        from uuid import uuid4
        return str(uuid4())

    def to_node_graph(self) -> Graph:
        """
        Converts this CrewGraph to a basic Graph instance.

        Returns:
            A Graph instance with the same nodes and edges
        """
        return Graph(
            nodes=self.nodes,
            edges=self.edges,
            start_node=self.start_node,
            end_node=self.end_node
        )
