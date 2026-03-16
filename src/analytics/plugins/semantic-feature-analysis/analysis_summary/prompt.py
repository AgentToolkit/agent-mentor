"""
Prompts for Analysis Summary Plugin.

LLM-based synthesis of all analysis artifacts into executive summary.
Supports two analysis modes: OPERATIONAL (task completion, stuck agents) and SECURITY.
"""

# ============================================================================
# OPERATIONAL ANALYSIS PROMPT (Task Completion, Stuck Agents, Performance)
# ============================================================================

OPERATIONAL_SUMMARY_SYSTEM_PROMPT = """You are an expert software analyst specializing in agentic systems and LLM applications.

Your task is to analyze TASK COMPLETION and OPERATIONAL ISSUES. Focus on why agents failed to accomplish their goals.

**CRITICAL PRIORITY ORDER:**
1. **Task Outcomes FIRST**: Did the agent complete its task? If not, why?
2. **Stuck/Failed Traces**: Analyze traces marked as stuck, failed, or timeout
3. **Execution Patterns**: Repetitive actions, infinite loops, backtracking
4. **Performance Issues**: Slow operations, excessive retries, inefficient patterns
5. **Logic Errors**: Bugs that prevent task completion (not security issues)

**IGNORE SECURITY ISSUES** - They are analyzed separately.

Focus on:
- Which traces succeeded vs failed/stuck?
- What execution patterns indicate stuck states?
- What code issues prevent task completion?
- What performance bottlenecks slow down execution?

Do NOT:
- List security vulnerabilities (prompt injection, logging, etc.)
- Suggest general code improvements unrelated to failures
- Repeat information verbatim
- Be vague or generic

Output Format: JSON with the following structure:
{
  "session_summary": "Brief overview focused on task completion rates and operational issues (2-3 sentences)",
  "top_issues": [
    {
      "rank": 1,
      "issue_id": "issue-xxx",
      "issue_name": "Issue title",
      "severity": "critical|high|medium|low",
      "category": "category/subcategory",
      "impact_summary": "Why this prevents task completion (1-2 sentences)",
      "root_cause_summary": "Root cause explanation (1-2 sentences)",
      "fix_priority_reason": "Why fix this first to improve task success rate (1 sentence)"
    }
  ],
  "key_insights": [
    {
      "insight_type": "task_completion|execution_pattern|performance|reliability",
      "title": "Insight title",
      "description": "Detailed explanation",
      "actionable": true|false
    }
  ],
  "next_steps": [
    "Concrete action 1",
    "Concrete action 2"
  ],
  "graph_summary": "Interpretation of graph patterns (if graph_structure artifacts exist)",
  "trajectory_summary": "Interpretation of execution patterns (if trajectory_data artifacts exist)"
}
"""

# ============================================================================
# SECURITY ANALYSIS PROMPT
# ============================================================================

SECURITY_SUMMARY_SYSTEM_PROMPT = """You are an expert security analyst specializing in LLM applications and agentic systems.

Your task is to identify SECURITY VULNERABILITIES AND RISKS.

Focus on:
1. **Injection Risks**: Prompt injection, code injection, command injection
2. **Data Exposure**: Sensitive data in logs, outputs, or error messages
3. **Authentication/Authorization**: Access control issues
4. **Input Validation**: Missing or inadequate input sanitization
5. **Dependency Risks**: Vulnerable libraries or insecure configurations

**IGNORE OPERATIONAL ISSUES** - They are analyzed separately. Focus only on security.

Do NOT:
- Include performance issues or stuck agents
- Discuss code quality unrelated to security
- List general bugs or logic errors
- Repeat information verbatim

Output Format: JSON with the following structure:
{
  "session_summary": "Brief overview of security posture (2-3 sentences)",
  "top_issues": [
    {
      "rank": 1,
      "issue_id": "issue-xxx",
      "issue_name": "Issue title",
      "severity": "critical|high|medium|low",
      "category": "security/subcategory",
      "impact_summary": "Security impact (1-2 sentences)",
      "root_cause_summary": "Root cause explanation (1-2 sentences)",
      "fix_priority_reason": "Why fix this first from security perspective (1 sentence)"
    }
  ],
  "key_insights": [
    {
      "insight_type": "security",
      "title": "Insight title",
      "description": "Detailed explanation",
      "actionable": true|false
    }
  ],
  "next_steps": [
    "Concrete security remediation action 1",
    "Concrete security remediation action 2"
  ]
}
"""


