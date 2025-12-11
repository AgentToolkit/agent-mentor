# Utility variables and functions adapted from Langtrace to support CrewAI instrumentation,
# eliminating the direct dependency on the Langtrace package.
# Adapted from langtrace-python-sdk version: 3.3.4

import os
import json
from typing import Any, Dict, Literal, Union

from opentelemetry.trace import Span
from opentelemetry import baggage


# From: langtrace_python_sdk/constants/instrumentation/common.py
LANGTRACE_ADDITIONAL_SPAN_ATTRIBUTES_KEY = "langtrace_additional_attributes"

SERVICE_PROVIDERS = {
    "ANTHROPIC": "Anthropic",
    "AZURE": "Azure",
    "CHROMA": "Chroma",
    "CREWAI": "CrewAI",
    "DSPY": "DSPy",
    "GROQ": "Groq",
    "LANGCHAIN": "Langchain",
    "LANGCHAIN_COMMUNITY": "Langchain Community",
    "LANGCHAIN_CORE": "Langchain Core",
    "LANGGRAPH": "Langgraph",
    "LITELLM": "Litellm",
    "LLAMAINDEX": "LlamaIndex",
    "OPENAI": "OpenAI",
    "PINECONE": "Pinecone",
    "COHERE": "Cohere",
    "PPLX": "Perplexity",
    "QDRANT": "Qdrant",
    "WEAVIATE": "Weaviate",
    "OLLAMA": "Ollama",
    "VERTEXAI": "VertexAI",
    "GEMINI": "Gemini",
    "MISTRAL": "Mistral",
    "EMBEDCHAIN": "Embedchain",
    "AUTOGEN": "Autogen",
    "XAI": "XAI",
    "MONGODB": "MongoDB",
    "AWS_BEDROCK": "AWS Bedrock",
    "CEREBRAS": "Cerebras",
}


# From: langtrace_python_sdk/types/__init__.py
class NotGiven:
    """
    A sentinel singleton class used to distinguish omitted keyword arguments
    from those passed in with the value None (which may have different behavior).

    For example:

    ```py
    def get(timeout: Union[int, NotGiven, None] = NotGiven()) -> Response:
        ...


    get(timeout=1)  # 1s timeout
    get(timeout=None)  # No timeout
    get()  # Default timeout behavior, which may not be statically known at the method definition.
    ```
    """

    def __bool__(self) -> Literal[False]:
        return False

    def __repr__(self) -> str:
        return "NOT_GIVEN"


NOT_GIVEN = NotGiven()


