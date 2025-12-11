import json
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Any, Dict, Union
from enum import Enum
from datetime import datetime
from .elements import Element, AttributeValue

class ActionKind(str, Enum):
    """
    Defines the mechanism by which the action is performed.
    """
    TOOL = "tool"  # Action performed by invoking a registered tool, plugin, or external API
    LLM = "llm"  # Action carried out through interaction with a Large Language Model
    ML = "ml"  # Action involves running inference with a machine learning model
    VECTOR_DB = "vector_db"  # Action involves semantic search or retrieval from a vector database
    WORKFLOW = "workflow"  # Action represents a multi-step process decomposing task into sub-actions
    GUARDRAIL = "guardrail"  # Action enforces behavioral constraints or safety checks
    HUMAN = "human"  # Action performed manually by a human
    OTHER = "other"  # Action uses a mechanism not represented by the categories above

class WorkflowNodeType(str, Enum):
    """
    Types for nodes in a structured action workflow.
    """
    START = "start"  # Entry point of the workflow
    END = "end"  # Terminal node of the workflow
    INVOKE = "invoke"  # Executes a specific action or callable step
    SELECT = "select"  # Chooses among alternative paths based on decision logic
    FORK = "fork"  # Splits execution into parallel branches
    JOIN = "join"  # Merges execution paths after a fork

class CommandType(str, Enum):
    """
    Type of command within the action lifecycle.
    """
    LOAD = "load"  # Load the action's code/handler into runtime without executing
    INVOKE = "invoke"  # Execute the action once with given inputs to produce outputs
    UPDATE = "update"  # Modify the action's code or configuration
    UNLOAD = "unload"  # Unregister and unload the action's code/handler from runtime

class ActionCode(BaseModel):
    """
    Code-related attributes for an action.
    """
    id: Optional[str] = Field(None, description="Fully-qualified identifier for the code implementation")
    language: Optional[str] = Field(None, description="Programming language in which the action is implemented")
    input_schema: Optional[str] = Field(None, description="JSON Schema describing expected input structure")
    output_schema: Optional[str] = Field(None, description="JSON Schema describing output format")
    body: Optional[str] = Field(None, description="The actual source code or code snippet implementing the action")

class WorkflowEdge(BaseModel):
    """
    Edge definition for workflow structure.
    """
    from_node_index: int = Field(description="Source node index")
    to_node_index: int = Field(description="Destination node index")
    edge_type: Optional[str] = Field(None, description="Type of edge (e.g., control_flow)")

class WorkflowStructure(BaseModel):
    """
    Workflow structure definition for workflow actions.
    """
    node_types: Optional[List[WorkflowNodeType]] = Field(None, description="List of types for nodes in workflow")
    nodes_action_code_ids: Optional[List[str]] = Field(None, description="Code identifiers for actions assigned to each workflow node")
    edges: Optional[List[WorkflowEdge]] = Field(None, description="Edge definitions between nodes")

class ActionCommand(BaseModel):
    """
    Command-related attributes for action lifecycle control.
    """
    type: Optional[CommandType] = Field(None, description="Type of command within the action lifecycle")
    code_id: Optional[str] = Field(None, description="Identifier of the code element implementing the control command")