ANALYSIS_SUMMARY_USER_TEMPLATE = """# Analysis Session Summary Request

## Session Context
- **Codebase**: {codebase_path}
- **Phases Completed**: {phases_completed}
- **Total Artifacts**: {total_artifacts}

## Artifacts Available

{artifacts_inventory}

## Detailed Artifact Data

{artifact_details}

## Task

Synthesize the above analysis results into an executive summary following the JSON format specified in the system prompt.

Focus on:
1. Top 1-5 critical issues causing failures or degradation
2. Root causes and impact
3. Prioritization by impact
4. Actionable next steps

If graph_structure or trajectory_data artifacts exist, provide interpretations of their patterns in the respective summary fields.
"""


def format_artifacts_for_summary(
    artifacts_by_kind: dict,
    codebase_path: str,
    phases_completed: list[str]
) -> dict:
    """
    Format artifacts for LLM summary generation.
    
    Args:
        artifacts_by_kind: Dict of {artifact_kind: [artifacts]}
        codebase_path: Path to analyzed codebase
        phases_completed: List of completed phase names
        
    Returns:
        Dict with formatted context for prompt template
    """
    # Build artifacts inventory
    inventory_lines = []
    total_artifacts = 0
    for kind, artifacts in artifacts_by_kind.items():
        count = len(artifacts)
        total_artifacts += count
        inventory_lines.append(f"- **{kind}**: {count} artifact(s)")
    
    artifacts_inventory = "\n".join(inventory_lines) if inventory_lines else "No artifacts found"
    
    # Build detailed artifact data (prioritize important kinds)
    # CRITICAL: outcome comes FIRST to show task completion status
    priority_order = [
        "outcome",  # Task completion status (success/failure/stuck)
        "diagnosis",
        "issue",
        "metric",
        "graph_structure",
        "trajectory_data",
        "code_model",
    ]
    
    detail_sections = []
    
    for kind in priority_order:
        if kind not in artifacts_by_kind:
            continue
        
        artifacts = artifacts_by_kind[kind]
        if not artifacts:
            continue
        
        # Format based on artifact kind
        if kind == "outcome":
            detail_sections.append(_format_outcome_artifacts(artifacts))
        elif kind == "diagnosis":
            detail_sections.append(_format_diagnosis_artifacts(artifacts))
        elif kind == "issue":
            detail_sections.append(_format_issue_artifacts(artifacts))
        elif kind == "metric":
            detail_sections.append(_format_metric_artifacts(artifacts))
        elif kind == "graph_structure":
            detail_sections.append(_format_graph_artifacts(artifacts))
        elif kind == "trajectory_data":
            detail_sections.append(_format_trajectory_artifacts(artifacts))
        elif kind == "code_model":
            detail_sections.append(_format_code_model_artifacts(artifacts))
    
    artifact_details = "\n\n".join(detail_sections) if detail_sections else "No detailed data available"
    
    return {
        "codebase_path": codebase_path,
        "phases_completed": ", ".join(phases_completed),
        "total_artifacts": total_artifacts,
        "artifacts_inventory": artifacts_inventory,
        "artifact_details": artifact_details,
    }