# From: langtrace/trace_attributes/__init__.py
class SpanAttributes:
    LLM_SYSTEM = "gen_ai.system"
    LLM_OPERATION_NAME = "gen_ai.operation.name"
    LLM_REQUEST_MODEL = "gen_ai.request.model"
    LLM_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
    LLM_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
    LLM_REQUEST_TOP_P = "gen_ai.request.top_p"
    LLM_SYSTEM_FINGERPRINT = "gen_ai.system_fingerprint"

    LLM_REQUEST_DOCUMENTS = "gen_ai.request.documents"
    LLM_REQUEST_SEARCH_REQUIRED = "gen_ai.request.is_search_required"
    LLM_PROMPTS = "gen_ai.prompt"
    LLM_CONTENT_PROMPT = "gen_ai.content.prompt"
    LLM_COMPLETIONS = "gen_ai.completion"
    LLM_CONTENT_COMPLETION = "gen_ai.content.completion"

    LLM_RESPONSE_MODEL = "gen_ai.response.model"
    LLM_USAGE_COMPLETION_TOKENS = "gen_ai.usage.output_tokens"
    LLM_USAGE_PROMPT_TOKENS = "gen_ai.usage.input_tokens"
    LLM_USAGE_TOTAL_TOKENS = "gen_ai.usage.total_tokens"
    LLM_USAGE_TOKEN_TYPE = "gen_ai.usage.token_type"
    LLM_USAGE_SEARCH_UNITS = "gen_ai.usage.search_units"
    LLM_GENERATION_ID = "gen_ai.generation_id"
    LLM_TOKEN_TYPE = "gen_ai.token.type"
    LLM_RESPONSE_ID = "gen_ai.response_id"
    LLM_URL = "url.full"
    LLM_PATH = "url.path"
    LLM_RESPONSE_FORMAT = "gen_ai.request.response_format"
    LLM_IMAGE_SIZE = "gen_ai.image.size"
    LLM_REQUEST_ENCODING_FORMATS = "gen_ai.request.encoding_formats"
    LLM_REQUEST_DIMENSIONS = "gen_ai.request.dimensions"
    LLM_REQUEST_SEED = "gen_ai.request.seed"
    LLM_REQUEST_TOP_LOGPROPS = "gen_ai.request.top_props"
    LLM_REQUEST_LOGPROPS = "gen_ai.request.log_props"
    LLM_REQUEST_LOGITBIAS = "gen_ai.request.logit_bias"

    LLM_REQUEST_TYPE = "gen_ai.request.type"
    LLM_HEADERS = "gen_ai.headers"

    LLM_USER = "gen_ai.user"
    LLM_TOOLS = "gen_ai.request.tools"
    LLM_TOOL_CHOICE = "gen_ai.request.tool_choice"
    LLM_TOOL_RESULTS = "gen_ai.request.tool_results"

    LLM_TOP_K = "gen_ai.request.top_k"
    LLM_IS_STREAMING = "gen_ai.request.stream"
    LLM_FREQUENCY_PENALTY = "gen_ai.request.frequency_penalty"
    LLM_PRESENCE_PENALTY = "gen_ai.request.presence_penalty"
    LLM_CHAT_STOP_SEQUENCES = "gen_ai.chat.stop_sequences"
    LLM_REQUEST_FUNCTIONS = "gen_ai.request.functions"
    LLM_REQUEST_REPETITION_PENALTY = "gen_ai.request.repetition_penalty"
    LLM_RESPONSE_FINISH_REASON = "gen_ai.response.finish_reasons"
    LLM_RESPONSE_STOP_REASON = "gen_ai.response.stop_reason"
    LLM_CONTENT_COMPLETION_CHUNK = "gen_ai.completion.chunk"
    # embeddings
    LLM_REQUEST_EMBEDDING_INPUTS = "gen_ai.request.embedding_inputs"
    LLM_REQUEST_EMBEDDING_DATASET_ID = "gen_ai_request_embedding_dataset_id"
    LLM_REQUEST_EMBEDDING_INPUT_TYPE = "gen_ai.request.embedding_input_type"
    LLM_REQUEST_EMBEDDING_JOB_NAME = "gen_ai.request.embedding_job_name"

    # Cohere
    LLM_COHERE_RERANK_QUERY = "gen_ai.cohere.rerank.query"
    LLM_COHERE_RERANK_RESULTS = "gen_ai.cohere.rerank.results"

    # Langtrace
    LANGTRACE_SDK_NAME = "langtrace.sdk.name"
    LANGTRACE_SERVICE_NAME = "langtrace.service.name"
    LANGTRACE_SERVICE_TYPE = "langtrace.service.type"
    LANGTRACE_SERVICE_VERSION = "langtrace.service.version"
    LANGTRACE_VERSION = "langtrace.version"

    # Http
    HTTP_MAX_RETRIES = "http.max.retries"
    HTTP_TIMEOUT = "http.timeout"


# From: langtrace_python_sdk/utils/__init__.py
def set_span_attribute(span: Span, name, value):
    if value is not None:
        if value != "" or value != NOT_GIVEN:
            if name == SpanAttributes.LLM_PROMPTS:
                set_event_prompt(span, value)
            else:
                span.set_attribute(name, value)
    return


def set_event_prompt(span: Span, prompt):
    enabled = os.environ.get("TRACE_PROMPT_COMPLETION_DATA", "true")
    if enabled.lower() == "false":
        return

    span.add_event(
        name=SpanAttributes.LLM_CONTENT_PROMPT,
        attributes={
            SpanAttributes.LLM_PROMPTS: prompt,
        },
    )


# From: langtrace_python_sdk/utils/llm.py
def get_span_name(operation_name):
    extra_attributes = get_extra_attributes()
    if extra_attributes is not None and "langtrace.span.name" in extra_attributes:
        return f'{operation_name}-{extra_attributes["langtrace.span.name"]}'
    return operation_name


def get_extra_attributes() -> Union[Dict[str, Any], object]:
    extra_attributes = baggage.get_baggage(LANGTRACE_ADDITIONAL_SPAN_ATTRIBUTES_KEY)
    return extra_attributes or {}


def set_span_attributes(span: Span, attributes: Any) -> None:
    from pydantic import BaseModel

    attrs = (
        attributes.model_dump(by_alias=True)
        if isinstance(attributes, BaseModel)
        else attributes
    )

    for field, value in attrs.items():
        set_span_attribute(span, field, value)


# From: langtrace_python_sdk/utils/misc.py
def serialize_args(*args):
    # Function to check if a value is serializable
    def is_serializable(value):
        try:
            json.dumps(value)
            return True
        except (TypeError, ValueError):
            return False

    # Filter out non-serializable items
    serializable_args = [arg for arg in args if is_serializable(arg)]

    # Convert to string representation
    return json.dumps(serializable_args)


def serialize_kwargs(**kwargs):
    # Function to check if a value is serializable
    def is_serializable(value):
        try:
            json.dumps(value)
            return True
        except (TypeError, ValueError):
            return False

    # Filter out non-serializable items
    serializable_kwargs = {k: v for k, v in kwargs.items() if is_serializable(v)}

    # Convert to string representation
    return json.dumps(serializable_kwargs)
