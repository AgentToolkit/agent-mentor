"""
Main client for the AgentOps SDK

Provides a unified interface for all SDK operations.
"""


import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from agent_analytics.runtime.api import TenantComponents
from agent_analytics.runtime.api.initialization import ensure_tenant_initialized
from agent_analytics.runtime.registry.analytics_metadata import (
    AnalyticsMetadata,
    ControllerConfig,
    RuntimeConfig,
    RuntimeType,
    Status,
    TemplateConfig,
    TriggerType,
)
from agent_analytics.runtime.registry.analytics_registry import AnalyticsRegistry
from agent_analytics.runtime.storage.logical_data_manager import AnalyticsDataManager
from agent_analytics.sdk.resources.actions import ActionsResource
from agent_analytics.sdk.resources.annotations import AnnotationsResource
from agent_analytics.sdk.resources.issues import IssuesResource
from agent_analytics.sdk.resources.metrics import MetricsResource
from agent_analytics.sdk.resources.recommendations import RecommendationsResource
from agent_analytics.sdk.resources.spans import SpansResource
from agent_analytics.sdk.resources.task import TasksResource
from agent_analytics.sdk.resources.trace_groups import TraceGroupsResource
from agent_analytics.sdk.resources.trace_workflows import TraceWorkflowsResource
from agent_analytics.sdk.resources.traces import TracesResource

