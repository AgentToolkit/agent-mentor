import json
import os
from datetime import datetime
from typing import Any

import yaml
from dotenv import load_dotenv
from ibm_agent_analytics_common.interfaces.metric import AggregateMetric

from agent_analytics.core.data.span_data import SpanEvent, SpanKind
from agent_analytics.core.data_composite.base_span import BaseSpanComposite
from agent_analytics.core.data_composite.base_trace import BaseTraceComposite
from agent_analytics.core.data_composite.metric import MetricComposite
from agent_analytics.core.data_composite.task import TaskComposite
from agent_analytics.core.data_composite.trace_group import TraceGroupComposite
from agent_analytics.core.plugin.base_plugin import ExecutionStatus
from agent_analytics.runtime.api import TenantComponents
from agent_analytics.runtime.api.config import settings
from agent_analytics.runtime.api.initialization import clear_all_backends, ensure_tenant_initialized
from agent_analytics.runtime.api.tenant_config_service import (
    StoreType,
    TenantConfig,
    tenant_config_service,
)
from agent_analytics.runtime.registry.analytics_metadata import (
    AnalyticsMetadata,
    ControllerConfig,
    RuntimeConfig,
    RuntimeType,
    Status,
    TemplateConfig,
    TriggerType,
)

# from platform.
from agent_analytics.runtime.utilities.file_loader import parse_trace_logs
from agent_analytics.server.analytics_utils import transform_workflow
from agent_analytics.server.logger import logger
from agent_analytics.server.span_sender import send_spans
from agent_analytics.server.trajectory_step import TrajectoryElement, TrajectoryStep
from agent_analytics.server.utils.runtime_metrics_aggregations import (
    create_combined_agent_summary_metrics_traces_optimized,
    create_detailed_metrics_traces,
)

# Load environment variables from .env file
load_dotenv()

# T = TypeVar('T', bound=BaseArtifact)
PROXY_SERVER_URL = os.environ.get('PROXY_SERVER_URL', None)
# ENABLE_EXTENSIONS = ENABLE_EXTENSIONS and find_spec("agent_pipe_eval") is not None

