import json
import os
import re
from typing import Any

from agent_analytics_common.interfaces.annotations import DataAnnotation
from pydantic import BaseModel, Field

from agent_analytics.core.data.base_data_manager import DataManager
from agent_analytics.core.data_composite.annotation import BaseAnnotation
from agent_analytics.core.data_composite.base_trace import BaseTraceComposite

# Import our specific models
from agent_analytics.core.data_composite.task import TaskComposite
from agent_analytics.core.data_composite.trace_group import TraceGroupComposite
from agent_analytics.core.plugin.base_plugin import (
    BaseAnalyticsPlugin,
    ExecutionError,
    ExecutionResult,
    ExecutionStatus,
)

show_system_prompt = os.getenv('SHOW_SYSTEM_PROMPT', '').lower() in ('true', '1', 'yes', 'on')


class PatternAnnotationInput(BaseModel):
    trace_id: str | None = Field(None, description="Single trace ID")
    trace_group_id: str | None = Field(None, description="ID of trace group")


class PatternAnnotationOutput(BaseModel):
    annotations: list[dict[str, Any]] = Field(..., description="List of annotations extracted")
    trace_id: str | None = Field(None, description="Single trace ID")
    trace_group_id: str | None = Field(None, description="ID of trace group")


def extract_react_components_with_indices(content: str) -> list[dict[str, Any]]:
    """
    Extract Thought, Action, and Observation components from content string with their indices.

    Args:
        content: String content to parse

    Returns:
        List of dictionaries containing the component type, content, and indices
    """
    components = []

    # Regular expressions for each component
    thought_pattern = re.compile(r'Thought:.*?(?=Thought:|Action:|Observation:|$)', re.DOTALL | re.IGNORECASE)
    action_pattern = re.compile(r'Action:.*?(?=Thought:|Action:|Observation:|$)', re.DOTALL | re.IGNORECASE)
    observation_pattern = re.compile(r'Observation:.*?(?=Thought:|Action:|Observation:|$)', re.DOTALL | re.IGNORECASE)

    for match in thought_pattern.finditer(content):
        components.append({
            "type": DataAnnotation.Type.THOUGHT,
            "start": match.start() + len(DataAnnotation.Type.THOUGHT) + 2, # plus 2 because of ': '
            "end": match.end()
        })

    for match in action_pattern.finditer(content):
        components.append({
            "type": DataAnnotation.Type.ACTION,
            "start": match.start() + len(DataAnnotation.Type.ACTION) + 2, # plus 2 because of ': ',
            "end": match.end()
        })

    for match in observation_pattern.finditer(content):
        components.append({
            "type": DataAnnotation.Type.OBSERVATION,
            "start": match.start() + len(DataAnnotation.Type.OBSERVATION) + 2, # plus 2 because of ': ',
            "end": match.end()
        })

    components.sort(key=lambda x: x['start'])

    return components