ENABLE_EXTENSIONS = os.getenv('ENABLE_EXTENSIONS', '').lower() in ('true', '1', 'yes', 'on')
class AgentOpsClient:
    """
    Main client for interacting with AgentOps analytics platform.

    This client provides access to all platform resources through
    intuitive resource-based APIs.

    Resources:
        - traces: Query and retrieve trace data
        - trace_groups: Query and create trace groups
        - spans: Query span data
        - metrics: Create and query metrics
        - issues: Create and query issues
        - trace_workflows: Query trace workflows
        - recommendations: Create and query recommendations
        - annotations: Create and query annotations

    Example:
        client = await AgentOpsClient.create()

        # Query traces
        traces = await client.traces.fetch(service_name="my-service")

        # Get spans for a trace
        spans = await client.spans.fetch(trace_id=traces[0].id)

        # Create metrics
        metric = await client.metrics.create(
            owner=traces[0],
            name="quality_score",
            value=0.95
        )

        # Create issues
        issue = await client.issues.create(
            owner=traces[0],
            name="High Latency",
            description="Response time exceeded threshold",
            related_to=[spans[0]]
        )
    """

    TASK_ANALYTICS = "task_analytics"
    EVAL_METRICS = "eval_metrics"
    WORKFLOW_ANALYTICS = "workflow_analytics"
    PATTERN_ANNOTATION_ANALYTICS = "pattern_annotation_analytics"
    ISSUE_ANALYTICS = "issue_analytics"
    ANNOTATION_ANALYTICS = "annotation_analytics"
    SECURITY_ANALYTICS = "security_analytics"
    TOOL_USAGE_ANALYTICS="tool_usage_analytics"
    DRIFT_ANALYTICS = "drift_analytics"
    CYCLE_ANALYTICS = "cycles_detection_analytics"
    ISSUE_DIST_ANALYTICS = "trace_issue_distribution"
    WORKFLOW_METRIC_ANALYTICS = "workflow_metric_analytics"
    TASK_METRIC_ANALYTICS = "task_metrics_analytics"

    change_analytics_config = {
        "change_analytics": "True",
        "anomaly_analytics": "True",
        "min_observations": 7,
        "window_max": "10",
        "change_threshold": "0.75",
        "anomaly_threshold": "0.95",
        "change_ratio_bound": "0.05",
        "anomaly_ratio_bound": "0.2"
        }

    def __init__(self, data_manager: AnalyticsDataManager, tenant_components: TenantComponents):
        """
        Initialize the AgentOps client.

        Args:
            data_manager: The underlying data manager instance
            tenant_components: The tenant components for accessing executor and registry

        Note:
            Use AgentOpsClient.create() instead of calling this directly.
        """
        self._data_manager = data_manager
        self._tenant_components = tenant_components

        # Initialize resource APIs
        self.traces = TracesResource(data_manager, tenant_components)
        self.trace_groups = TraceGroupsResource(data_manager, tenant_components)
        self.spans = SpansResource(data_manager)
        self.metrics = MetricsResource(data_manager)
        self.issues = IssuesResource(data_manager)
        self.workflows = TraceWorkflowsResource(data_manager)
        self.recommendations = RecommendationsResource(data_manager)
        self.annotations = AnnotationsResource(data_manager)
        self.actions = ActionsResource(data_manager)
        self.tasks = TasksResource(data_manager)

    @staticmethod
    def _load_environment(env_path: Path | str | None = None) -> None:
        """
        Load environment variables from .env file.

        Searches for .env file up the directory tree if not explicitly provided.
        Existing environment variables are not overridden.

        Args:
            env_path: Optional explicit path to .env file. If None, auto-discovers
                     by searching up the directory tree from current working directory.
        """
        if env_path:
            # Explicit path provided
            env_path = Path(env_path)
            if env_path.exists():
                load_dotenv(env_path, override=False)
        else:
            # Auto-discover .env file by walking up directory tree
            dotenv_path = find_dotenv(usecwd=True)
            if dotenv_path:
                load_dotenv(dotenv_path, override=False)

    @classmethod
    async def create(cls, tenant_id: str | None = None,  env_path: Path | str | None = None) -> "AgentOpsClient":
        """
        Create and initialize a new AgentOps client.

        This method handles all necessary initialization including tenant
        setup and backend connections.

        Args:
            tenant_id: Optional tenant identifier. If not provided, uses
                      the default tenant configuration.

        Returns:
            An initialized AgentOpsClient instance

        Example:
            # Use default tenant
            client = await AgentOpsClient.create()

            # Use specific tenant
            client = await AgentOpsClient.create(tenant_id="my-tenant")
        """
        # Load environment variables before tenant initialization
        cls._load_environment(env_path)

        # Initialize the tenant backend
        tenant_components, _, is_new_tenant = await ensure_tenant_initialized(tenant_id=tenant_id)

        if is_new_tenant:
            await AgentOpsClient._register_analytics(tenant_components.registry)

        # Create and return the client
        return cls(tenant_components.data_manager, tenant_components)


    @classmethod
    async def _register_analytics(cls, registry: AnalyticsRegistry):
        analytics_metadata = []
        #Create a list of all issue creation plugins

        analytics_metadata.append(AnalyticsMetadata(
                id=AgentOpsClient.TASK_METRIC_ANALYTICS,
                name="Task Metrics",
                description="Calculate metric tasks",
                version="1.0",
                owner="analytics_team",
                status=Status.ACTIVE,
                template=TemplateConfig(
                    runtime=RuntimeConfig(
                        type=RuntimeType.PYTHON,
                        config={
                            "module_path": "agent_analytics.extensions.task_analytics.metrics.task_metric_plugin"}
                    ),
                    controller=ControllerConfig(
                        trigger_config={"type": TriggerType.DIRECT},
                        dependsOn=[] #RuntimeClient.ISSUE_DIST_ANALYTICS
                    ),
                    config={},
                )
            ))

        analytics_metadata.append(AnalyticsMetadata(
            id=AgentOpsClient.TASK_ANALYTICS,
            name="Task Analytics",
            description="Build a task tree for the trace flow",
            version="1.0",
            owner="analytics_team",
            status=Status.ACTIVE,
            template=TemplateConfig(
                runtime=RuntimeConfig(
                    type=RuntimeType.PYTHON,
                    # config={"module_path": "agent_analytics.extensions.task_analytics.flows.task_analytics"}
                    config={"module_path": "agent_analytics.extensions.spans_processing.task_span_processing.task_creation_plugin"}
                ),
                controller=ControllerConfig(
                    trigger_config={"type": TriggerType.DIRECT},
                    dependsOn=[],  # No dependencies,
                    triggers=[AgentOpsClient.TASK_METRIC_ANALYTICS]
                ),
                config={}
            )
        ))

        analytics_metadata.append(AnalyticsMetadata(
            id=AgentOpsClient.WORKFLOW_METRIC_ANALYTICS,
            name="Trace Issue Distribution Metric",
            description="Calculate issue distribution per severity for each task in a trace",
            version="1.0",
            owner="analytics_team",
            status=Status.ACTIVE,
            template=TemplateConfig(
                runtime=RuntimeConfig(
                    type=RuntimeType.PYTHON,
                    config={"module_path": "agent_analytics.extensions.workflow.workflow_metric_plugin"}
                ),
                controller=ControllerConfig(
                    trigger_config={"type": TriggerType.DIRECT},
                    dependsOn=[]  # RuntimeClient.WORKFLOW_ANALYTICS
                ),
                config={"list_numeric_metrics": \
                        [("Number of visits", "Num_Visits", 'Count'), \
                        ("Execution time", "Execution_Time", 'Seconds'), \
                        ("LLM calls", "LLM_Calls", 'Count'), \
                        ("Tool calls","Tool_Calls", 'Count'), \
                        ("Subtasks", "Subtasks", 'Count'), \
                        ("Maximal subtree", "Width", 'Width'), \
                        ("Input tokens", "Input_Tokens", 'Count'), \
                        ("Output tokens", "Output_Tokens", 'Count'), \
                        ("Total tokens", "Total_Tokens", 'Count')], \
                            "list_distribution_metrics" : \
                            [("Tool distribution", "Tool_Distribution"),\
                            ("Issue distribution in task", "Issue_Distribution")]
                     },
            )
        ))

        analytics_metadata.append(AnalyticsMetadata(
            id=AgentOpsClient.WORKFLOW_ANALYTICS,
            name="Workflow Analytics",
            description="Calculate workflow for traces",
            version="1.0",
            owner="analytics_team",
            status=Status.ACTIVE,
            template=TemplateConfig(
                runtime=RuntimeConfig(
                    type=RuntimeType.PYTHON,
                    config={"module_path": "agent_analytics.extensions.causal_discovery.causal_discovery_light_plugin"}
                ),
                controller=ControllerConfig(
                    trigger_config={"type": TriggerType.DIRECT},
                    dependsOn=[], #RuntimeClient.TASK_METRIC_ANALYTICS
                    triggers=[AgentOpsClient.WORKFLOW_METRIC_ANALYTICS]
                ),
                config={},
            )
        ))

        analytics_metadata.append(AnalyticsMetadata(
            id=AgentOpsClient.ISSUE_DIST_ANALYTICS,
            name="Trace Issue Distribution Metric",
            description="Calculate issue distribution per severity for each task in a trace",
            version="1.0",
            owner="analytics_team",
            status=Status.ACTIVE,
            template=TemplateConfig(
                runtime=RuntimeConfig(
                    type=RuntimeType.PYTHON,
                    config={"module_path": "agent_analytics.extensions.task_analytics.metrics.issue_distribution_trace_plugin"}
                ),
                controller=ControllerConfig(
                    trigger_config={"type": TriggerType.DIRECT},
                    dependsOn=[]  # No dependencies but in practice it's on ['task_analytics', 'issue_analytics']
                ),
                config={},
            )
        ))

        analytics_metadata.append(AnalyticsMetadata(
            id=AgentOpsClient.ISSUE_ANALYTICS,
            name="Span Issue Analytics",
            description="Calculate Issue for spans",
            version="1.0",
            owner="analytics_team",
            status=Status.ACTIVE,
            template=TemplateConfig(
                runtime=RuntimeConfig(
                    type=RuntimeType.PYTHON,
                    config={"module_path": "agent_analytics.extensions.issue.issue_analytics"}
                ),
                controller=ControllerConfig(
                    trigger_config={"type": TriggerType.DIRECT},
                    dependsOn=[]
                ),
                config={},
            )
        ))

        analytics_metadata.append(AnalyticsMetadata(
            id=AgentOpsClient.PATTERN_ANNOTATION_ANALYTICS,
            name="Pattern Annotation Analytics",
            description="Extact patterns to create annotation",
            version="1.0",
            owner="analytics_team",
            status=Status.ACTIVE,
            template=TemplateConfig(
                runtime=RuntimeConfig(
                    type=RuntimeType.PYTHON,
                    config={"module_path": "agent_analytics.extensions.object_extraction.pattern_annotation_plugin"}
                ),
                controller=ControllerConfig(
                    trigger_config={"type": TriggerType.DIRECT},
                    dependsOn=[]  # No dependencies
                ),
                config={}
            )
        ))

        analytics_metadata.append(AnalyticsMetadata(
            id=AgentOpsClient.ANNOTATION_ANALYTICS,
            name="Annotation Analytics",
            description="Extract annotations from the trace spans",
            version="1.0",
            owner="analytics_team",
            status=Status.ACTIVE,
            template=TemplateConfig(
                runtime=RuntimeConfig(
                    type=RuntimeType.PYTHON,
                    config={"module_path": "agent_analytics.extensions.object_extraction.annotation_plugin"}
                ),
                controller=ControllerConfig(
                    trigger_config={"type": TriggerType.DIRECT},
                    dependsOn=[]  # No dependencies
                ),
                config={}
            )
        ))

        if ENABLE_EXTENSIONS:
            analytics_metadata.append(AnalyticsMetadata(
                id=AgentOpsClient.EVAL_METRICS,
                name="Task Metrics Analytics",
                description="Calculate metrics for individual tasks",
                version="1.0",
                owner="analytics_team",
                status=Status.ACTIVE,
                template=TemplateConfig(
                    runtime=RuntimeConfig(
                        type=RuntimeType.PYTHON,
                        config={"module_path": "agent_analytics.extensions.task_analytics.metrics.agent_pipe_eval_plugin"}
                    ),
                    controller=ControllerConfig(
                        trigger_config={"type": TriggerType.DIRECT},
                        dependsOn=[]
                    ),
                    config={},
                )
            ))

            analytics_metadata.append(AnalyticsMetadata(
                id=AgentOpsClient.SECURITY_ANALYTICS,
                name="Security Analytics",
                description="Find security issues",
                version="1.0",
                owner="analytics_team",
                status=Status.ACTIVE,
                template=TemplateConfig(
                    runtime=RuntimeConfig(
                        type=RuntimeType.PYTHON,
                        # config={"module_path": "agent_analytics.extensions.task_analytics.flows.task_analytics"}
                        config={"module_path": "agent_analytics.extensions.security.security_issues_plugin"}
                    ),
                    controller=ControllerConfig(
                        trigger_config={"type": TriggerType.DIRECT},
                        dependsOn=[]  # No dependencies
                    ),
                    config={}
                )
            ))

            analytics_metadata.append(AnalyticsMetadata(
                id=AgentOpsClient.TOOL_USAGE_ANALYTICS,
                name="Tool Usage Analytics",
                description="Find tool usage issues",
                version="1.0",
                owner="analytics_team",
                status=Status.ACTIVE,
                template=TemplateConfig(
                    runtime=RuntimeConfig(
                        type=RuntimeType.PYTHON,
                        config={"module_path": "agent_analytics.extensions.issue.tool_usage_issues_plugin"}
                    ),
                    controller=ControllerConfig(
                        trigger_config={"type": TriggerType.DIRECT},
                        dependsOn=[]  # No dependencies
                    ),
                    config={}
                )
            ))

        analytics_metadata.append(AnalyticsMetadata(
            id=AgentOpsClient.DRIFT_ANALYTICS,
            name="Drift/Change Analytics",
            description="Detect drift or change points in a group of traces",
            version="1.0",
            owner="analytics_team",
            status=Status.ACTIVE,
            template=TemplateConfig(
                runtime=RuntimeConfig(
                    type=RuntimeType.PYTHON,
                    config={"module_path": "agent_analytics.extensions.drift_anomalies.change_plugin"}
                ),
                controller=ControllerConfig(
                    trigger_config={"type": TriggerType.DIRECT},
                    dependsOn=[]  # No dependencies
                ),
                config=AgentOpsClient.change_analytics_config
            )
        ))

        # analytics_metadata.append(AnalyticsMetadata(
        #     id=AgentOpsClient.CYCLE_ANALYTICS,
        #     name="Cycles Detection Analytics",
        #     description="Detect repetitive execution of nodes in the agentic graph",
        #     version="1.0",
        #     owner="analytics_team",
        #     status=Status.ACTIVE,
        #     template=TemplateConfig(
        #         runtime=RuntimeConfig(
        #             type=RuntimeType.PYTHON,
        #             config={"module_path": "agent_analytics.extensions.cycle_detection.cycles_plugin"}
        #         ),
        #         controller=ControllerConfig(
        #             trigger_config={"type": TriggerType.DIRECT},
        #             dependsOn=[]  # No dependencies but in practice it's on ['task_analytics']
        #         ),
        #         config={'min_occurrences':'2'},
        #     )
        # ))

        for metadata in analytics_metadata:
            analytics = await registry.get_analytics(metadata.id)
            if analytics is not None:
                # existing analytics
                if not analytics.equals(metadata):
                    # changed analytics
                    await registry.delete_analytics(metadata.id)
                    await registry.register_analytics(metadata)
                # else:
                    # existing but not change - do nothing
            else:
                # new analytics
                await registry.register_analytics(metadata)


    async def close(self):
        """
        Close the client and clean up resources.

        Call this when you're done using the client to ensure proper cleanup.
        """
        # Future: Add cleanup logic if needed
        pass

    async def __aenter__(self):
        """Support async context manager"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Support async context manager"""
        await self.close()
