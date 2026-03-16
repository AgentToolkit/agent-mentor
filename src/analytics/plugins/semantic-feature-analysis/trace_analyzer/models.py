"""Simple artifact models for experiment pipeline plugins."""

from typing import Any, Dict, Optional

from models.artifacts import Artifact


class ExperimentArtifact(Artifact):
    """Generic artifact for experiment pipeline data (node_traces, cluster_info, etc.)."""

    artifact_kind: str = "experiment"
    node_name: Optional[str] = None
