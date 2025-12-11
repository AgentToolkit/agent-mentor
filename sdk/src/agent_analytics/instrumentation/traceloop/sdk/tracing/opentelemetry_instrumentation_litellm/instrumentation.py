from typing import Collection, Optional, Any
import importlib.metadata
import logging

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.trace import get_tracer, TracerProvider
from .version import __version__

from wrapt import wrap_function_wrapper

# from langtrace_python_sdk.instrumentation.litellm.patch import (
#     async_chat_completions_create,
#     async_embeddings_create,
#     async_images_generate,
#     chat_completions_create,
#     embeddings_create,
#     images_generate,
# )

from .patch import (
    async_chat_completions_create,
    async_embeddings_create,
    chat_completions_create,
    embeddings_create,
)

logging.basicConfig(level=logging.FATAL)


class LiteLLMInstrumentation(BaseInstrumentor):  # type: ignore

    def instrumentation_dependencies(self) -> Collection[str]:
        return ["litellm >= 1.48.0"]

    def _instrument(self, **kwargs: Any) -> None:
        tracer_provider: Optional[TracerProvider] = kwargs.get("tracer_provider")
        tracer = get_tracer(__name__, __version__, tracer_provider)
        version: str = importlib.metadata.version("openai")

        # Wrap both litellm.completion and litellm.main.completion
        # to ensure we catch sync calls regardless of import path
        wrap_function_wrapper(
            "litellm",
            "completion",
            chat_completions_create(version, tracer),
        )

        wrap_function_wrapper(
            "litellm.main",
            "completion",
            chat_completions_create(version, tracer),
        )

        wrap_function_wrapper(
            "litellm",
            "text_completion",
            chat_completions_create(version, tracer),
        )

        # Wrap both litellm.acompletion and litellm.main.acompletion
        # to ensure we catch async calls regardless of import path
        wrap_function_wrapper(
            "litellm",
            "acompletion",
            async_chat_completions_create(version, tracer),
        )

        wrap_function_wrapper(
            "litellm.main",
            "acompletion",
            async_chat_completions_create(version, tracer),
        )

        wrap_function_wrapper(
            "litellm.main",
            "embedding",
            embeddings_create(version, tracer),
        )

        wrap_function_wrapper(
            "litellm.main",
            "aembedding",
            async_embeddings_create(version, tracer),
        )

    def _uninstrument(self, **kwargs: Any) -> None:
        pass
