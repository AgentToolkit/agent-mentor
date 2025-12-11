import inspect
import json
from pathlib import Path
from agent_analytics_common.interfaces.action import ActionKind, ActionCode
from agent_analytics.instrumentation.reportable import ReportableAction


def get_code_id(func):
    """Extract code identifier from a function."""
    try:
        actual_func = inspect.unwrap(func)  # handle partials and decorators
        code = actual_func.__code__
        filename = Path(code.co_filename).name
        lineno = code.co_firstlineno
        module = getattr(actual_func, "__module__", "<unknown>")
        qualname = getattr(actual_func, "__qualname__", repr(actual_func))
        return f"{filename}:{lineno}:{module}:{qualname}"
    except Exception:
        return "<unknown>:<unknown>:<unknown>:<unknown>"


def get_caller_code_id(skip_frames: int = 0):
    """
    Extract code identifier from the calling function by inspecting the call stack.
    Uses get_code_id internally for consistent formatting.

    Args:
        skip_frames: Number of additional frames to skip (default 0).
                    The function automatically skips its own frame and the immediate caller.
                    Use this to skip additional wrapper/decorator frames.

    Returns:
        A code_id string using the same format as get_code_id().
        If no valid caller is found, returns a location-based identifier.
    """
    try:
        # Get the current call stack
        # Frame 0: get_caller_code_id (this function)
        # Frame 1: The function that called get_caller_code_id (e.g., __init__)
        # Frame 2: The actual caller we want to identify
        frame_index = 2 + skip_frames
        stack = inspect.stack()

        # Check if we have enough frames
        if len(stack) <= frame_index:
            frame_index = len(stack) - 1 if len(stack) > 0 else 0

        if frame_index < 0 or len(stack) == 0:
            return "<unknown>:0:<unknown>:<module>"

        frame_info = stack[frame_index]

        # Try to find the function object from the frame
        # First, check if there's a 'self' or 'cls' which might give us a method
        frame_locals = frame_info.frame.f_locals
        frame_globals = frame_info.frame.f_globals

        # Try to get the function object
        func_name = frame_info.function
        func = None

        # Check locals first (for methods and local functions)
        if 'self' in frame_locals and hasattr(frame_locals['self'].__class__, func_name):
            func = getattr(frame_locals['self'].__class__, func_name)
        elif 'cls' in frame_locals and hasattr(frame_locals['cls'], func_name):
            func = getattr(frame_locals['cls'], func_name)
        elif func_name in frame_globals:
            potential_func = frame_globals[func_name]
            if callable(potential_func):
                func = potential_func

        # If we found a function, use get_code_id
        if func is not None and callable(func):
            return get_code_id(func)

        # Fallback: create code_id from frame information directly
        filename = Path(frame_info.filename).name
        lineno = frame_info.lineno
        module = frame_globals.get('__name__', '<unknown>')
        qualname = func_name if func_name != '<module>' else '<module>'

        return f"{filename}:{lineno}:{module}:{qualname}"

    except Exception:
        return "<unknown>:0:<unknown>:<unknown>"


def _get_action_from_func(func, kind: ActionKind = ActionKind.TOOL) -> ReportableAction:
    """
    Create a ReportableAction object from a Python function by inspecting its signature.

    Args:
        func: The function to inspect
        kind: The ActionKind to assign (defaults to TOOL)

    Returns:
        ReportableAction object with code metadata populated
    """
    sig = inspect.signature(func)
    input_schema = {
        name: {
            "annotation": str(param.annotation) if param.annotation != inspect.Parameter.empty else None,
            "default": str(param.default) if param.default != inspect.Parameter.empty else None,
            "kind": param.kind.name,
        }
        for name, param in sig.parameters.items()
    }

    output_schema = (
        str(sig.return_annotation) if sig.return_annotation != inspect.Signature.empty else None
    )

    # Extract name and description from function
    func_name = getattr(func, '__name__', None)
    func_description = None
    if hasattr(func, '__doc__') and func.__doc__:
        func_description = func.__doc__.strip()

    # Create ActionCode object with all code-related attributes
    action_code = ActionCode(
        id=get_code_id(func),
        language="python",
        input_schema=json.dumps(input_schema),  # ActionCode expects JSON string
        output_schema=output_schema,
        body=None  # Don't include source code by default
    )

    # Create ReportableAction with all attributes at once
    action = ReportableAction(
        kind=kind,
        name=func_name,
        description=func_description,
        code=action_code
    )

    return action
