"""
Analysis Summary Plugin - LLM-based synthesis of all analysis results.

Reads ALL artifacts from the session and generates an executive summary
with prioritized issues, key insights, and actionable recommendations.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional
from collections import defaultdict

from analytics.base_plugin import AnalyticsPlugin
from utils.llm_service import get_llm_service
from analytics.plugins.analysis_summary.prompt import (
    OPERATIONAL_SUMMARY_SYSTEM_PROMPT,
    SECURITY_SUMMARY_SYSTEM_PROMPT,
    ANALYSIS_SUMMARY_USER_TEMPLATE,
    format_artifacts_for_summary,

)

# Local plugin-specific models
from analytics.plugins.analysis_summary.models import AnalysisSummaryArtifact


class AnalysisSummaryPlugin(AnalyticsPlugin):
    """
    LLM-based analysis summary plugin.
    
    Synthesizes ALL artifacts from the session into an executive summary
    with prioritized issues and actionable recommendations.
    
    Pipeline phase: summary (runs last)
    Produces: analysis_summary artifacts
    
    Features:
    - Reads all artifact kinds from session
    - Uses LLM to synthesize findings
    - Prioritizes top 1-5 critical issues
    - Provides actionable next steps
    - Interprets visualization patterns
    """
    
    def __init__(
        self,
        top_issues_count: int = 5,
        focus_areas: Optional[list[str]] = None,
        split_security_operational: bool = True,
        enable_operational: bool = True,
        enable_security: bool = True
    ):
        """
        Initialize analysis summary plugin.

        Args:
            top_issues_count: Number of top issues to highlight (1-5)
            focus_areas: Areas to focus on (e.g., ["critical_issues", "performance"])
            split_security_operational: Generate separate security and operational summaries
            enable_operational: Generate operational summary (task completion, stuck agents)
            enable_security: Generate security summary (vulnerabilities, risks)
        """
        self.top_issues_count = min(max(top_issues_count, 1), 5)  # Clamp to 1-5
        self.focus_areas = focus_areas or [
            "critical_issues",
            "performance_bottlenecks",
            "architectural_concerns"
        ]
        self.split_security_operational = split_security_operational
        self.enable_operational = enable_operational
        self.enable_security = enable_security
    
    @property
    def name(self) -> str:
        return "analysis_summary"
    
    @property
    def description(self) -> str:
        return "LLM-based synthesis of all analysis results"
    
    def configure(self, config: Dict[str, Any]):
        """Configure plugin from plugins.yaml."""
        self.top_issues_count = config.get("top_issues_count", self.top_issues_count)
        self.focus_areas = config.get("focus_areas", self.focus_areas)
        self.split_security_operational = config.get("split_security_operational", self.split_security_operational)
        self.enable_operational = config.get("enable_operational", self.enable_operational)
        self.enable_security = config.get("enable_security", self.enable_security)
    
    async def execute(self, state: 'ApplicationState') -> Dict[str, Any]:
        """
        Execute analysis summary generation.

        Generates separate operational and security summaries if split mode is enabled.

        Args:
            state: ApplicationState with all artifacts from session

        Returns:
            Execution summary dict
        """
        # Register artifact kind for this plugin
        state._data_manager.register_artifact_kind("analysis_summary", AnalysisSummaryArtifact)

        self._log("Starting analysis summary generation")

        # Collect all artifacts by kind
        artifacts_by_kind = await self._collect_all_artifacts(state)

        if not artifacts_by_kind:
            return {
                "status": "skipped",
                "message": "No artifacts found to summarize",
                "artifacts_produced": 0,
            }

        # Get session context
        codebase_path = str(state.codebase_path or "Unknown")
        phases_completed = list(state.completed_phases) if hasattr(state, 'completed_phases') else []

        # Format artifacts for LLM
        context = format_artifacts_for_summary(
            artifacts_by_kind,
            codebase_path,
            phases_completed
        )

        artifacts_produced = 0
        summaries_generated = []

        # Generate operational summary (task completion, stuck agents, performance)
        if self.enable_operational and self.split_security_operational:
            self._log("Generating operational summary (task completion & performance)...")
            try:
                operational_summary = await self._generate_summary(
                    context,
                    state,
                    summary_type="operational"
                )
                if operational_summary:
                    operational_artifact = self._build_summary_artifact(
                        operational_summary,
                        artifacts_by_kind,
                        codebase_path,
                        phases_completed,
                        summary_type="operational"
                    )
                    operational_markdown = self._generate_markdown_report(
                        operational_artifact,
                        title="Operational Analysis: Task Completion & Performance"
                    )
                    operational_artifact["markdown_report"] = operational_markdown

                    # Save operational summary
                    await state.artifacts() \
                        .from_plugin(self.name) \
                        .kind("analysis_summary") \
                        .save([operational_artifact])
                    self._save_markdown_file(state, operational_markdown, filename="operational_summary.md")

                    artifacts_produced += 1
                    summaries_generated.append("operational")
                    self._log("Operational summary generated successfully")
            except Exception as e:
                self._log(f"Failed to generate operational summary: {e}", level="error")

        # Generate security summary (vulnerabilities, risks)
        if self.enable_security and self.split_security_operational:
            self._log("Generating security summary (vulnerabilities & risks)...")
            try:
                security_summary = await self._generate_summary(
                    context,
                    state,
                    summary_type="security"
                )
                if security_summary:
                    security_artifact = self._build_summary_artifact(
                        security_summary,
                        artifacts_by_kind,
                        codebase_path,
                        phases_completed,
                        summary_type="security"
                    )
                    security_markdown = self._generate_markdown_report(
                        security_artifact,
                        title="Security Analysis: Vulnerabilities & Risks"
                    )
                    security_artifact["markdown_report"] = security_markdown

                    # Save security summary
                    await state.artifacts() \
                        .from_plugin(self.name) \
                        .kind("analysis_summary") \
                        .save([security_artifact])
                    self._save_markdown_file(state, security_markdown, filename="security_summary.md")

                    artifacts_produced += 1
                    summaries_generated.append("security")
                    self._log("Security summary generated successfully")
            except Exception as e:
                self._log(f"Failed to generate security summary: {e}", level="error")


        if artifacts_produced == 0:
            return {
                "status": "failed",
                "message": "Failed to generate any summaries",
                "artifacts_produced": 0,
            }

        self._log(f"Analysis summary generation complete ({', '.join(summaries_generated)} generated)")

        return {
            "status": "success",
            "artifacts_produced": artifacts_produced,
            "summaries_generated": summaries_generated,
        }
    
    async def _collect_all_artifacts(
        self,
        state: 'ApplicationState'
    ) -> Dict[str, list]:
        """
        Collect all artifacts from session grouped by kind.
        
        Args:
            state: ApplicationState
            
        Returns:
            Dict of {artifact_kind: [artifacts]}
        """
        artifacts_by_kind = defaultdict(list)
        
        # Get all artifact kinds from state
        # Priority order for processing
        artifact_kinds = [
            "outcome",  # NEW: Collect outcome artifacts for prioritization
            "diagnosis",
            "issue",
            "metric",
            "graph_structure",
            "trajectory_data",
            "code_model",
        ]
        
        for kind in artifact_kinds:
            try:
                result = await state.artifacts().kind(kind).get()
                artifacts = result.to_list()
                if artifacts:
                    artifacts_by_kind[kind] = artifacts
                    self._log(f"Collected {len(artifacts)} {kind} artifacts")
            except Exception as e:
                self._log(f"Failed to collect {kind} artifacts: {e}", level="warning")
        
        return dict(artifacts_by_kind)
    
    async def _generate_summary(
        self,
        context: Dict[str, Any],
        state: 'ApplicationState',
        summary_type: str = "combined"
    ) -> Optional[Dict[str, Any]]:
        """
        Generate summary using LLM.

        Args:
            context: Formatted context for prompt
            state: ApplicationState
            summary_type: Type of summary ("operational", "security", or "combined")

        Returns:
            Parsed summary dict or None
        """
        # Get LLM service
        llm = get_llm_service()

        # Select appropriate system prompt
        if summary_type == "operational":
            system_prompt = OPERATIONAL_SUMMARY_SYSTEM_PROMPT
        elif summary_type == "security":
            system_prompt = SECURITY_SUMMARY_SYSTEM_PROMPT
        else:
            # Default to operational if unknown
            system_prompt = OPERATIONAL_SUMMARY_SYSTEM_PROMPT

        # Format user prompt
        user_prompt = ANALYSIS_SUMMARY_USER_TEMPLATE.format(**context)

        # Add summary type guidance to user prompt
        if summary_type == "operational":
            user_prompt += "\n\n**IMPORTANT: Focus ONLY on task completion, stuck agents, execution patterns, and performance. IGNORE security issues.**"
        elif summary_type == "security":
            user_prompt += "\n\n**IMPORTANT: Focus ONLY on security vulnerabilities and risks. IGNORE operational/performance issues.**"

        # Call LLM
        self._log(f"Calling LLM for {summary_type} summary generation...")
        response = await llm.call_llm(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            attributes={"max_tokens": 4096, "temperature": 0.3}
        )

        # Parse response
        summary_data = self._parse_summary_response(response.content)

        if not summary_data:
            self._log("Failed to parse LLM response", level="warning")
            self._log(f"Response: {response.content[:500]}...", level="warning")

        return summary_data
    
    def _parse_summary_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse LLM summary response into structured data.
        
        Args:
            response_text: Raw LLM response text
            
        Returns:
            Parsed summary dict or None if parsing fails
        """
        try:
            # Extract JSON from response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                summary = json.loads(json_text)
                return summary
            else:
                self._log("No JSON found in LLM response", level="warning")
                return None
        
        except json.JSONDecodeError as e:
            self._log(f"Failed to parse LLM response as JSON: {e}", level="warning")
            return None
    
    def _build_summary_artifact(
        self,
        summary_data: Dict[str, Any],
        artifacts_by_kind: Dict[str, list],
        codebase_path: str,
        phases_completed: list[str],
        summary_type: str = "combined"
    ) -> Dict[str, Any]:
        """
        Build analysis summary artifact from LLM response.

        Args:
            summary_data: Parsed LLM response
            artifacts_by_kind: Collected artifacts
            codebase_path: Path to analyzed codebase
            phases_completed: List of completed phases
            summary_type: Type of summary ("operational", "security", or "combined")

        Returns:
            Summary artifact dict
        """
        # Build artifacts inventory
        artifacts_analyzed = {
            kind: len(artifacts)
            for kind, artifacts in artifacts_by_kind.items()
        }
        
        # Extract top issues (limit to configured count)
        raw_top_issues = summary_data.get("top_issues") or []
        
        # NEW: Prioritize issues by outcome (failed/stuck traces get boosted priority)
        top_issues = self._prioritize_by_outcome(
            raw_top_issues,
            artifacts_by_kind.get("outcome", []),
            artifacts_by_kind.get("issue", [])
        )[:self.top_issues_count]
        
        # Enrich top issues with artifact references
        for issue in top_issues:
            issue_id = issue.get("issue_id")
            if issue_id:
                # Find related artifacts
                related_ids, related_kinds = self._find_related_artifacts(
                    issue_id,
                    artifacts_by_kind
                )
                issue["related_artifact_ids"] = related_ids
                issue["related_artifact_kinds"] = related_kinds
        
        # Build artifact
        summary_artifact = {
            "summary_type": summary_type,  # NEW: Mark the type of summary
            "session_summary": summary_data.get("session_summary", "No summary provided"),
            "codebase_path": codebase_path,
            "phases_completed": phases_completed,
            "top_issues": top_issues,
            "key_insights": summary_data.get("key_insights") or [],
            "artifacts_analyzed": artifacts_analyzed,
            "next_steps": summary_data.get("next_steps") or [],
            "graph_summary": summary_data.get("graph_summary"),
            "trajectory_summary": summary_data.get("trajectory_summary"),
        }

        return summary_artifact
    
    def _find_related_artifacts(
        self,
        issue_id: str,
        artifacts_by_kind: Dict[str, list]
    ) -> tuple[list[str], list[str]]:
        """
        Find artifacts related to an issue.
        
        Args:
            issue_id: Issue ID to search for
            artifacts_by_kind: All artifacts
            
        Returns:
            Tuple of (related_artifact_ids, related_artifact_kinds)
        """
        related_ids = []
        related_kinds = []
        
        # Search in diagnosis artifacts
        for diagnosis in artifacts_by_kind.get("diagnosis", []):
            # Check if diagnosis relates to this issue
            relations = diagnosis.get("relations") or []
            for rel in relations:
                if rel.get("target_id") == issue_id:
                    related_ids.append(diagnosis.get("id"))
                    related_kinds.append("diagnosis")
                    break
        
        # Add the issue itself
        for issue in artifacts_by_kind.get("issue", []):
            if issue.get("id") == issue_id:
                related_ids.append(issue_id)
                related_kinds.append("issue")
                break
        
        return related_ids, related_kinds
    
    def _prioritize_by_outcome(
        self,
        issues: list[Dict[str, Any]],
        outcomes: list,
        all_issues: list
    ) -> list[Dict[str, Any]]:
        """
        Reorder issues based on task outcomes.
        
        Issues from failed/stuck/timeout traces get highest priority.
        
        Args:
            issues: Top issues from LLM
            outcomes: Outcome artifacts
            all_issues: All issue artifacts
            
        Returns:
            Reordered issues list
        """
        if not outcomes or not issues:
            return issues
        
        # Build trace_id -> outcome status map
        outcome_by_trace = {}
        for outcome in outcomes:
            trace_id = outcome.get("trace_id") if isinstance(outcome, dict) else getattr(outcome, "trace_id", None)
            status = outcome.get("status") if isinstance(outcome, dict) else getattr(outcome, "status", None)
            if trace_id and status:
                outcome_by_trace[trace_id] = status
        
        # Calculate priority scores for issues
        issue_scores = []
        for issue in issues:
            issue_id = issue.get("issue_id")
            
            # Find related trace via issue artifact relationships
            related_trace_id = None
            for issue_artifact in all_issues:
                if issue_artifact.get("id") == issue_id:
                    relations = issue_artifact.get("relations") or []
                    for rel in relations:
                        if rel.get("target_kind") == "traces":
                            related_trace_id = rel.get("target_id")
                            break
                    break
            
            # Score based on outcome status
            priority_score = 0
            if related_trace_id and related_trace_id in outcome_by_trace:
                outcome_status = outcome_by_trace[related_trace_id]
                
                # Priority boost based on outcome
                if outcome_status == "stuck":
                    priority_score = 100  # Highest priority
                elif outcome_status == "failed":
                    priority_score = 90
                elif outcome_status == "timeout":
                    priority_score = 85
                elif outcome_status == "partial_success":
                    priority_score = 50
                elif outcome_status == "success":
                    priority_score = 10  # Lowest priority (edge case)
            
            # Add base severity score
            severity = issue.get("severity", "").lower()
            severity_scores = {"critical": 40, "high": 30, "medium": 20, "low": 10}
            priority_score += severity_scores.get(severity, 0)
            
            issue_scores.append((priority_score, issue))
        
        # Sort by priority score (descending)
        issue_scores.sort(key=lambda x: x[0], reverse=True)
        
        return [issue for score, issue in issue_scores]

    
    def _generate_markdown_report(
        self,
        summary_artifact: Dict[str, Any],
        title: str = "Analysis Summary Report"
    ) -> str:
        """
        Generate markdown report from summary artifact.

        Args:
            summary_artifact: Summary artifact dict
            title: Report title (different for operational vs security)

        Returns:
            Markdown formatted report
        """
        lines = []

        # Header
        lines.append(f"# {title}")
        lines.append("")
        lines.append(f"**Codebase**: `{summary_artifact['codebase_path']}`")
        lines.append(f"**Phases Completed**: {', '.join(summary_artifact['phases_completed'])}")
        lines.append("")
        
        # Session Summary
        lines.append("## Executive Summary")
        lines.append("")
        lines.append(summary_artifact["session_summary"])
        lines.append("")
        
        # Top Issues
        top_issues = summary_artifact.get("top_issues", [])
        if top_issues:
            lines.append("## Critical Issues")
            lines.append("")
            lines.append(f"The following {len(top_issues)} issue(s) require immediate attention:")
            lines.append("")
            
            for issue in top_issues:
                rank = issue.get("rank", 0)
                severity = issue.get("severity", "unknown").upper()
                name = issue.get("issue_name", "Unknown")
                
                lines.append(f"### {rank}. {name} [{severity}]")
                lines.append("")
                lines.append(f"**Category**: {issue.get('category', 'unknown')}")
                lines.append("")
                lines.append(f"**Impact**: {issue.get('impact_summary', 'N/A')}")
                lines.append("")
                lines.append(f"**Root Cause**: {issue.get('root_cause_summary', 'N/A')}")
                lines.append("")
                lines.append(f"**Why Fix This First**: {issue.get('fix_priority_reason', 'N/A')}")
                lines.append("")
        
        # Key Insights
        insights = summary_artifact.get("key_insights", [])
        if insights:
            lines.append("## Key Insights")
            lines.append("")
            
            for insight in insights:
                insight_type = insight.get("insight_type", "unknown").replace("_", " ").title()
                title = insight.get("title", "Unknown")
                
                lines.append(f"### {insight_type}: {title}")
                lines.append("")
                lines.append(insight.get("description", "No description"))
                lines.append("")
        
        # Visualization Summaries
        if summary_artifact.get("graph_summary"):
            lines.append("## Graph Structure Analysis")
            lines.append("")
            lines.append(summary_artifact["graph_summary"])
            lines.append("")
        
        if summary_artifact.get("trajectory_summary"):
            lines.append("## Execution Trajectory Analysis")
            lines.append("")
            lines.append(summary_artifact["trajectory_summary"])
            lines.append("")
        
        # Next Steps
        next_steps = summary_artifact.get("next_steps", [])
        if next_steps:
            lines.append("## Recommended Next Steps")
            lines.append("")
            for i, step in enumerate(next_steps, 1):
                lines.append(f"{i}. {step}")
            lines.append("")
        
        # Artifacts Summary
        artifacts_analyzed = summary_artifact.get("artifacts_analyzed", {})
        if artifacts_analyzed:
            lines.append("## Artifacts Analyzed")
            lines.append("")
            for kind, count in artifacts_analyzed.items():
                lines.append(f"- **{kind}**: {count}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _save_markdown_file(
        self,
        state: 'ApplicationState',
        markdown_content: str,
        filename: str = "analysis_summary.md"
    ):
        """
        Save markdown report as a separate .md file.

        Args:
            state: ApplicationState with session info
            markdown_content: Markdown formatted report
            filename: Name of the markdown file to save
        """
        try:
            # Get the persistence handler from state
            persistence = state.persistence_handler
            
            if not persistence:
                self._log("No persistence handler available, skipping markdown file save", level="warning")
                return
            
            # Get the plugin directory for this session
            session_id = state.session_id
            plugin_dir = persistence.get_plugin_dir(session_id, "summary", self.name)
            
            # Write markdown file
            md_file = plugin_dir / filename
            md_file.write_text(markdown_content, encoding="utf-8")

            self._log(f"Markdown report saved to: {md_file}")
        
        except Exception as e:
            self._log(f"Failed to save markdown file: {e}", level="warning")

# Made with Bob
