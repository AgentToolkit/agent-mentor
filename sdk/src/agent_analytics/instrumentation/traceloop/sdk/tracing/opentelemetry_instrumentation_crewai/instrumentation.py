from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.trace import get_tracer
from .version import __version__
from wrapt import wrap_function_wrapper as _W
from typing import Collection
from importlib_metadata import version as v
import importlib.metadata
from .patch import patch_crew, patch_memory, patch_tool
import packaging.version


class CrewAIInstrumentation(BaseInstrumentor):
    """
    The CrewAIInstrumentation class represents the CrewAI instrumentation"""

    def __init__(self, new_trace_on_workflow=False):
        super().__init__()
        self.new_trace_on_workflow = new_trace_on_workflow

    def instrumentation_dependencies(self) -> Collection[str]:
        return ["crewai >= 0.32.0"]

    def _instrument(self, **kwargs):
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(__name__, __version__, tracer_provider)

        version = v("crewai")
        try:
            _W(
                "crewai.crew",
                "Crew.kickoff",
                patch_crew("Crew.kickoff", version, tracer),
            )
            _W(
                "crewai.crew",
                "Crew.kickoff_for_each",
                patch_crew("Crew.kickoff_for_each", version, tracer),
            )
            _W(
                "crewai.crew",
                "Crew.kickoff_async",
                patch_crew("Crew.kickoff_async", version, tracer),
            )
            _W(
                "crewai.crew",
                "Crew.kickoff_for_each_async",
                patch_crew("Crew.kickoff_for_each_async", version, tracer),
            )
            _W(
                "crewai.agent",
                "Agent.execute_task",
                patch_crew("Agent.execute_task", version, tracer, self.new_trace_on_workflow, True),
            )
            _W(
                "crewai.task",
                "Task.execute_sync",
                patch_crew("Task.execute", version, tracer),
            )
            _W(
                "crewai.memory.storage.rag_storage",
                "RAGStorage.save",
                patch_memory("RAGStorage.save", version, tracer),
            )
            _W(
                "crewai.memory.storage.rag_storage",
                "RAGStorage.search",
                patch_memory("RAGStorage.search", version, tracer),
            )
            _W(
                "crewai.memory.storage.rag_storage",
                "RAGStorage.reset",
                patch_memory("RAGStorage.reset", version, tracer),
            )

        # pylint: disable=broad-except
        except Exception:
            pass

        # Patch tools
        try:
            # Check crewai version
            crewai_version = importlib.metadata.version("crewai")
            if packaging.version.parse(crewai_version) >= packaging.version.parse("0.85.0"):
                try:
                    # patch tool from crewai.tool
                    # _W(
                    #     "crewai.tools.base_tool",
                    #     "Tool._run",
                    #     patch_tool("Tool._run", version, tracer),
                    # )
                    _W(
                        "crewai.tools.structured_tool",
                        "CrewStructuredTool.invoke",
                        patch_tool("CrewStructuredTool.invoke", version, tracer),
                    )
                    _W(
                        "crewai.tools.structured_tool",
                        "CrewStructuredTool.ainvoke",
                        patch_tool("CrewStructuredTool.ainvoke", version, tracer),
                    )
                except Exception:
                    pass
        except importlib.metadata.PackageNotFoundError:
            pass

    def _uninstrument(self, **kwargs):
        pass