class RuntimeClient:
    ENABLE_EXTENSIONS = os.getenv('ENABLE_EXTENSIONS', '').lower() in ('true', '1', 'yes', 'on')

    TASK_ANALYTICS = "task_analytics"
    EVAL_METRICS = "eval_metrics"
    PATTERN_ANNOTATION_ANALYTICS = "pattern_annotation_analytics"
    ISSUE_ANALYTICS = "issue_analytics"
    ANNOTATION_ANALYTICS = "annotation_analytics"
    SECURITY_ANALYTICS = "security_analytics"
    TOOL_USAGE_ANALYTICS="tool_usage_analytics"
    DRIFT_ANALYTICS = "drift_analytics"
    CYCLE_ANALYTICS = "cycles_detection_analytics"
    ISSUE_DIST_ANALYTICS = "trace_issue_distribution"
    TASK_METRIC_ANALYTICS = "task_metrics_analytics"

    STATUS_RUNNING = "RUNNING"
    STATUS_READY = "READY"
    STATUS_EMPTY = "EMPTY"
    STATUS_NOT_STARTED = "NOT_STARTED"
    STATUS_FAILED = "ERROR"


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

    ISSUE_ANALYTICS_PLUGINS = [
        ISSUE_ANALYTICS,
        CYCLE_ANALYTICS
    ]
    if ENABLE_EXTENSIONS:
       pass


    async def initialize(self):
        config_file_path = os.environ.get('TENANT_CONFIG_FILE')

        try:
            if config_file_path:
                with open(config_file_path) as f:
                    config = yaml.safe_load(f)

                tenants = config.get("tenants", {})
                logger.info(f"Initializing analytics for {len(tenants)} tenants: {list(tenants.keys())}")

                # Initialize analytics for each tenant
                for tenant_id in tenants.keys():
                    try:
                        self.set_tenant_config(tenant_id, tenants[tenant_id])
                        await self.ensure_initialized(tenant_id)
                        logger.info(f"✅ Initialized analytics for tenant: {tenant_id}")
                    except Exception as e:
                        logger.error(f"❌ Failed to initialize tenant '{tenant_id}': {e}")
            else:
                logger.info("Falling back to default tenant")
                await self.ensure_initialized(settings.DEFAULT_TENANT_ID)
                logger.info(f"✅ Initialized analytics for fallback tenant: {settings.DEFAULT_TENANT_ID}")

        except Exception as e:
            logger.error(f"Failed to load tenant configuration from {config_file_path}: {e}")
            logger.info("Falling back to default tenant")
            await self.ensure_initialized(settings.DEFAULT_TENANT_ID)
            logger.info(f"✅ Initialized analytics for fallback default tenant: {settings.DEFAULT_TENANT_ID}")

    async def ensure_initialized(self, tenant_id) -> tuple[TenantComponents, TenantConfig]:
        tenant_components, tenant_config, is_new_tenant = await ensure_tenant_initialized(tenant_id)
        if is_new_tenant:
            await self.register_analytics(tenant_id)
        return tenant_components, tenant_config

    async def cleanup(self, tenant_id):
        # await clear_backend_for_tenant(tenant_id)
        pass

    async def cleanup_all(self):
        await clear_all_backends()

    async def register_analytics(self, tenant_id: str):
        tenant_components, tenant_config, _ = await ensure_tenant_initialized(tenant_id)
        analytics_metadata = []
        #Create a list of all issue creation plugins

        analytics_metadata.append(AnalyticsMetadata(
            id=RuntimeClient.TASK_ANALYTICS,
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
                    dependsOn=[]  # No dependencies
                ),
                config={}
            )
        ))

        analytics_metadata.append(AnalyticsMetadata(
            id=RuntimeClient.ISSUE_DIST_ANALYTICS,
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
                id=RuntimeClient.TASK_METRIC_ANALYTICS,
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
            id=RuntimeClient.ISSUE_ANALYTICS,
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
            id=RuntimeClient.PATTERN_ANNOTATION_ANALYTICS,
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
            id=RuntimeClient.ANNOTATION_ANALYTICS,
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

        if self.ENABLE_EXTENSIONS:
            pass

        analytics_metadata.append(AnalyticsMetadata(
            id=RuntimeClient.DRIFT_ANALYTICS,
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
                config=self.change_analytics_config
            )
        ))

        analytics_metadata.append(AnalyticsMetadata(
            id=RuntimeClient.CYCLE_ANALYTICS,
            name="Cycles Detection Analytics",
            description="Detect repetitive execution of nodes in the agentic graph",
            version="1.0",
            owner="analytics_team",
            status=Status.ACTIVE,
            template=TemplateConfig(
                runtime=RuntimeConfig(
                    type=RuntimeType.PYTHON,
                    config={"module_path": "agent_analytics.extensions.cycle_detection.cycles_plugin"}
                ),
                controller=ControllerConfig(
                    trigger_config={"type": TriggerType.DIRECT},
                    dependsOn=[]  # No dependencies but in practice it's on ['task_analytics']
                ),
                config={'min_occurrences':'2'},
            )
        ))

       

        for metadata in analytics_metadata:
            analytics = await tenant_components.registry.get_analytics(metadata.id)
            if analytics is not None:
                # existing analytics
                if not analytics.equals(metadata):
                    # changed analytics
                    await tenant_components.registry.delete_analytics(metadata.id)
                    await tenant_components.registry.register_analytics(metadata)
                # else:
                    # existing but not change - do nothing
            else:
                # new analytics
                await tenant_components.registry.register_analytics(metadata)


    async def get_jaeger_url(self, tenant_id: str):
        _, tenant_config = await self.ensure_initialized(tenant_id)
        return tenant_config.jaeger_url or os.environ.get('JAEGER_URL')


    async def _invoke_send_spans_memory_store(self,
                                        file_content: str,
                                        tenant_id: str
                                        ):
        tenant_components, _ = await self.ensure_initialized(tenant_id)
        data_manager = tenant_components.data_manager
        traces, validate_warning = await data_manager.store_trace_logs(file_content)

        #analyze traces to fetch service name and from_date
        service_name = traces[0].service_name #even if several traces they all have the same service name
        earliest_time = None
        for trace in traces:
            if earliest_time is None or earliest_time > trace.start_time:
                earliest_time = trace.start_time
        return service_name, earliest_time, validate_warning, traces


    async def _invoke_send_spans_db_store(self,
                                          file_content: str,
                                          tenant_config: TenantConfig
                                        ):
        # Send spans to OTLP collector (configured via OTEL_COLLECTOR_SERVICE env var)
        traces, spans, validate_warning = parse_trace_logs(file_content)

        # Auto-configure collector based on OTEL_COLLECTOR_SERVICE environment variable
        service_name, from_date = send_spans(
            spans,
            tenant_id=tenant_config.tenant_id
            # endpoint=None triggers auto-configuration based on OTEL_COLLECTOR_SERVICE
        )
        return service_name, from_date, validate_warning, traces


    # TODO: Yuval should replace this with a call to the Jaeger collector API
    async def process_file(self,
                     file_content: str,
                     tenant_id: str,
                     return_source_traces_only: bool = False
                     ):
        tenant_components, tenant_config = await self.ensure_initialized(tenant_id)
        store_type = tenant_config.store_type

         # Parse the logs to get traces and spans
        if store_type == StoreType.MEMORY:
            service_name, from_date, validate_warning, traces= await self._invoke_send_spans_memory_store(file_content, tenant_id=tenant_config.tenant_id)
        else:
            service_name, from_date, validate_warning, traces = await self._invoke_send_spans_db_store(file_content, tenant_config)

        if not return_source_traces_only:
            if isinstance(from_date, (int, float)):
                from_date = datetime.fromtimestamp(from_date // 1e9)
            traces = await self.get_traces(service_name, from_date, None, tenant_config.tenant_id, None)
        else:
            traces = await self.format_traces(tenant_components, traces, None)

        # traces = await self.data_manager.store_trace_logs(file_content)
        # ### TODO: We need to handle a file uploaded with tasks and not traces (.json)
        return {
            "traces": traces,
            "warning": validate_warning
        }

    async def get_traces(self,
                     service_name: str,
                     from_date: datetime,
                     to_date: datetime | None,
                     tenant_id: str,
                     metric_status: dict | None = None
                     ):
        tenant_components, tenant_config = await self.ensure_initialized(tenant_id)
        traces = await self.get_raw_traces(service_name, from_date, to_date, tenant_id, metric_status)
        formatted_traces = await self.format_traces(tenant_components, traces, metric_status)

        return formatted_traces

    async def get_raw_traces(self,
                     service_name: str,
                     from_date: datetime,
                     to_date: datetime | None,
                     tenant_id: str,
                     metric_status: dict | None = None
                     ) -> list[BaseTraceComposite]:
        tenant_components, tenant_config = await self.ensure_initialized(tenant_id)
        traces = await BaseTraceComposite.get_traces(tenant_components.data_manager, service_name, from_date, to_date)

        return traces



    async def get_traces_with_content(self,
                     service_name: str,
                     from_date: datetime,
                     to_date: datetime | None,
                     tenant_id: str
                     ):
        tenant_components, tenant_config = await self.ensure_initialized(tenant_id)
        traces = await BaseTraceComposite.get_traces(tenant_components.data_manager, service_name, from_date, to_date)
        artifacts = {}
        for trace in traces:
            try:
                artifacts[trace.element_id] = await self.get_trace_artifacts(trace.element_id, with_spans=True, tenant_id=tenant_id)
            except Exception as e:
                artifacts[trace.element_id] = { "error" : e.args[0] }

        return self.format_traces_with_content(traces, artifacts)


    async def get_groups(self,
                     service_name: str,
                     tenant_id: str
                     ):
        tenant_components, tenant_config = await self.ensure_initialized(tenant_id)
        formatted_groups = []
        groups = await TraceGroupComposite.get_trace_groups(tenant_components.data_manager, service_name)
        for group in groups:
            traces_for_group = await group.traces
            formatted_groups.append(await self.format_group(group, traces_for_group))

        return formatted_groups

    async def get_group_traces(self,
                     service_name: str,
                     group_id: str,
                     tenant_id: str
                     ):
        tenant_components, _ = await self.ensure_initialized(tenant_id)

        trace_group = await TraceGroupComposite.get_by_id(tenant_components.data_manager, group_id)
        traces_for_group = await trace_group.traces
        formatted_traces = await self.format_traces(tenant_components, traces_for_group, None)

        workflow_list = []
        group_tasks = []
        group_metrics = []
        group_issues = []
        failure = None

        # iterate on child elements to force create before accessing the group
        for trace in traces_for_group:
            group_tasks.extend(await self._get_or_create_task(tenant_components, trace.element_id))
            # task workflow is discarded on the task level - group workflow will be created below
           

            ### TODO: revisit when applying metrics
            ### For now - there is no need to fetch the issues/metrics as they will be fetched per trace
            # group_metrics.extend(await self.get_trace_metrics(trace.element_id))
            # group_issues.extend(await self._get_or_create_issues(tenant_components, trace.element_id, False))

       
        
        # group = await tenant_components.data_manager.get_by_id(group_id, TraceGroup)
        # formatted_group = await self.format_group(group, traces_for_group)
        if len(traces_for_group) >= self.change_analytics_config["min_observations"]:
            exec_results = await tenant_components.executor.execution_results_data_manager.get_results_by_trace_or_group_id(RuntimeClient.DRIFT_ANALYTICS, [group_id])
            ran = False
            if group_id in exec_results:
                for result in exec_results[group_id]:
                    if result.status == ExecutionStatus.SUCCESS:
                        ran = True
            if not ran:
                input_model_class = await tenant_components.registry.get_pipeline_input_model(RuntimeClient.DRIFT_ANALYTICS)
                result = await tenant_components.executor.execute_analytics(
                    RuntimeClient.DRIFT_ANALYTICS,
                    input_model_class(trace_group_id=group_id)
                )

                if result.status != ExecutionStatus.SUCCESS:
                    print(result.error.message)
                    print(result.error.stacktrace)
                    raise Exception(result.error.message)

        return {
            "traces": formatted_traces,
            "metrics": [metric.model_dump() for metric in group_metrics],            
            "tasks": [task.model_dump() for task in group_tasks],
            "issues": [issue.model_dump() for issue in group_issues],
            "error": failure
        }






    async def _get_or_create_task(self, tenant_components: TenantComponents, trace_id):
        tasks = await BaseTraceComposite.get_tasks_for_trace(tenant_components.data_manager, trace_id)
        if not tasks:
            input_model_class = await tenant_components.registry.get_pipeline_input_model(RuntimeClient.TASK_ANALYTICS)
            result = await tenant_components.executor.execute_analytics(
                RuntimeClient.TASK_ANALYTICS,
                input_model_class(trace_id=trace_id)
            )

            ### TODO:  Validate failure/Success by status
            if result.error != None:
                print(result.error.message)
                print(result.error.stacktrace)
                raise Exception(result.error.message)
            else:
                tasks = await BaseTraceComposite.get_tasks_for_trace(tenant_components.data_manager, trace_id)

                input_model_class = await tenant_components.registry.get_pipeline_input_model(RuntimeClient.TASK_METRIC_ANALYTICS)
                result = await tenant_components.executor.execute_analytics(
                    RuntimeClient.TASK_METRIC_ANALYTICS,
                    input_model_class(trace_id=trace_id)
                )

                if result.error is not None:
                    error_msg = f"Plugin {RuntimeClient.TASK_METRIC_ANALYTICS} failed: {result.error.message}"
                    logger.error(error_msg)
                    logger.error(result.error.stacktrace)
                    # No longer raising exception to avoid blocking span retrieval
                    # raise Exception(error_msg)

        return tasks

    async def _get_or_create_issues(self, tenant_components: TenantComponents, trace_id, should_fail=True):
        """
        Get or create issues for a trace using all registered issue analytics plugins.
        
        Args:
            tenant_components: TenantComponents instance
            trace_id: ID of the trace to get/create issues for
            should_fail: Whether to raise exception on plugin failure
            
        Returns:
            Tuple of (issues_list, error_message)
        """
        # Get existing related issues for the trace
        related_issues = await (await BaseTraceComposite.get_by_id(tenant_components.data_manager, trace_id)).related_issues

        # Get all existing issues for the trace
        issues_obj = await BaseTraceComposite.get_all_issues_for_trace(tenant_components.data_manager, trace_id)

        # If no issues exist, try to generate them using all registered issue plugins
        if not issues_obj:
            errors = []

            # Iterate through all registered issue analytics plugins
            for plugin_id in RuntimeClient.ISSUE_ANALYTICS_PLUGINS:
                try:
                    # Check if this plugin has already run successfully for this trace
                    exec_results = await tenant_components.executor.execution_results_data_manager.get_results_by_trace_or_group_id(
                        plugin_id, trace_id
                    )

                    # Check if plugin already ran successfully
                    plugin_already_ran = False
                    if trace_id in exec_results:
                        for result in exec_results[trace_id]:
                            if result.status == ExecutionStatus.SUCCESS:
                                plugin_already_ran = True
                                break

                    # If plugin hasn't run successfully, execute it
                    if not plugin_already_ran:
                        logger.info(f"Running issue analytics plugin: {plugin_id} for trace: {trace_id}")

                        input_model_class = await tenant_components.registry.get_pipeline_input_model(plugin_id)
                        result = await tenant_components.executor.execute_analytics(
                            plugin_id,
                            input_model_class(trace_id=trace_id)
                        )

                        # Handle execution errors
                        if result.error is not None:
                            error_msg = f"Plugin {plugin_id} failed: {result.error.message}"
                            logger.error(error_msg)
                            logger.error(result.error.stacktrace)
                            errors.append(error_msg)

                            if should_fail:
                                raise Exception(error_msg)
                    else:
                        logger.info(f"Plugin {plugin_id} already ran successfully for trace: {trace_id}")

                except Exception as e:
                    error_msg = f"Error running plugin {plugin_id}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

                    if should_fail:
                        raise Exception(error_msg)

            # After running all plugins, fetch all issues created for the trace
            issues_obj = await BaseTraceComposite.get_all_issues_for_trace(tenant_components.data_manager, trace_id)

            # If there were errors but we're not failing, return the error message
            if errors and not should_fail:
                return related_issues, "; ".join(errors)

            input_model_class = await tenant_components.registry.get_pipeline_input_model(RuntimeClient.ISSUE_DIST_ANALYTICS)
            result = await tenant_components.executor.execute_analytics(
                RuntimeClient.ISSUE_DIST_ANALYTICS,
                input_model_class(trace_id=trace_id)
            )

            # Handle execution errors
            if result.error is not None:
                error_msg = f"Plugin {RuntimeClient.ISSUE_DIST_ANALYTICS} failed: {result.error.message}"
                logger.error(error_msg)
                logger.error(result.error.stacktrace)
                errors.append(error_msg)

        # Combine related issues with newly found/created issues
        if issues_obj:
            related_issues.extend(issues_obj)


        return related_issues, None



    



    

    # ### TODO: @Inna Should move this logic to platform!!!
    # def _filter_by_type(self, elements: List[BaseArtifact], type_name: Type[T]) -> List[T]:
    #     return [element for element in elements if type(element) == type_name]

    def _create_trajectory_element(self, idx, title, text, annotation):
        return TrajectoryElement(
            type = annotation.annotation_type,
            title=title,
            message = text if (annotation.segment_start is None or annotation.segment_end is None) \
                else text[annotation.segment_start:annotation.segment_end],
            start_index = idx)

    async def _get_or_create_annotations(self, tenant_components: TenantComponents, trace_id, tasks : list[TaskComposite], should_fail=True):
        all_steps = []
        annotations = await BaseTraceComposite.get_all_annotations_for_trace(tenant_components.data_manager, trace_id)
        if not annotations:
            input_model_class = await tenant_components.registry.get_pipeline_input_model(RuntimeClient.ANNOTATION_ANALYTICS)
            result = await tenant_components.executor.execute_analytics(
                RuntimeClient.ANNOTATION_ANALYTICS,
                input_model_class(trace_id=trace_id)
            )

            ### TODO:  Validate failure/Success by status
            if result.error != None:
                print(result.error.message)
                print(result.error.stacktrace)
                if should_fail:
                    raise Exception(result.error.message)
                else:
                    return None, result.error.message

            input_model_class = await tenant_components.registry.get_pipeline_input_model(RuntimeClient.PATTERN_ANNOTATION_ANALYTICS)
            result = await tenant_components.executor.execute_analytics(
                RuntimeClient.PATTERN_ANNOTATION_ANALYTICS,
                input_model_class(trace_id=trace_id)
            )

            ### TODO:  Validate failure/Success by status
            if result.error != None:
                print(result.error.message)
                print(result.error.stacktrace)
                if should_fail:
                    raise Exception(result.error.message)
                else:
                    return None, result.error.message

            annotations = await BaseTraceComposite.get_all_annotations_for_trace(tenant_components.data_manager, trace_id)

        # sort order is meaningful only within context of task and input/output type - not globally!!!
        annotations = sorted(annotations, key=lambda x: x.segment_start)

        for task in tasks:
            #TODO: maybe we should change the const mapping so it will be better accessed?
            trajectory_elements = []

            idx = 0
            for annotation in annotations:
                if (task.element_id in annotation.related_to_ids):
                    text = None
                    if annotation.path_to_string and annotation.path_to_string in task.input:
                        text = task.input[annotation.path_to_string]
                    elif annotation.path_to_string and annotation.path_to_string in task.output:
                        text = task.output[annotation.path_to_string]
                    else:
                        text = f"{annotation.annotation_content}"

                    if text:
                        trajectory_elements.append(self._create_trajectory_element(idx, annotation.annotation_title, text, annotation))
                        idx += 1

            if trajectory_elements:
                all_steps.append(TrajectoryStep(element_id=f'trajectory_step_{task.element_id}',
                                    # root_id=task.root_id,
                                    task_id=task.element_id, task_name=task.name,
                                    elements=trajectory_elements))

        return all_steps, None

    async def get_trace_artifacts(self,
                     trace_id: str,
                     with_spans: bool,
                     tenant_id: str
                     ):
        tenant_components, _ = await self.ensure_initialized(tenant_id)

        spans = await BaseSpanComposite.get_spans_for_trace(data_manager=tenant_components.data_manager, trace_id=trace_id) if with_spans else None
        tasks = []
        annoations = []
        tasks = await self._get_or_create_task(tenant_components, trace_id)
        if tasks:
            annoations, _ = await self._get_or_create_annotations(tenant_components, trace_id, tasks)


            #print(annoations)
            

            #trace = BaseTrace(element_id=trace_id, name=trace_id)
            issues, _ = await self._get_or_create_issues(tenant_components, trace_id)
            #issues = await self.data_manager.get_elements_related_to(trace)
            ### TODO: how to get elements for workflow?
            # issues.append(await self.data_manager.get_elements_related_to(workflow_obj))

            metrics = await self.get_trace_metrics(trace_id, tenant_id=tenant_id)


           
            advanced_status = RuntimeClient.STATUS_NOT_STARTED
            if metrics != None and len(metrics) > 0:
                for metric in metrics:
                    if metric.plugin_metadata_id == RuntimeClient.EVAL_METRICS:
                        advanced_status = RuntimeClient.STATUS_NOT_STARTED

            analysis_status = {
                "basic": RuntimeClient.STATUS_READY if tasks != None and len(tasks) > 0 else RuntimeClient.STATUS_NOT_STARTED,
                "advanced": advanced_status,
            }

            full_metrics = metrics 

            return {
                    "spans": [span.model_dump() for span in spans] if spans else None,
                    "tasks": [task.model_dump() for task in tasks],
                    "metrics": [metric.model_dump() for metric in full_metrics],                    
                    "issues": [issue.model_dump() for issue in issues],
                    "trajectory" : annoations,
                    "analysisStatus": analysis_status
            }
        else:
            analysis_status = {
                "basic": RuntimeClient.STATUS_EMPTY,
                "advanced": RuntimeClient.STATUS_EMPTY,
            }

            return {
                    "error": "No tasks found for the provided trace.",
                    "spans": [span.model_dump() for span in spans] if spans else None,
                    "tasks": [task.model_dump() for task in tasks] if tasks else [],
                    "metrics": [],                    
                    "issues": [],
                    "trajectory" : [],
                    "analysisStatus": analysis_status
            }



    async def get_trace_metrics(self,
                     trace_id: str,
                     tenant_id: str
                     ) -> list[MetricComposite]:
        tenant_components, _ = await self.ensure_initialized(tenant_id)

        # result = []
        metrics = await BaseTraceComposite.get_all_metrics_for_trace(tenant_components.data_manager, trace_id)
        # if metrics:
        #     for metric in metrics:
        #         result.append(metric)

        return metrics

    async def launch_eval_metrics(self,
                     trace_id: str,
                     tenant_id: str
                     ):
        tenant_components, _ = await self.ensure_initialized(tenant_id)

        input_model_class = await tenant_components.registry.get_pipeline_input_model(RuntimeClient.EVAL_METRICS)
        result = await tenant_components.executor.execute_analytics(
            RuntimeClient.EVAL_METRICS,
            input_model_class(trace_id=trace_id)
        )

        ### TODO:  Validate failure/Success by status
        metrics = None
        if result.error != None:
            print(result.error.message)
            print(result.error.stacktrace)
            raise Exception(result.error.message)
        else:
            # Assuming metrics is unique and returned only once
            if 'task_metrics' in result.output_result:
                metrics = result.output_result['task_metrics']

        return metrics


    async def delete_trace(self,
                     trace_id: str
                     ):
        pass

    async def create_group(self,
                    service_name: str,
                    group_name: str,
                    traces_ids: list[str],
                    tenant_id: str
                ):
        tenant_components, _ = await self.ensure_initialized(tenant_id)


        trace_group_id=f"Group:{group_name}"
        trace_group = await TraceGroupComposite.create(
            tenant_components.data_manager,
            element_id=trace_group_id,
            root_id="None",
            name=group_name,
            traces_ids= traces_ids,
            service_name=service_name
        )
        traces_for_group = await trace_group.traces

        return {
            "success": f"Successfully created group_id: {trace_group.element_id}",
            "group": await self.format_group(trace_group, traces_for_group)
        }


    def set_tenant_config(self,
                          tenant_id: str,
                          tenant_config: dict[str, Any]

    ):
        tenant_config_service.set_tenant_config(tenant_id, tenant_config)




    async def get_instana_artifacts(self,
                    spans: list,
                    tenant_id: str
                ):
        tenant_components, _ = await self.ensure_initialized(tenant_id)


        raise NotImplementedError("Instana artifacts are currently not supported!")

        # metrics = None # await self.data_manager.get_children(trace_id, Metric)
        # tasks = None
        # if len(self.span_analytics_metadata) == 0:
        #     self.span_analytics_metadata: List[AnalyticsMetadata] = await self.registry.list_analytics()

        # for metadata in self.span_analytics_metadata:
        #     input_model_class = await self.registry.get_pipeline_input_model(metadata.id)
        #     result = await self.executor.execute_analytics(
        #         metadata.id,
        #         input_model_class(spans=spans)
        #     )

        #     ### TODO:  Validate failure/Success by status
        #     if result.error != None:
        #         print(result.error.message)
        #         print(result.error.stacktrace)
        #         return { "error": result.error.message }
        #     else:
        #         # Assuming task_list is unique and returned only once
        #         if 'task_list' in result.output_result:
        #             tasks = result.output_result['task_list']
        #         # TODO: When additional analytics providde metrics - might need to add to result

        # return {
        #         "spans": spans,
        #         "tasks": tasks,
        #         # "metrics": metrics
        #         }


    async def format_traces(self, tenant_components:  TenantComponents, traces: list[BaseTraceComposite], metric_status: dict | None):
        formatted_traces = {}
        trace_ids = [trace.element_id for trace in traces]

        processed_tasks_for_trace_ids = await tenant_components.executor.execution_results_data_manager.get_results_by_trace_or_group_id(RuntimeClient.TASK_ANALYTICS, trace_ids)
        metrics_for_trace_ids = await BaseTraceComposite.get_all_metrics_for_traces(tenant_components.data_manager, trace_ids)

        for trace in traces:
            analysis_status = {}
            issue_dist = None
            if trace.element_id not in processed_tasks_for_trace_ids:
                analysis_status["basic"] = RuntimeClient.STATUS_NOT_STARTED
            else:
                for task_result in processed_tasks_for_trace_ids[trace.element_id]:
                    if task_result.status == ExecutionStatus.SUCCESS:
                        if task_result.output_result['task_list']:
                            analysis_status["basic"] = RuntimeClient.STATUS_READY
                            break
                        else:
                            analysis_status["basic"] = RuntimeClient.STATUS_EMPTY
                    else:
                        analysis_status["basic"] = RuntimeClient.STATUS_FAILED

            if trace.element_id in metrics_for_trace_ids:
                analysis_status["advanced"] = RuntimeClient.STATUS_NOT_STARTED
                for metric in metrics_for_trace_ids[trace.element_id]:
                    if metric.plugin_metadata_id == RuntimeClient.EVAL_METRICS:
                        analysis_status["advanced"] = RuntimeClient.STATUS_READY
                    if metric.plugin_metadata_id == RuntimeClient.ISSUE_DIST_ANALYTICS:
                        issue_dist = metric.value
            else:
                key = f"{trace.element_id}:{RuntimeClient.EVAL_METRICS}"
                if metric_status and key in metric_status:
                    analysis_status["advanced"] = metric_status[key]['status']
                else:
                    analysis_status["advanced"] = RuntimeClient.STATUS_NOT_STARTED


            formatted_traces[trace.element_id] = {
                'id': trace.element_id,
                'timestamp': trace.start_time,
                'serviceName': trace.service_name,
                'spansNum': trace.num_of_spans,
                'analysisStatus': analysis_status,
                'issue_dist': issue_dist
            }

        return list(formatted_traces.values())

    async def format_group(self, group: TraceGroupComposite, traces: list[BaseTraceComposite]):
        first_start = None
        last_end = None
        num_of_spans = 0
        trace_count = 0
        for trace in traces:
            if trace.start_time and (not first_start or \
                                     trace.start_time < first_start):
                first_start = trace.start_time
            if trace.end_time and (not last_end or \
                                   trace.end_time > last_end):
                last_end = trace.end_time
            if trace.num_of_spans:
                num_of_spans += trace.num_of_spans
            trace_count += 1

        return {
            "id": f"{group.element_id}",
            "name": group.name,
            'timestamp': first_start,
            'serviceName': group.service_name,
            'analysisStatus': {
                'basic': RuntimeClient.STATUS_READY,
                'advanced': RuntimeClient.STATUS_NOT_STARTED
            },
            'spansNum': num_of_spans,
            'traceCount': trace_count
        }

    def format_traces_with_content(self, traces: list[BaseTraceComposite], artifacts: dict[str, dict]):
        formatted_traces = {}
        for trace in traces:
            formatted_traces[trace.element_id] = {
                'id': trace.element_id,
                'startTime': trace.start_time,
                'serviceName': trace.service_name,
                'spansNum': trace.num_of_spans,
                'tasks': artifacts[trace.element_id]["tasks"] if "tasks" in artifacts[trace.element_id] else None,
                'spans': artifacts[trace.element_id]["spans"] if "spans" in artifacts[trace.element_id] else None,                
                'error': artifacts[trace.element_id]["error"] if "error" in artifacts[trace.element_id] else None
            }

        return list(formatted_traces.values())

    async def get_detailed_metrics_traces(self,
                                        service_name: str,
                                        tenant_id: str,
                                        agent_ids_filter: list[str] | None = None,
                                        start_time: datetime | None = None,
                                        end_time: datetime | None = None,
                                        pagination: tuple[int, int] | None = None
                                        ) -> list[AggregateMetric]:
        """
        Get detailed metrics per trace for a service, including LLM usage data.
        
        Args:
            service_name: Name of the service to get traces for
            agent_ids_filter: Optional list of agent IDs to filter by
            start_time: Optional start time for filtering traces
            end_time: Optional end time for filtering traces
            pagination: Optional tuple of (start_index, end_index) for pagination
            tenant_id: Optional tenant ID (uses default if not provided)
            
        Returns:
            List of AggregateMetric, one per trace containing duration, issues, and LLM usage
        """
        tenant_components, _ = await self.ensure_initialized(tenant_id)

        try:
            return await create_detailed_metrics_traces(
                data_manager=tenant_components.data_manager,
                registry=tenant_components.registry,
                execution_engine=tenant_components.executor,
                task_analytics_name=RuntimeClient.TASK_ANALYTICS,
                service_name=service_name,
                tenant_components=tenant_components,
                tenant_id=tenant_id,
                agent_ids_filter=agent_ids_filter,
                start_time=start_time,
                end_time=end_time,
                pagination=pagination
            )
        except Exception as e:
            raise Exception(f"Error getting detailed metrics for service {service_name}: {str(e)}") from e

    async def get_spans(self,
                        trace_id: str,
                        tenant_id: str
                        ) -> list[BaseSpanComposite]:
            """
            Get all spans for a specific trace.
            
            Args:
                trace_id: ID of the trace to get spans for
                tenant_id: Optional tenant ID (uses default if not provided)
                
            Returns:
                List of BaseSpanComposite objects for the trace
            """
            tenant_components, _ = await self.ensure_initialized(tenant_id)

            try:
                return await tenant_components.data_manager.get_spans(trace_id)
            except Exception as e:
                raise Exception(f"Error getting spans for trace {trace_id}: {str(e)}") from e

    async def get_combined_agent_summary_metrics_traces_optimized(self,
                                    service_name: str,
                                    tenant_id: str,
                                    agent_ids_filter: list[str] | None = None,
                                    start_time: datetime | None = None,
                                    end_time: datetime | None = None,
                                    include_overall_metric: bool = True
                                    ) -> list[AggregateMetric]:
            """
            Get both overall and per-agent summary metrics with maximum optimization.
            Returns len(agent_ids_filter) + 1 metrics total.
            
            Args:
                service_name: Name of the service to get traces for
                agent_ids_filter: Optional list of agent IDs to filter by
                start_time: Optional start time for filtering traces
                end_time: Optional end time for filtering traces
                tenant_id: Optional tenant ID (uses default if not provided)
                
            Returns:
                List of AggregateMetric: one overall + one per agent
            """
            tenant_components, _ = await self.ensure_initialized(tenant_id)

            try:
                return await create_combined_agent_summary_metrics_traces_optimized(
                    service_name=service_name,
                    tenant_components=tenant_components,
                    tenant_id=tenant_id,
                    agent_ids_filter=agent_ids_filter,
                    start_time=start_time,
                    end_time=end_time,include_overall_metric=include_overall_metric

                )
            except Exception as e:
                raise Exception(f"Error getting combined agent summary metrics for service {service_name}: {str(e)}") from e

    ################################## NEW METHODS ##########################
    async def process_event(
        self,
        analytics_id: str,
        tenant_id: str,
        trace_id: str = None,
        trace_group_id: str = None,
        creating_plugin_id: str = None,
        metadata: dict = None,
        timestamp: datetime = None
    ):
        """
        Process event by executing specified analytics.
        
        Args:
            analytics_id: ID of analytics to execute
            trace_id: Optional trace ID
            trace_group_id: Optional trace group ID  
            tenant_id: Tenant identifier
            creating_plugin_id: Optional plugin ID that created the event
            metadata: Optional metadata dictionary
            timestamp: Optional timestamp
        """
        tenant_components, _ = await self.ensure_initialized(tenant_id)

        # Get analytics metadata from registry
        analytics_metadata = await tenant_components.registry.get_analytics(analytics_id)
        if not analytics_metadata:
            raise ValueError(f"Analytics {analytics_id} not found in registry")

        # Get input model class for this analytics
        input_model_class = await tenant_components.registry.get_pipeline_input_model(analytics_id)

        # Create input data with trace_id or trace_group_id
        if trace_id:
            result = await tenant_components.executor.execute_analytics( # type: ignore
                    analytics_id=analytics_id,
                    input_model=input_model_class(trace_id=trace_id),
                )
        else:
            result = await tenant_components.executor.execute_analytics( # type: ignore
                    analytics_id=analytics_id,
                    input_model=input_model_class(trace_group_id=trace_group_id)
                )

        return result


def process_span_json_for_create(json_data: dict[str, Any]) -> dict[str, Any]:
    """
    Process JSON span data to extract parameters for the create function.
    
    Args:
        json_data: The JSON data dictionary
        
    Returns:
        Dictionary with all parameters needed for the create function
    """

    # Parse datetime strings
    def parse_datetime(dt_string: str) -> datetime:
        # Handle different datetime formats
        if dt_string.endswith('Z'):
            # ISO format with Z
            return datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        else:
            # Try standard ISO format
            return datetime.fromisoformat(dt_string)

    # Extract basic required parameters
    name = json_data.get('name', '')
    trace_id = json_data.get('context', {}).get('trace_id', '')
    span_id = json_data.get('context', {}).get('span_id', '')

    # Parse SpanKind enum
    kind_str = json_data.get('kind', 'SpanKind.INTERNAL')
    if kind_str.startswith('SpanKind.'):
        kind_value = kind_str.replace('SpanKind.', '')
    else:
        kind_value = kind_str

    try:
        kind = SpanKind(kind_value)
    except ValueError:
        # Fallback to INTERNAL if unknown kind
        kind = SpanKind.INTERNAL

    # Parse timestamps
    start_time = parse_datetime(json_data.get('start_time'))
    end_time = parse_datetime(json_data.get('end_time'))

    # Extract service name from resource attributes
    service_name = json_data.get('resource', {}).get('attributes', {}).get('service.name', 'unknown_service')

    # Extract status code
    status_code = json_data.get('status', {}).get('status_code', 'OK')

    # Optional parameters
    parent_id = json_data.get('parent_id')
    attributes = json_data.get('attributes', {})

    # Process events
    events = []
    events_data = json_data.get('events', [])
    for event_data in events_data:
        event_name = event_data.get('name', '')
        event_timestamp = parse_datetime(event_data.get('timestamp', datetime.now().isoformat()))
        event_attributes = event_data.get('attributes', {})

        span_event = SpanEvent(
            name=event_name,
            timestamp=event_timestamp,
            attributes=event_attributes
        )
        events.append(span_event)

    # Process links
    links = json_data.get('links', [])

    # Extract resource attributes for **kwargs
    resource_attributes = json_data.get('resource', {}).get('attributes', {})
    # Remove service.name since it's handled separately
    resource_attributes = {k: v for k, v in resource_attributes.items() if k != 'service.name'}

    return {
        'name': name,
        'trace_id': trace_id,
        'span_id': span_id,
        'kind': kind,
        'start_time': start_time,
        'end_time': end_time,
        'service_name': service_name,
        'status_code': status_code,
        'parent_id': parent_id,
        'attributes': attributes,
        'events': events,
        'links': links,
        **resource_attributes
    }

async def create_span_from_json(data_manager, json_string: str):
    """
    Complete function to process JSON string and create span.
    
    Args:
        data_manager: Your DataManager object
        json_string: JSON string representation of span data
        
    Returns:
        Result from the create function
    """

    # Parse JSON string if it's a string, otherwise assume it's already a dict
    if isinstance(json_string, str):
        json_data = json.loads(json_string)
    else:
        json_data = json_string

    # Process the data
    create_params = process_span_json_for_create(json_data)

    # Call the create function (assuming it's a class method)
    # Replace YourSpanClass with the actual class name
    result = await BaseSpanComposite.create(
        data_manager=data_manager,
        **create_params
    )

    return result