class PatternAnnotationPlugin(BaseAnalyticsPlugin):

    @classmethod
    def get_input_model(cls) -> type[PatternAnnotationInput]:
        return PatternAnnotationInput

    @classmethod
    def get_output_model(cls) -> type[PatternAnnotationOutput]:
        return PatternAnnotationOutput

    async def _execute(
        self,
        analytics_id: str,
        data_manager: DataManager,
        input_data: PatternAnnotationInput,
        config: dict[str, Any]
    ) -> ExecutionResult:
        trace_id = input_data.trace_id
        trace_group_id = input_data.trace_group_id

        if not trace_id and not trace_group_id:
            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="InputError",
                    message="Either trace_id or trace_group_id must be provided"
                )
            )

        if trace_group_id and trace_id:
            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="InputError",
                    message="Only one of trace_group_id or trace_id can be provided"
                )
            )


        trace_ids = None
        if trace_group_id:
            trace_group = await TraceGroupComposite.get_by_id(data_manager=data_manager,id=trace_group_id)
            if not trace_group:
                return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="InputError",
                    message="The trace group for the provided trace_group_id doesn't exist"
                )
            )
            trace_ids = trace_group.traces_ids
            if trace_ids is None or len(trace_ids) == 0:
                return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="InputError",
                    message="No traces for the provided trace group id exists"
                )
            )

        trace_ids = trace_ids or [trace_id]

        try:

            # ---------------------------
            # Step 1: Fetch tasks and their associated spans
            # ---------------------------
            tasks : list[TaskComposite] = []

            for specific_trace_id in trace_ids:
                # Fetch the task
                if specific_trace_id:
                    tasks_for_trace = await BaseTraceComposite.get_tasks_for_trace(data_manager=data_manager,trace_id=specific_trace_id)
                    if not tasks_for_trace:
                        continue

                    tasks = tasks + tasks_for_trace

            if not tasks:
                return ExecutionResult(
                    analytics_id=analytics_id,
                    status=ExecutionStatus.FAILURE,
                    error=ExecutionError(
                        error_type="DataError",
                        message="No tasks found for provided task_id(s)"
                    )
                )

            # ---------------------------
            # Step 2: Process spans to extract annotations
            # ---------------------------
            all_annotations = []
            root_element_id = -1
            task_dict = {}
            next_min_prompt_index = 0

            for task in tasks:
                task_dict[task.id] = task
                if not task.parent_id:
                    root_element_id = task.id

                # Get the task root_id
                latest_prompt_key = None
                latest_prompt_index = -1

                annot_str, max_prompt_index = self.extract_annot_str(task, show_system_prompt=show_system_prompt, min_prompt_index=next_min_prompt_index)
                if annot_str != "":
                    primary_task = task
                    while primary_task.parent_id != root_element_id:
                        primary_task = task_dict[primary_task.parent_id]
                    all_annotations.append(self.create_annotations(primary_task, task, DataAnnotation.Type.PROMPT, "", annot_str))

                # Update the next minimum prompt index for the next iteration
                if max_prompt_index >= 0:
                    next_min_prompt_index = max_prompt_index + 1

                # Check if this is a milvus.search task
                if self.is_milvus_search_task(task):
                    rag_annotation = await self.create_rag_annotation(task)
                    if rag_annotation:
                        all_annotations.append(rag_annotation)

                prior_annotations = await task.related_annotations()
                if not self.has_prior_thoughts_actions_observations(prior_annotations):
                    for key in task.input:
                        # Check for prompt content keys
                        prompt_match = re.match(r'gen_ai\.prompt\.(\d+)\.content', key)
                        if prompt_match:
                            index = int(prompt_match.group(1))
                            if index > latest_prompt_index:
                                latest_prompt_index = index
                                latest_prompt_key = key
                    if latest_prompt_key and latest_prompt_key in task.input:
                        prompt_content = task.input[latest_prompt_key]
                        all_annotations.extend(await self.extract_and_store_annotations(task, latest_prompt_key, prompt_content))


                    latest_completion_key = None
                    latest_completion_index = -1
                    for key in task.output:
                        # Check for completion content keys
                        completion_match = re.match(r'gen_ai\.completion\.(\d+)\.content', key)
                        if completion_match:
                            index = int(completion_match.group(1))
                            if index > latest_completion_index:
                                latest_completion_index = index
                                latest_completion_key = key

                    # Process prompt content
                    if latest_prompt_key and latest_prompt_key in task.output:
                        prompt_content = task.output[latest_prompt_key]
                        all_annotations.extend(await self.extract_and_store_annotations(task, latest_prompt_key, prompt_content))

                    # Process completion content
                    if latest_completion_key and latest_completion_key in task.output:
                        completion_content = task.output[latest_completion_key]

                        # Check if the content contains any of the ReAct markers
                        all_annotations.extend(await self.extract_and_store_annotations(task, latest_completion_key, completion_content))

            stored_annotations=[]
            if all_annotations:
                stored_annotations = await BaseAnnotation.bulk_store(data_manager=data_manager,base_annotations=all_annotations)

            # ---------------------------
            # Step 3: Return output
            # ---------------------------
            # Create output based on what was processed
            all_annotations_dicts = [annot.model_dump() for annot in stored_annotations]

            output = PatternAnnotationOutput(
                annotations=all_annotations_dicts,
                trace_id=trace_id if not trace_group_id else None,
                trace_group_id=trace_group_id if trace_group_id else None,
            )

            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.SUCCESS,
                output=output
            )

        except Exception as e:
            import traceback
            traceback.format_exc()
            print(traceback.format_exc())
            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="ProcessingError",
                    message=f"Failed to process Pattern annotations: {str(e)}"
                )
            )

    def is_milvus_search_task(self, task: TaskComposite) -> bool:
        """Check if the task is a milvus.search task"""
        return (hasattr(task, 'name') and task.name is not None and 'milvus.search' in task.name) or \
               (hasattr(task, 'tags') and task.tags is not None and 'vector_DB' in task.tags)

    async def create_rag_annotation(self, task: TaskComposite) -> BaseAnnotation | None:
        """Create a RAG annotation for milvus.search tasks"""
        try:
            # Extract milvus search attributes
            query_attributes = {}
            if hasattr(task, 'attributes') and task.attributes:
                for key, value in task.attributes.items():
                    if key.startswith('db.milvus.search.'):
                        # Remove the 'db.milvus.search.' prefix
                        attr_name = key.replace('db.milvus.search.', '')
                        query_attributes[attr_name] = value

            # Extract results from events
            results = []
            if hasattr(task, 'events') and task.events:
                for event in task.events:
                    if 'attributes' in event and \
                        'event' in event['attributes'] and \
                        'db.search.result' in event['attributes']['event']:

                        result_entry = {}
                        # Extract score (distance)
                        if 'db.search.result.distance' in event['attributes']:
                            result_entry['score'] = event['attributes']['db.search.result.distance']

                        # Extract entity
                        if 'db.search.result.entity' in event['attributes']:
                            entity_str = event['attributes']['db.search.result.entity']
                            try:
                                # Try to parse the entity string as it might be a string representation of a dict
                                import ast
                                entity = ast.literal_eval(entity_str)
                                result_entry['entity'] = entity
                            except (ValueError, SyntaxError):
                                # If parsing fails, use the string as is
                                result_entry['entity'] = entity_str

                        if result_entry:  # Only add if we have some data
                            results.append(result_entry)

            # Create the JSON content
            rag_content = {
                "query": query_attributes,
                "results": results
            }

            # Create the annotation
            return BaseAnnotation(
                element_id=f"rag_annotation_{task.element_id}",
                related_to=[task],
                name=f"rag_annotation_{task.element_id}",
                description=f"RAG annotation for milvus search in task {task.element_id}",
                annotation_type=DataAnnotation.Type.RAG,
                path_to_string=None,
                segment_start=0,
                segment_end=None,
                annotation_title="Milvus Search",
                annotation_content=json.dumps(rag_content, indent=2),
                root=task.root_id
            )

        except Exception as e:
            print(f"Error creating RAG annotation: {str(e)}")
            return None

    def has_prior_thoughts_actions_observations(self, annotations):
        for annotation in annotations:
            if annotation.annotation_type == DataAnnotation.Type.ACTION or annotation.annotation_type == DataAnnotation.Type.THOUGHT or annotation.annotation_type == DataAnnotation.Type.OBSERVATION:
                return True
        return False

    async def extract_and_store_annotations(self, task: TaskComposite, latest_completion_key, completion_content) -> list[BaseAnnotation]:
        annotations = []
        if "Thought:" in completion_content or "Action:" in completion_content or "Observation:" in completion_content:
            # Extract ReAct components with indices
            components = extract_react_components_with_indices(completion_content)

            # Create Annotation objects
            for component in components:
                annotations.append(BaseAnnotation(
                                    element_id=f"react_annotation_{task.element_id}_{component['start']}_{component['end']}",
                                    related_to=[task],
                                    name=f"react_annotation_{task.element_id}_{component['start']}_{component['end']}",
                                    description=f"react_annotation_{task.element_id}_{component['start']}_{component['end']}",
                                    #related_to_ids=[element_id],
                                    #related_to_types=[f"{Task.__module__}.{Task.__qualname__}"],
                                    annotation_type=component["type"],
                                    path_to_string=latest_completion_key,
                                    segment_start=component["start"],
                                    segment_end=component["end"],
                                    annotation_title=None,
                                    annotation_content=None,
                                    root=task.root_id
                                ))

        return annotations

    def create_annotations(self, primary_task: TaskComposite, minor_task: TaskComposite, type, title, content) -> BaseAnnotation:
        return BaseAnnotation(
            element_id=f"pattern_annotation_{primary_task.element_id}_{minor_task.element_id}",
            related_to=[primary_task],
            name=f"pattern_annotation_{primary_task.element_id}",
            description=f"pattern_annotation_{primary_task.element_id}",
            annotation_type=type,
            path_to_string=None,
            segment_start=0,
            segment_end=None,
            annotation_title=title,
            annotation_content=content,
            root=primary_task.root_id
        )

    def extract_annot_str(self, task: TaskComposite, show_system_prompt: bool = False, min_prompt_index: int = 0) -> tuple[str, int]:

        def is_json_content(content: str):
            """Check if content is JSON"""
            try:
                content_stripped = content.strip()
                if (content_stripped.startswith('{') and content_stripped.endswith('}')) or \
                (content_stripped.startswith('[') and content_stripped.endswith(']')):
                    json.loads(content_stripped)
                    return True
            except Exception:
                pass
            return False

        def format_json_content(content):
            """Helper function to format JSON snippets for better readability"""
            try:
                content_stripped = content.strip()
                if (content_stripped.startswith('{') and content_stripped.endswith('}')) or \
                (content_stripped.startswith('[') and content_stripped.endswith(']')):
                    json_obj = json.loads(content_stripped)
                    return json.dumps(json_obj, indent=2)
            except Exception:
                pass
            return content

        def indent_content(content, spaces=4):
            """Add indentation to each line of content"""
            indent = " " * spaces
            lines = content.split('\n')
            return '\n'.join(indent + line if line.strip() else line for line in lines)

        # Collect all message components with their indices
        message_components = []
        max_prompt_index = -1  # Track the highest prompt index found

        # Process input messages (prompts)
        for key in task.input:
            prompt_match = re.match(r'gen_ai\.(prompt)\.(\d+)\.([a-zA-Z_]+)(?:\.\d+\.([a-zA-Z_]+))?', key)
            if prompt_match:
                message_type = prompt_match.group(1)  # 'prompt'
                index = int(prompt_match.group(2))

                # Track the maximum prompt index we've seen
                max_prompt_index = max(max_prompt_index, index)

                # Skip prompts that have already been processed in earlier tasks
                if index < min_prompt_index:
                    continue

                field = prompt_match.group(3)
                subfield = prompt_match.group(4)
                value = task.input[key]
                message_components.append((message_type, index, 'input', field, subfield, value))

        # Process output messages (completions)
        for key in task.output:
            completion_match = re.match(r'gen_ai\.(completion)\.(\d+)\.([a-zA-Z_]+)(?:\.\d+\.([a-zA-Z_]+))?', key)
            if completion_match:
                message_type = completion_match.group(1)  # 'completion'
                index = int(completion_match.group(2))
                field = completion_match.group(3)
                subfield = completion_match.group(4)
                value = task.output[key]
                message_components.append((message_type, index, 'output', field, subfield, value))

        # Sort by message type first (prompt before completion), then by index, then by field priority
        def sort_key(component):
            message_type, index, io_type, field, subfield, value = component
            # Primary sort: message type (prompt=0, completion=1 to maintain conversation order)
            type_priority = {'prompt': 0, 'completion': 1}.get(message_type, 2)
            # Secondary sort: index within message type
            # Tertiary sort: field priority (role before content before tool_calls)
            field_priority = {'role': 0, 'content': 1, 'tool_calls': 2}.get(field, 3)
            # Quaternary sort: subfield priority
            subfield_priority = {'name': 0, 'arguments': 1}.get(subfield, 2) if subfield else 0
            return (type_priority, index, field_priority, subfield_priority)

        message_components.sort(key=sort_key)

        # If hiding system prompts, first identify which message indices are system messages
        system_message_indices = set()
        for message_type, index, _, field, _, value in message_components:
            if field == "role" and value.lower() == "system":
                system_message_indices.add((message_type, index))

        # Group components by message index and build formatted output
        annot_str = ""
        current_message_id = None
        pending_tool_name = ""

        for message_type, index, _, field, subfield, value in message_components:
            message_id = (message_type, index)

            # Skip this entire message if it's a system message and we're hiding them
            if not show_system_prompt and message_id in system_message_indices:
                continue

            # Add spacing between different messages
            if current_message_id is not None and current_message_id != message_id:
                annot_str += "\n"
            current_message_id = message_id

            if field == "role":
                # Format role as bold header
                annot_str += f"**{value}**:\n"

            elif field == "content":
                # Format content with proper indentation
                content = value

                # Check if content is JSON - if so, display it in an indented code block
                if is_json_content(content):
                    formatted_json = format_json_content(content)
                    indented_block = indent_content(f"```json\n{formatted_json}\n```")
                    annot_str += f"{indented_block}\n\n"
                else:
                    # Regular content - convert newline formats and indent
                    formatted_content = content.replace('\\n', '\n').replace('<br>', '\n')
                    indented_content = indent_content(formatted_content)
                    annot_str += f"{indented_content}\n\n"

            elif field == "tool_calls":
                if subfield == "name":
                    # Store tool name for pairing with arguments
                    pending_tool_name = value
                elif subfield == "arguments":
                    # Format tool call with name and formatted arguments
                    try:
                        if isinstance(value, str):
                            # Try to parse and reformat JSON arguments
                            args_obj = json.loads(value)
                            formatted_args = json.dumps(args_obj, indent=2)
                        else:
                            formatted_args = str(value)
                    except Exception:
                        formatted_args = str(value)

                    # Output the complete tool call with indentation
                    if pending_tool_name:
                        tool_call_content = f"**Tool Call - {pending_tool_name}**:\n```json\n{formatted_args}\n```"
                        indented_tool_call = indent_content(tool_call_content)
                        annot_str += f"{indented_tool_call}\n\n"
                        pending_tool_name = ""
                    else:
                        tool_args_content = f"**tool args**:\n```json\n{formatted_args}\n```"
                        indented_tool_args = indent_content(tool_args_content)
                        annot_str += f"{indented_tool_args}\n\n"

        # Clean up any trailing newlines and return both the annotation string and max prompt index
        return annot_str.rstrip("\n"), max_prompt_index
