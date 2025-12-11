import sys, os, re ,json,uuid, inspect, platform
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
# from agent_analytics.instrumentation.traceloop.instrumentor import Instrumentor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
from langtrace_python_sdk import langtrace
# from traceloop.sdk import Traceloop
# use extended traceloop class 
# from agent_analytics.instrumentation.traceloop.sdk import Traceloop

from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.environ.get("PROJECT_ROOT", ""))
from datetime import datetime, timezone


def find_nearest_src_path_with_caller_directory(caller_directory):
    caller_directory = os.path.abspath(caller_directory)

    # Traverse up the directory structure to find the nearest 'src' to the end
    current_directory = caller_directory
    nearest_src_path = None
    while current_directory and not os.path.ismount(current_directory):
        if os.path.basename(current_directory) == 'src':
            nearest_src_path = current_directory
        current_directory = os.path.dirname(current_directory)

    if nearest_src_path:
        return nearest_src_path

    raise Exception("Directory 'src' not found in the directory structure for '{}'".format(caller_directory))

def load_log_file(log_path: str):
    """
    :param log_path: path of log file containing the output of multiple opentelemetry ReadableSpan as a json file.
    :return: list of loaded spans/traces
    """
    with open(log_path, 'r') as file:
        file_content = file.read()

        return load_log_content(file_content)

def load_log_content(log_file_content: str):
    """
    :param log_file_content: content of file containing the output of multiple opentelemetry ReadableSpan as a json file.
    :return: list of loaded spans/traces
    """
    json_objects, start = [],0

    while start < len(log_file_content):
        try:
            json_obj, end = json.JSONDecoder().raw_decode(log_file_content[start:].lstrip())  # Strip leading spaces
            json_objects.append(json_obj)
            start += end+1
        except json.JSONDecodeError:
            break
    return json_objects

def get_unique_id():
    return uuid.uuid4().hex


def datetime_converter(obj):
    if isinstance(obj, datetime):
        return obj.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
    else:
        try:
            json.dumps(obj)  # Attempt to serialize the object
            return obj  # If serializable, return the object
        except (TypeError, OverflowError):
            return str(id(obj))  # If not serializable,return id of the object

def join_variables(var1, var2, separator="\n"):
    if isinstance(var1, dict) and isinstance(var2, dict):
        merged_dict = {}
        all_keys = set(var1) | set(var2)  # Union of keys from both dictionaries
        for key in all_keys:
            v1 = var1.get(key)
            v2 = var2.get(key)
            if v1 is None:
                merged_dict[key] = v2
            elif v2 is None:
                merged_dict[key] = v1
            else:
                merged_dict[key] = _to_list(v1) + _to_list(v2)  # Merge values as lists
        return merged_dict

    elif isinstance(var1, (list, tuple)) and isinstance(var2, (list, tuple)):
        return list(var1) + list(var2)  # Convert tuples to lists before merging

    else:
        return f"{str(var1)}{separator}{str(var2)}"


def _to_list(value):
    """Ensures the value is a list for consistent merging."""
    return value if isinstance(value, list) else [value]


def load_json_str_to_dict(json_str, field_name=None, max_depth=5):
    """
    Safely loads JSON strings, handling cases of multiple nested JSONs.

    Args:
        json_str: The JSON string to parse
        field_name: Field name to use if result is a primitive value
        max_depth: Maximum number of parsing attempts to prevent infinite loops

    Returns:
        The parsed object (dict, list, etc.) or appropriately wrapped primitive value
    """

    result = json_str
    depth = 0

    while isinstance(result, str) and depth < max_depth:
        try:
            parsed = json.loads(result)
            if parsed == result:
                break
            result = parsed
            depth += 1
        except json.JSONDecodeError:
            break

    if not isinstance(result, dict) and field_name:
        result = {field_name: result}

    return result