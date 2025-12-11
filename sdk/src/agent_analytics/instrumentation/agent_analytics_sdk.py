import os
import inspect
import re
import platform
import sys
from enum import Enum
from typing import Optional
import warnings

from opentelemetry.sdk.trace.export import SpanExporter, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GRPCSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HTTPSpanExporter

from dotenv import load_dotenv
load_dotenv()

# Get Agent Analytics extended frameworks
from .traceloop.sdk import Traceloop  # noqa: E402
from .configs import (  # noqa: E402
    BaseExporterConfig,
    CustomExporterConfig,
    LogExporterConfig,
    OTLPCollectorConfig,
    RemoteExporterConfig
)

_split_pattern = re.compile(r'\W+')


class agent_analytics_sdk:
    """
    A namespace to handle initialization and configuration of logging and tracing
    for different tracer types.

    Attributes:
        SUPPORTED_TRACER_TYPES (list): Supported tracer types for the SDK.
    """
    class SUPPORTED_TRACER_TYPES(Enum):
        LOG = 1
        REMOTE = 2
        CUSTOM = 3

    @staticmethod
    def get_logs_dir_and_filename(logs_dir_path: str = None, log_filename: str = None):
        """
        Get the directory and filename for log files.

        If not provided, the directory defaults to a "log" folder in the caller's directory,
        and the filename defaults to the caller's file name.

        Args:
            logs_dir_path (str, optional): Custom path for the logs directory.
            log_filename (str, optional): Custom name for the log file.

        Returns:
            tuple: A tuple containing the log directory path and the log filename.

        Example:
            logs_dir, log_file = agent_analytics_sdk.get_logs_dir_and_filename()
        """
        # Get the caller's file information (two frames up in the stack)
        try:
            caller_frame = inspect.stack()[2]
            caller_file_path = os.path.abspath(caller_frame.filename)
            caller_dir = os.path.dirname(caller_file_path)
            caller_file_name = os.path.splitext(os.path.basename(caller_file_path))[0]
        except Exception:
            caller_dir = os.getcwd()
            caller_file_name = "default"

        logs_dir_path = logs_dir_path if logs_dir_path else os.path.join(caller_dir, "log")

        if not os.path.exists(logs_dir_path):
            os.makedirs(logs_dir_path)

        log_filename = f"{log_filename}.log" if log_filename else f"{caller_file_name}_otel.log"

        return logs_dir_path, log_filename

    @staticmethod
    def initialize_observability(
            config: Optional[BaseExporterConfig] = None,
            custom_exporter: Optional[SpanExporter] = None,
            **kwargs,
            ) -> SpanExporter:
        """
        Initialize observability using configuration-based tracer type inference.

        The tracer type is automatically determined from the config class:
        - LogExporterConfig → File-based logging
        - RemoteExporterConfig/OTLPCollectorConfig → OTLP remote collection
        - CustomExporterConfig → Custom exporter
        - None → File-based logging with default configuration

        Args:
            config (Optional[BaseExporterConfig]): Configuration object that determines the tracer type:
                - LogExporterConfig for file-based logging
                - RemoteExporterConfig or OTLPCollectorConfig for OTLP remote collection
                - CustomExporterConfig for custom exporters
                - None to use default file-based logging with default settings
            custom_exporter (Optional[SpanExporter]): Required when using CustomExporterConfig.
                The custom exporter instance to use.
            **kwargs: Additional keyword arguments passed to Traceloop.init()

        Returns:
            SpanExporter: The exporter object initialized for the inferred tracer type.

        Raises:
            ValueError: If configuration type is not recognized, if custom_exporter
                        is missing for CustomExporterConfig, or if required fields
                        are missing in the configuration.

        Example:
            # Default behavior - file-based logging with default settings
            exporter = agent_analytics_sdk.initialize_observability()

            # File-based logging with custom config
            config = LogExporterConfig(
                app_name="my_app",
                logs_dir_path="./logs",
                resource_attributes={"version": "1.0.0"}
            )
            exporter = agent_analytics_sdk.initialize_observability(config=config)

            # Remote OTLP collection
            config = RemoteExporterConfig(
                endpoint="http://localhost:4317",
                app_name="my_service",
                resource_attributes={"env": "prod"}
            )
            exporter = agent_analytics_sdk.initialize_observability(config=config)

            # Custom exporter
            config = CustomExporterConfig(app_name="custom_app")
            my_exporter = MyCustomExporter()
            exporter = agent_analytics_sdk.initialize_observability(
                config=config,
                custom_exporter=my_exporter
            )
        """
        # Default to LogExporterConfig if no config provided
        if config is None:
            config = LogExporterConfig()

        # Validate config type
        if not isinstance(config, (LogExporterConfig, RemoteExporterConfig,
                                   OTLPCollectorConfig, CustomExporterConfig)):
            raise ValueError(
                f"Unsupported configuration type: {type(config).__name__}. "
                "Expected LogExporterConfig, RemoteExporterConfig, "
                "OTLPCollectorConfig, or CustomExporterConfig."
            )

        # Generate app name if not provided
        if not config.app_name:
            machine_name = platform.node()
            user_name = _split_pattern.split(machine_name)[0]
            script_name = os.path.splitext(os.path.basename(sys.argv[0]))[0]
            app_name = f"{user_name}_{script_name}"
        else:
            app_name = config.app_name

        # Initialize exporter variable
        exporter = None

        # Initialize exporter based on config type
        if isinstance(config, LogExporterConfig):
            # File-based logging
            logs_dir_path, log_filename = agent_analytics_sdk.get_logs_dir_and_filename(
                config.logs_dir_path,
                config.log_filename
            )
            traceloop_log_file_path = os.path.join(logs_dir_path, log_filename)
            traceloop_log_file = open(traceloop_log_file_path, "w")
            exporter = ConsoleSpanExporter(out=traceloop_log_file)
            print(f"Observability logging initialized in {traceloop_log_file_path}")

        elif isinstance(config, (RemoteExporterConfig, OTLPCollectorConfig)):
            # Remote OTLP collection
            if not config.endpoint:
                raise ValueError("Endpoint must be provided in config.")

            if config.is_grpc:
                exporter = GRPCSpanExporter(
                    endpoint=config.endpoint,
                    timeout=config.timeout,
                    insecure=config.insecure,
                    headers=config.headers or {}
                )
            else:
                exporter = HTTPSpanExporter(
                    endpoint=config.endpoint,
                    timeout=config.timeout,
                    headers=config.headers or {}
                )

            print(f"Remote logging initialized. App name: {app_name}")

        elif isinstance(config, CustomExporterConfig):
            # Custom exporter
            if custom_exporter is None:
                raise ValueError(
                    "custom_exporter must be provided when using CustomExporterConfig."
                )
            exporter = custom_exporter
            print(f"Custom exporter logging initialized. App name: {app_name}")

        if "tracer_type" in kwargs:
            kwargs.pop("tracer_type")
        # Initialize Traceloop with the exporter
        Traceloop.init(
            disable_batch=True,
            exporter=exporter,
            app_name=app_name,
            resource_attributes=config.resource_attributes,
            telemetry_enabled=False,
            new_trace_on_workflow=config.new_trace_on_workflow,
            **kwargs,
        )

        return exporter

    # Deprecated method
    @staticmethod
    def initialize_logging(
            tracer_type: SUPPORTED_TRACER_TYPES = SUPPORTED_TRACER_TYPES.LOG,
            logs_dir_path: str = None,
            log_filename: str = None,
            config: OTLPCollectorConfig = None,
            resource_attributes: dict = {},
            custom_exporter: SpanExporter = None,
            new_trace_on_workflow: bool = False,
            disable_batch: bool = True,
            api_endpoint: str = None,
            headers: str = None
            ):
        """
        Initialize logging for the specified tracer type.

        Supports "log", "remote" and "custom" tracer types. Each type initializes
        logging with its respective configuration.

        Args:
            tracer_type (SUPPORTED_TRACER_TYPES, optional): The type of tracer to initialize.
                Options are SUPPORTED_TRACER_TYPES.LOG, SUPPORTED_TRACER_TYPES.REMOTE, SUPPORTED_TRACER_TYPES.CUSTOM,
                or SUPPORTED_TRACER_TYPES.CUSTOM. Defaults to LOG.
            logs_dir_path (str, optional): Directory path where log files should be saved (applies to LOG).
            log_filename (str, optional): Custom name for the log file (applies to LOG).
            config (OTLPCollectorConfig, optional): Configuration object for OTLP-based tracers
                (e.g., Instana). Required when using REMOTE.
            resource_attributes (dict, optional): Attributes to associate with the OpenTelemetry Resource.
            custom_exporter (Any, optional): Custom exporter instance to use when tracer_type is CUSTOM.

        Returns:
            Any: The exporter object initialized for the tracer type.

        Raises:
            ValueError: If an unsupported tracer type is specified or if required
                        configuration is missing.

        Example:
            exporter = agent_analytics_sdk.initialize_logging(
                tracer_type=SUPPORTED_TRACER_TYPES.LOG,
                log_filename="example.log"
            )
        """
        warnings.warn(
            "The initialize_logging() function will be removed in a future version. "
            "Please migrate to initialize_observability().",
            DeprecationWarning,
            stacklevel=2,
        )

        # Convert config to the new format
        if tracer_type == agent_analytics_sdk.SUPPORTED_TRACER_TYPES.LOG:
            config = LogExporterConfig(
                log_filename=log_filename,
                logs_dir_path=logs_dir_path,
                resource_attributes=resource_attributes,
                new_trace_on_workflow=new_trace_on_workflow,

            )
        elif tracer_type == agent_analytics_sdk.SUPPORTED_TRACER_TYPES.REMOTE:
            config.resource_attributes = resource_attributes
            config.new_trace_on_workflow = new_trace_on_workflow
        else:
            # Custom
            config = CustomExporterConfig(
                resource_attributes=resource_attributes,
                new_trace_on_workflow=new_trace_on_workflow,
                app_name=config.app_name if config else None
            )

        exporter = agent_analytics_sdk.initialize_observability(
            # tracer_type=tracer_type,
            config=config,
            custom_exporter=custom_exporter if custom_exporter else None
        )

        return exporter
