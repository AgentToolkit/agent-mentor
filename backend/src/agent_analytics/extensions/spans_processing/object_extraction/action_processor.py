from typing import Any

from ibm_agent_analytics_common.interfaces.action import ActionKind

from agent_analytics.core.data_composite.action import BaseAction
from agent_analytics.extensions.spans_processing.common.langfuse import LangfuseObservationType
from agent_analytics.extensions.spans_processing.config.const import *
from agent_analytics.extensions.spans_processing.span_processor import SpanProcessor, VisitPhase
from agent_analytics.runtime.storage.store_config import StorageTag


class ActionVisitor(SpanProcessor):
    def __init__(self, shared_context: dict | None = None):
        self.actions = {}  # Local actions for this trace
        self.shared_context = shared_context  # Shared across all traces


    def process(self, span: Any, phase: VisitPhase, context: dict[str, Any]) -> None:

        if self._is_action_span(span):
            span_action = self._extract_action(span)

        # if we know this span, take constant generated values for code_id
        elif span.name in KNOWN_SPAN_NAMES.keys():
            span_action = BaseAction(
                input_schema=KNOWN_SPAN_NAMES[span.name][INPUT_SCHEMA],
                output_schema=KNOWN_SPAN_NAMES[span.name][OUTPUT_SCHEMA],
                code_id=KNOWN_SPAN_NAMES[span.name][CODE_ID],
                name=span.name,
                description=KNOWN_SPAN_NAMES[span.name][CODE_ID],
                is_generated=False,
                tags=[StorageTag.TASK]
            )
        # default action for unknown spans
        else:
            action_kind = self._get_action_kind(span)
            span_action = BaseAction(
                input_schema=UNKNOWN,
                output_schema=UNKNOWN,
                code_id=span.name,
                name=span.name,
                description=span.name,
                kind=action_kind,
                is_generated=True,
                tags=[StorageTag.TASK]
            )

        # Handle deduplication with shared context (only for non-root tasks)
        if self.shared_context and span_action.code_id != 'main':
            with self.shared_context['action_lock']:
                if span_action.code_id in self.shared_context['code_id_to_action']:
                    # Use existing shared action
                    span_action = self.shared_context['code_id_to_action'][span_action.code_id]
                else:
                    # Add to shared context
                    self.shared_context['code_id_to_action'][span_action.code_id] = span_action
                    # Also add to local actions
                    self.actions[span_action] = span_action
        else:
            # Fallback to local deduplication only (for single trace or root tasks)
            if span_action in self.actions:
                span_action = self.actions[span_action]
            else:
                self.actions[span_action] = span_action

        # if we have a task for the same action span, then it should be associated with it.
        # otherwise the manully reported task should have refreance for action_id
        task = context[SPAN_ID_TO_TASK].get(span.context.span_id, None)
        if task: 
            task.action_id = span_action.element_id


    def should_process(self, span: Any, context: dict[str, Any]) -> bool:
        """
        action should be created for spans which are transformed into tasks or manual actions 
        """
        return ((PROCESSED in span.raw_attributes.keys()) and span.raw_attributes[PROCESSED]
                or  self._is_action_span(span))

    def after_traversal(self, context: dict[str, Any]) -> None:
        self.add_action_for_root_tasks(context)
        context[ACTIONS] = list(self.actions.values())
        if SPAN_ID_TO_TASK in context.keys():
            context[TASKS] = {**context.get(TASKS, {}), **{task.id: task.flatten() for task in context[SPAN_ID_TO_TASK].values()}}
        else:
            context[TASKS] = {}


    def add_action_for_root_tasks(self, context: dict[str, Any]) -> None:
        for task in context[SPAN_ID_TO_TASK].values():
            if task.name.endswith(ROOT_NAME):
                fake_root_action = BaseAction(
                    input_schema=UNKNOWN,
                    output_schema=UNKNOWN,
                    code_id='main',
                    name=task.name,
                    description=task.name,
                    is_generated=True,
                    tags=[StorageTag.TASK]
                )
                self.actions[fake_root_action] = fake_root_action
                task.action_id = fake_root_action.element_id

    def _is_action_span(self, span: Any) -> bool:
        return OTEL_ACTION_ID in span.raw_attributes.keys()

    def _get_action_kind(self, span: Any) -> ActionKind:
        # get observation_type
        observation_to_action_kind = {
            LangfuseObservationType.GENERATION: ActionKind.LLM,
            LangfuseObservationType.RETRIEVER: ActionKind.VECTOR_DB,
            LangfuseObservationType.TOOL: ActionKind.TOOL,
            LangfuseObservationType.GUARDRAIL: ActionKind.GUARDRAIL,
            LangfuseObservationType.AGENT: ActionKind.LLM, # TODO: add action kind agent
        }

        observation_type = span.raw_attributes.get('langfuse.observation.type', 'SPAN')
        if observation_type in observation_to_action_kind:
            return observation_to_action_kind[observation_type]

        return ActionKind.OTHER

    def _extract_action(self, span: Any) -> BaseAction:
        """
        Extract action information from a span's raw attributes.
        Handles gen_ai.action.* OTEL semantic conventions.
        """
        attrs = span.raw_attributes

        # Extract action ID
        element_id = attrs.get(OTEL_ACTION_ID)

        # Extract code_id
        code_id = attrs.get(OTEL_ACTION_CODE_ID, UNKNOWN)
        language = attrs.get(OTEL_ACTION_CODE_LANGUAGE, UNKNOWN)

        # Extract schemas with 'unknown' default
        input_schema = attrs.get(OTEL_ACTION_CODE_INPUT_SCHEMA, UNKNOWN)
        output_schema = attrs.get(OTEL_ACTION_CODE_OUTPUT_SCHEMA, UNKNOWN)

        # Extract name and description
        name = attrs.get(OTEL_ACTION_NAME, span.name)
        description = attrs.get(OTEL_ACTION_DESCRIPTION, UNKNOWN)

        # Extract is_generated flag
        is_generated = attrs.get(OTEL_ACTION_IS_GENERATED, False)

        return BaseAction(
            element_id=element_id,
            input_schema=input_schema,
            output_schema=output_schema,
            language=language,
            code_id=code_id,
            name=name,
            description=description,
            is_generated=is_generated,
            tags=[StorageTag.TASK]
        )
