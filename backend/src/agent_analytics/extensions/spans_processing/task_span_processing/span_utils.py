from typing import Any

from agent_analytics.core.data_composite.base_span import BaseSpanComposite
from agent_analytics.core.data_composite.task import HierarchicalTask
from agent_analytics.extensions.spans_processing.common.utils import *
from agent_analytics.extensions.spans_processing.config.const import *
from agent_analytics_common.interfaces.task import TaskTag


class SpanProcessingUtils:
    """
    Utility class for general span processing operations.

    Provides common methods for span attribute extraction,
    span type detection, and other generic span-related utilities.
    """

    @staticmethod
    def add_fields_acc_to_names(names_list: list[str], span_dict: dict[str, Any],
                                attr_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Add specific fields from span dictionary to attribute dictionary.

        Args:
            names_list: List of field names to look for
            span_dict: Dictionary of span attributes
            attr_dict: Dictionary to add attributes to

        Returns:
            Updated attribute dictionary
        """
        for k in names_list:
            if k in span_dict:
                attr_dict[k] = span_dict[k]
        return attr_dict

    @staticmethod
    def add_fields_acc_to_startswith(names_list: list[str], span_dict: dict[str, Any],
                                     attr_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Add fields from span dictionary to attribute dictionary based on prefix.

        Args:
            names_list: List of prefixes to match
            span_dict: Dictionary of span attributes
            attr_dict: Dictionary to add attributes to

        Returns:
            Updated attribute dictionary
        """
        span_keys = list(span_dict.keys())

        for name in names_list:
            # Find keys that start with the specified prefix
            keys_to_add = [key for key in span_keys if key.startswith(name)]

            # Create a dictionary of matching key-value pairs
            attr_to_add = {key: span_dict[key] for key in keys_to_add}

            # Update the attribute dictionary
            attr_dict.update(attr_to_add)

        return attr_dict


    @classmethod
    def is_llm_span(cls, span: BaseSpanComposite) -> bool:
        """
        Determine if the span is an LLM span.

        Args:
            span: The span to check

        Returns:
            True if the span is an LLM span
        """
        return span.name.endswith(CHAT_SUFF) or span.name in LLM_CALL_SPAN_NAMES

    @classmethod
    def is_tool_span(cls, span: BaseSpanComposite) -> bool:
        """
        Determine if the span is a tool span.

        Args:
            span: The span to check

        Returns:
            True if the span is a tool span
        """
        return span.name.endswith(TOOL_SUFF)

    @classmethod
    def extract_input_output(cls, span: dict[str, Any]) -> tuple[Any, Any, Any]:
        """
        Extract input and output from span attributes.

        Args:
            span: Dictionary of span attributes

        Returns:
            Tuple of input and output dictionaries
        """
        t_input, attr = SpanProcessingUtils.preprocess_field(span, TRACELOOP_INPUT, SPAN_INPUTS)
        t_output, attr = SpanProcessingUtils.preprocess_field(span, TRACELOOP_OUTPUT, SPAN_OUTPUTS, attr)
        return t_input, t_output, attr

    @staticmethod
    def preprocess_field(span: dict[str, Any], field_name: str, internal_field: str, attr: dict = None) -> dict[Any, Any] | tuple[
        str, dict[list[str], dict]] | Any:
        """
        preprocesses dict type field values in spans, mostly used for extracting input/output values.
        Args:
            span: Dictionary of span attributes
            field_name: Main name of attribute, usually from traceloop
            internal_field: name of internal field inside dictionary field value
            attr: values of attributes to append to.

        Returns: preprocessed field values, and additional task attributes

        """
        if attr is None:
            attr = {}
        dict_field_values = span.get(field_name, {})
        dict_field_values = load_json_str_to_dict(dict_field_values, field_name=field_name, max_depth=3)
        # if isinstance(dict_field_values, str) and dict_field_values.strip().startswith('{') and dict_field_values.strip().endswith('}'):
        #     # If it's a string, try to parse as JSON
        #     try:
        #         dict_field_values = json.loads(dict_field_values)
        #         print('f')
        #     except json.JSONDecodeError:
        #         return dict_field_values
        # if isinstance(dict_field_values, (int, float)):
        #     dict_field_values = {field_name: dict_field_values}

        # extract relevant values
        relv_values = json.dumps({internal_field: dict_field_values[internal_field]} if internal_field in dict_field_values.keys() else dict_field_values)
        attr[f'additional_{internal_field}'] = {k: v for k, v in dict_field_values.items() if k != internal_field}
        return relv_values, attr

    @staticmethod
    def get_node_name_without_prefix(name: str) -> str:
        """Extract the node name without any prefix."""
        if NODE_SEPARATOR in name:
            return name.split(NODE_SEPARATOR, 1)[1]
        return name

    def is_llm_task_doubled(self, task, context):
        """
        check if two consecutive relevant spans have been transformed into tasks, describing the same llm call
        Args:
            task:
            context:

        Returns:

        """
        current_parent = context[LAST_PARENTS][-1]
        return TaskTag.LLM_CALL in task.tags and TaskTag.LLM_CALL in current_parent.tags



class LLMSpanProcessor:
    """
    Processor for handling LLM span processing and extraction.

    Uses OpenTelemetry gen_ai.* semantic conventions to extract LLM-specific
    information (prompts, completions, tokens, metadata) from spans.
    Works with any LLM provider that follows these conventions.
    """

    def __init__(self, span_utils: SpanProcessingUtils = None):
        """
        Initialize LLM span processor.

        Args:
            span_utils: Optional SpanProcessingUtils instance
        """
        self.span_utils = span_utils or SpanProcessingUtils()

    @staticmethod
    def add_tokens_acc_to_map(span_dict: dict[str, Any], attr_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Add token attributes to the attribute dictionary based on a predefined map.

        Args:
            span_dict: Dictionary of span attributes
            attr_dict: Dictionary to add attributes to

        Returns:
            Updated attribute dictionary
        """
        for key in TOKEN_ATTR_MAP.keys():
            for token_key in TOKEN_ATTR_MAP[key]:
                if token_key in span_dict:
                    attr_dict[key] = span_dict[token_key]
                    break
        return attr_dict

    def get_openai_attr_metadata(self, span_dict: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Extract OpenAI-specific attributes and metadata from span dictionary.

        Args:
            span_dict: Dictionary of span attributes

        Returns:
            Tuple of attributes and metadata dictionaries
        """
        attr = self.add_tokens_acc_to_map(span_dict, {})
        attr = self.span_utils.add_fields_acc_to_names(LLM_ATTR_FIELDS, span_dict, attr)
        metadata = self.span_utils.add_fields_acc_to_names(LLM_METADATA_FIELDS, span_dict, {})
        return attr, metadata

    def process_llm_task(self, task: HierarchicalTask, span: BaseSpanComposite) -> None:
        """
        Update a task with LLM-specific information from a span.

        Args:
            task: The task to update
            span: The original span
        """
        task.add_tag([TaskTag.LLM_CALL])

        # Process input and output
        task.input = self.span_utils.add_fields_acc_to_startswith([GEN_AI_PROMPT], span.raw_attributes, {})
        task.output = self.span_utils.add_fields_acc_to_startswith([GEN_AI_COMPLETION], span.raw_attributes, {})

        # Process events
        for event in span.events:
            if event.name == GEN_AI_EVENT_PROMPT:
                prompt = event.get(SPAN_ATTRIBUTES, {}).get(LLM_PROMPT_PRE, '')
                task.input.update(prompt)
            elif event.name == GEN_AI_EVENT_COMPLETE:
                output_addition = event.get(SPAN_ATTRIBUTES, {}).get(LLM_COMPLETE_PRE, '')
                task.output.update(output_addition)

        # Extract OpenAI attributes and metadata
        attr, metadata = self.get_openai_attr_metadata(span.raw_attributes)
        attr = self.span_utils.add_fields_acc_to_startswith(LLM_CALL_STARTSWITH_ATTR, span.raw_attributes, attr)

        task.attributes.update(attr)
        task.metadata.update(metadata)