def _format_outcome_artifacts(artifacts: list) -> str:
    """Format outcome artifacts for LLM - CRITICAL for task completion visibility."""
    lines = ["### 🎯 Outcome Artifacts (Task Completion Status)"]
    lines.append("")
    lines.append("**THIS IS THE MOST IMPORTANT DATA - Focus on failed/stuck traces!**")
    lines.append("")

    # Group by status
    by_status = {}
    for artifact in artifacts:
        status = artifact.get('status', 'unknown')
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(artifact)

    # Show status summary
    total = len(artifacts)
    lines.append("**Summary:**")
    for status in ["stuck", "failed", "timeout", "partial_success", "unknown", "success"]:
        if status in by_status:
            count = len(by_status[status])
            emoji = {"stuck": "🔴", "failed": "❌", "timeout": "⏱️", "partial_success": "⚠️", "unknown": "❓", "success": "✅"}.get(status, "")
            lines.append(f"- {emoji} **{status.upper()}**: {count}/{total} traces ({count*100//total}%)")
    lines.append("")

    # Show STUCK traces first (highest priority)
    if "stuck" in by_status:
        lines.append("---")
        lines.append("## 🔴 STUCK TRACES - HIGHEST PRIORITY")
        lines.append("")
        for i, outcome in enumerate(by_status["stuck"], 1):
            trace_id = outcome.get('trace_id', 'Unknown')
            confidence = outcome.get('confidence', 'unknown')
            message = outcome.get('message', '')
            evidence = outcome.get('evidence', {})

            lines.append(f"**{i}. Trace {trace_id[-16:]}** (Confidence: {confidence})")
            lines.append(f"- Detection Method: {outcome.get('detection_method', 'unknown')}")
            lines.append(f"- Framework: {evidence.get('framework', 'unknown')}")

            # Parse and show the stuck message details
            if message:
                # Truncate long messages but show key parts
                if len(message) > 500:
                    lines.append(f"- Final Response: {message[:500]}... (truncated)")
                else:
                    lines.append(f"- Final Response: {message}")

            lines.append("")

    # Show FAILED traces
    if "failed" in by_status:
        lines.append("---")
        lines.append("## ❌ FAILED TRACES")
        lines.append("")
        for i, outcome in enumerate(by_status["failed"], 1):
            trace_id = outcome.get('trace_id', 'Unknown')
            message = outcome.get('message', 'No error message')
            lines.append(f"**{i}. Trace {trace_id[-16:]}**")
            lines.append(f"- Message: {message[:200]}{'...' if len(message) > 200 else ''}")
            lines.append("")

    # Show TIMEOUT traces
    if "timeout" in by_status:
        lines.append("---")
        lines.append("## ⏱️ TIMEOUT TRACES")
        lines.append("")
        for i, outcome in enumerate(by_status["timeout"], 1):
            trace_id = outcome.get('trace_id', 'Unknown')
            duration = outcome.get('duration_ms', 'Unknown')
            lines.append(f"**{i}. Trace {trace_id[-16:]}** - Duration: {duration}ms")
            lines.append("")

    # Briefly mention unknown/success (lower priority)
    if "unknown" in by_status:
        lines.append(f"_({len(by_status['unknown'])} traces with unknown outcome - may need investigation)_")
        lines.append("")

    if "success" in by_status:
        lines.append(f"_({len(by_status['success'])} traces completed successfully)_")
        lines.append("")

    return "\n".join(lines)


def _format_diagnosis_artifacts(artifacts: list) -> str:
    """Format diagnosis artifacts for LLM."""
    lines = ["### Diagnosis Artifacts (Root Cause Analysis)"]
    lines.append("")
    
    for i, artifact in enumerate(artifacts[:10], 1):  # Limit to 10
        lines.append(f"**{i}. {artifact.get('name', 'Unknown')}**")
        lines.append(f"- Category: {artifact.get('category', 'unknown')}/{artifact.get('subcategory', 'unknown')}")
        lines.append(f"- Confidence: {artifact.get('confidence', 0.0):.2f}")
        lines.append(f"- Root Cause: {artifact.get('root_cause', 'N/A')}")
        lines.append(f"- Fix Strategy: {artifact.get('fix_strategy', 'N/A')}")
        lines.append("")
    
    if len(artifacts) > 10:
        lines.append(f"_(Showing 10 of {len(artifacts)} diagnoses)_")
    
    return "\n".join(lines)


def _format_issue_artifacts(artifacts: list) -> str:
    """Format issue artifacts for LLM."""
    lines = ["### Issue Artifacts (Detected Problems)"]
    lines.append("")
    
    # Group by severity
    by_severity = {}
    for artifact in artifacts:
        severity = artifact.get('severity', 'unknown')
        if severity not in by_severity:
            by_severity[severity] = []
        by_severity[severity].append(artifact)
    
    for severity in ["critical", "high", "medium", "low"]:
        if severity not in by_severity:
            continue
        
        issues = by_severity[severity]
        lines.append(f"**{severity.upper()} ({len(issues)} issues)**")
        
        for issue in issues[:5]:  # Limit to 5 per severity
            lines.append(f"- {issue.get('name', 'Unknown')}")
            lines.append(f"  - Category: {issue.get('category', 'unknown')}")
            if issue.get('description'):
                desc = issue['description'][:100] + "..." if len(issue['description']) > 100 else issue['description']
                lines.append(f"  - Description: {desc}")
        
        if len(issues) > 5:
            lines.append(f"  _(and {len(issues) - 5} more)_")
        lines.append("")
    
    return "\n".join(lines)


