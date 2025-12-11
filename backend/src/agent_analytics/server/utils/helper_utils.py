import uuid

TRACE_GROUP_NAMESPACE = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')  # Example namespace
def create_trace_group_name(trace_ids: list[str]) -> str:
    """
    Create a deterministic, constant-length trace group name from trace IDs.
    
    Args:
        trace_ids: List of trace IDs (order matters)
    
    Returns:
        A UUID string representing the trace group
    
    Raises:
        ValueError: If trace_ids is empty
    """
    if not trace_ids:
        raise ValueError("trace_ids cannot be empty")

    # Sort to ensure consistent ordering (remove if order should be preserved)
    sorted_ids = sorted(trace_ids)

    # Create canonical string representation
    canonical_name = "|".join(sorted_ids)

    # Generate deterministic UUID5
    group_uuid = uuid.uuid5(TRACE_GROUP_NAMESPACE, canonical_name)

    return str(group_uuid)
