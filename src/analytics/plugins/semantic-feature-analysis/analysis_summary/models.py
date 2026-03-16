"""
Analysis summary artifact models.

These models are specific to the analysis_summary plugin.
"""

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from models.artifacts import Artifact


class TopIssue(BaseModel):
    """Prioritized issue from analysis summary."""
    model_config = ConfigDict(extra='allow')
    
    rank: int  # 1-5
    issue_id: str
    issue_name: str
    severity: str
    category: str
    
    # Why it's critical
    impact_summary: str  # LLM-generated explanation of impact
    root_cause_summary: str  # LLM-generated root cause
    fix_priority_reason: str  # Why this should be fixed first
    
    # References
    related_artifact_ids: list[str] = Field(default_factory=list)
    related_artifact_kinds: list[str] = Field(default_factory=list)


class KeyInsight(BaseModel):
    """Key insight from analysis."""
    model_config = ConfigDict(extra='allow')
    
    insight_type: str  # "architectural", "performance", "reliability", "code_quality"
    title: str
    description: str
    evidence: list[str] = Field(default_factory=list)  # Artifact IDs supporting this
    actionable: bool = True


class AnalysisSummaryArtifact(Artifact):
    """
    Executive summary of entire analysis session.
    
    Produced by analysis_summary plugin (LLM-based) from ALL artifacts.
    Synthesizes findings and prioritizes top issues.
    """
    artifact_kind: str = "analysis_summary"
    
    # Session overview
    session_summary: str  # LLM-generated overview
    codebase_path: str
    phases_completed: list[str] = Field(default_factory=list)
    
    # Prioritized findings
    top_issues: list[TopIssue] = Field(default_factory=list)  # Top 1-5 issues
    key_insights: list[KeyInsight] = Field(default_factory=list)
    
    # Artifact inventory
    artifacts_analyzed: dict[str, int] = Field(default_factory=dict)  # {kind: count}
    
    # Recommendations
    next_steps: list[str] = Field(default_factory=list)  # Actionable recommendations
    
    # Visualization context (if available)
    graph_summary: Optional[str] = None  # LLM interpretation of graph patterns
    trajectory_summary: Optional[str] = None  # LLM interpretation of execution patterns
    
    # Report
    markdown_report: Optional[str] = None  # Full markdown report