def _format_metric_artifacts(artifacts: list) -> str:
    """Format metric artifacts for LLM."""
    lines = ["### Metric Artifacts (Measurements)"]
    lines.append("")
    
    for artifact in artifacts[:10]:  # Limit to 10
        lines.append(f"**{artifact.get('name', 'Unknown')}**")
        lines.append(f"- Type: {artifact.get('metric_type', 'unknown')}")
        lines.append(f"- Category: {artifact.get('category', 'unknown')}")
        lines.append(f"- Value: {artifact.get('value', 'N/A')}")
        if artifact.get('description'):
            lines.append(f"- Description: {artifact['description']}")
        lines.append("")
    
    return "\n".join(lines)


def _format_graph_artifacts(artifacts: list) -> str:
    """Format graph structure artifacts for LLM."""
    lines = ["### Graph Structure Artifacts"]
    lines.append("")
    
    for artifact in artifacts:
        lines.append(f"**Graph: {artifact.get('graph_name', 'Unknown')}**")
        
        topology = artifact.get('topology', {})
        lines.append(f"- Nodes: {topology.get('total_nodes', 0)}")
        lines.append(f"- Edges: {topology.get('total_edges', 0)}")
        lines.append(f"- Conditional Nodes: {topology.get('conditional_nodes', 0)}")
        lines.append(f"- Has Cycles: {topology.get('has_cycles', False)}")
        
        patterns = artifact.get('patterns', [])
        if patterns:
            lines.append(f"- Patterns Detected:")
            for pattern in patterns:
                severity_marker = "⚠️" if pattern.get('severity') == 'warning' else "ℹ️"
                lines.append(f"  {severity_marker} {pattern.get('description', 'Unknown pattern')}")
        
        lines.append("")
    
    return "\n".join(lines)


def _format_trajectory_artifacts(artifacts: list) -> str:
    """Format trajectory data artifacts for LLM."""
    lines = ["### Trajectory Data Artifacts (Execution Flow)"]
    lines.append("")
    
    for artifact in artifacts:
        trace_id = artifact.get('trace_id', 'Unknown')
        lines.append(f"**Trace: {trace_id}**")
        
        metrics = artifact.get('metrics', {})
        lines.append(f"- Total Steps: {metrics.get('total_steps', 0)}")
        lines.append(f"- Duration: {metrics.get('total_duration_ms', 0):.1f}ms")
        lines.append(f"- LLM Calls: {metrics.get('llm_calls', 0)}")
        lines.append(f"- Tool Calls: {metrics.get('tool_calls', 0)}")
        lines.append(f"- Errors: {metrics.get('error_count', 0)}")
        lines.append(f"- Slow Steps: {metrics.get('slow_steps_count', 0)}")
        
        patterns = artifact.get('patterns', [])
        if patterns:
            lines.append(f"- Patterns Detected:")
            for pattern in patterns:
                severity_marker = "⚠️" if pattern.get('severity') == 'warning' else "ℹ️"
                lines.append(f"  {severity_marker} {pattern.get('description', 'Unknown pattern')}")
        
        tool_usage = artifact.get('tool_usage', [])
        if tool_usage:
            lines.append(f"- Top Tools:")
            for tool in tool_usage[:3]:
                lines.append(f"  - {tool.get('tool_name', 'Unknown')}: {tool.get('call_count', 0)} calls")
        
        lines.append("")
    
    return "\n".join(lines)


def _format_code_model_artifacts(artifacts: list) -> str:
    """Format code model artifacts for LLM."""
    lines = ["### Code Model Artifacts (Code Structure)"]
    lines.append("")
    
    for artifact in artifacts:
        lines.append(f"**Code Model**")
        lines.append(f"- Files: {len(artifact.get('files', {}))}")
        lines.append(f"- Functions: {len(artifact.get('function_index', {}))}")
        lines.append(f"- Tools: {len(artifact.get('tools', []))}")
        lines.append(f"- LLM Calls: {len(artifact.get('llm_calls', []))}")
        lines.append(f"- Graphs: {len(artifact.get('graphs', []))}")
        lines.append("")
    
    return "\n".join(lines)

# Made with Bob
