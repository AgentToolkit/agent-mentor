from typing import Any, List, Dict
from opentelemetry.trace import Span
from pydantic import BaseModel
import json

from .langtrace_utils_for_litellm import NOT_GIVEN, SpanAttributes


def set_prompt_or_completions(span: Span, name: str, value: List[Dict[str, Any]]):
    for i, d in enumerate(value):
        for k, v in d.items():
            span_attr_name = f"{name}.{i}.{k}"
            span.set_attribute(span_attr_name, v)


def set_span_attribute(span: Span, name, value):
    if value is not None:
        if value != "" or value != NOT_GIVEN:
            # if given name tyes need to adjust format for analytics
            if name == SpanAttributes.LLM_PROMPTS:
                # set_event_prompt(span, value)
                # pass the actual list not the serialization
                set_prompt_or_completions(span, name, json.loads(value))
            elif name == SpanAttributes.LLM_COMPLETIONS:
                set_prompt_or_completions(span, name, value)
            else:
                span.set_attribute(name, value)
    return


def set_span_attributes(span: Span, attributes: Any) -> None:

    attrs = (
        attributes.model_dump(by_alias=True)
        if isinstance(attributes, BaseModel)
        else attributes
    )

    for field, value in attrs.items():
        set_span_attribute(span, field, value)