class Action(Element):
    """
    Represents an executable unit of behavior in agentic and generative AI systems.
    Actions are invoked during task lifecycle and encompass operations such as
    tool invocation, LLM interaction, workflow execution, or human decisions.
    """
    
    # Core attributes
    kind: ActionKind = Field(ActionKind.OTHER, description="Defines the mechanism by which the action is performed")
    
    # Code and implementation
    code: Optional[ActionCode] = Field(None, description="Code-related attributes for the action")
    
    # Semantics and metadata
    description: Optional[str] = Field(None, description="Human-readable summary describing what the action does")
    is_generated: Optional[bool] = Field(None, description="Whether action is generated dynamically (true) or user-initiated (false)")
    
    # Guardrails and artifacts
    guardrail_code_ids: Optional[List[str]] = Field(None, description="List of guardrail identifiers applied to this action")
    artifact_ids: Optional[List[str]] = Field(None, description="Identifiers of artifacts used as inputs or outputs")
    
    # Workflow structure (for workflow actions)
    workflow: Optional[WorkflowStructure] = Field(None, description="Workflow structure for workflow actions")
    
    # Action lifecycle and control
    command: Optional[ActionCommand] = Field(None, description="Command attributes for action lifecycle control")
    
    # Timing and execution
    start_time: Optional[datetime] = Field(None, description="When the action started execution")
    end_time: Optional[datetime] = Field(None, description="When the action completed execution")
    
    # Input/Output
    input: Optional[Any] = Field(None, description="Action input data")
    output: Optional[Any] = Field(None, description="Action output data")
    
    # Status and errors
    status: Optional[str] = Field(None, description="Current status of the action")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered during execution")
    
    
    @model_validator(mode='after')
    def validate_workflow_consistency(self):
        """Validate workflow structure consistency if present."""
        if self.workflow:
            if self.workflow.node_types and self.workflow.nodes_action_code_ids:
                if len(self.workflow.node_types) != len(self.workflow.nodes_action_code_ids):
                    raise ValueError("workflow.node_types and workflow.nodes_action_code_ids must have same length")
        return self
    
    @model_validator(mode='after')
    def validate_command_requirement(self):
        """Validate command type is present when kind is command."""
        if self.kind == ActionKind.WORKFLOW and not self.workflow:
            # Workflow actions should have workflow structure, but not required
            pass
        return self
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Action':
        """Create an action from a dictionary"""
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Action':
        """Create an action from a JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def to_otel_attributes(self) -> Dict[str, AttributeValue]:
        """
        Convert action to OpenTelemetry semantic attributes format.
        Returns a dictionary with gen_ai.action.* prefixed keys.
        """
        attrs = {}
        
        # Required attributes
        attrs["gen_ai.action.kind"] = self.kind.value
        
        # Code attributes
        if self.code:
            if self.code.id:
                attrs["gen_ai.action.code.id"] = self.code.id
            if self.code.language:
                attrs["gen_ai.action.code.language"] = self.code.language
            if self.code.input_schema:
                attrs["gen_ai.action.code.input_schema"] = self.code.input_schema
            if self.code.output_schema:
                attrs["gen_ai.action.code.output_schema"] = self.code.output_schema
            if self.code.body:
                attrs["gen_ai.action.code.body"] = self.code.body
        
        # Semantics and metadata
        if self.description:
            attrs["gen_ai.action.description"] = self.description
        if self.is_generated is not None:
            attrs["gen_ai.action.is_generated"] = self.is_generated
        
        # Guardrails and artifacts
        if self.guardrail_code_ids:
            attrs["gen_ai.action.guardrail.code.ids"] = self.guardrail_code_ids
        if self.artifact_ids:
            attrs["gen_ai.action.artifact.ids"] = self.artifact_ids
        
        # Workflow structure
        if self.workflow:
            if self.workflow.node_types:
                attrs["gen_ai.action.workflow.node.types"] = [node_type.value for node_type in self.workflow.node_types]
            if self.workflow.nodes_action_code_ids:
                attrs["gen_ai.action.workflow.nodes.action.code.ids"] = self.workflow.nodes_action_code_ids
            if self.workflow.edges:
                from_indexes = []
                to_indexes = []
                edge_types = []
                for edge in self.workflow.edges:
                    from_indexes.append(edge.from_node_index)
                    to_indexes.append(edge.to_node_index)
                    if edge.edge_type:
                        edge_types.append(edge.edge_type)
                attrs["gen_ai.action.workflow.edge.from.node.indexes"] = from_indexes
                attrs["gen_ai.action.workflow.edge.to.node.indexes"] = to_indexes
                if edge_types:
                    attrs["gen_ai.action.workflow.edge.type"] = edge_types
        
        # Command attributes
        if self.command:
            if self.command.type:
                attrs["gen_ai.action.command.type"] = self.command.type.value
            if self.command.code_id:
                attrs["gen_ai.action.command.code.id"] = self.command.code_id
        
        # Additional attributes not in OTEL spec but useful
        if self.name:
            attrs["gen_ai.action.name"] = self.name
        if self.tags:
            attrs["gen_ai.action.tags"] = [str(tag) for tag in self.tags]
        if self.element_id:
            attrs["gen_ai.action.id"] = self.element_id
        
        return attrs
    
    def set_code(self, id: Optional[str] = None, language: Optional[str] = None, 
                 input_schema: Optional[Union[str, dict]] = None, 
                 output_schema: Optional[Union[str, dict]] = None,
                 body: Optional[str] = None) -> None:
        """
        Helper method to set code attributes.
        Automatically converts dict schemas to JSON strings.
        """
        if not self.code:
            self.code = ActionCode()
        
        if id is not None:
            self.code.id = id
        if language is not None:
            self.code.language = language
        if input_schema is not None:
            self.code.input_schema = json.dumps(input_schema) if isinstance(input_schema, dict) else input_schema
        if output_schema is not None:
            self.code.output_schema = json.dumps(output_schema) if isinstance(output_schema, dict) else output_schema
        if body is not None:
            self.code.body = body
    
    def set_workflow(self, node_types: List[WorkflowNodeType], 
                     nodes_action_code_ids: Optional[List[str]] = None,
                     edges: Optional[List[WorkflowEdge]] = None) -> None:
        """
        Helper method to set workflow structure.
        """
        if not self.workflow:
            self.workflow = WorkflowStructure()
        
        self.workflow.node_types = node_types
        if nodes_action_code_ids:
            self.workflow.nodes_action_code_ids = nodes_action_code_ids
        if edges:
            self.workflow.edges = edges
    
    def add_workflow_edge(self, from_index: int, to_index: int, edge_type: Optional[str] = None) -> None:
        """
        Helper method to add a workflow edge.
        """
        if not self.workflow:
            self.workflow = WorkflowStructure()
        if not self.workflow.edges:
            self.workflow.edges = []
        
        edge = WorkflowEdge(from_node_index=from_index, to_node_index=to_index, edge_type=edge_type)
        self.workflow.edges.append(edge)
    
    def set_command(self, type: CommandType, code_id: Optional[str] = None) -> None:
        """
        Helper method to set command attributes.
        """
        if not self.command:
            self.command = ActionCommand()
        
        self.command.type = type
        if code_id:
            self.command.code_id = code_id
    
    def add_guardrail(self, guardrail_code_id: str) -> None:
        """
        Helper method to add a guardrail.
        """
        if not self.guardrail_code_ids:
            self.guardrail_code_ids = []
        self.guardrail_code_ids.append(guardrail_code_id)
    
    def add_artifact(self, artifact_id: str) -> None:
        """
        Helper method to add an artifact.
        """
        if not self.artifact_ids:
            self.artifact_ids = []
        self.artifact_ids.append(artifact_id)