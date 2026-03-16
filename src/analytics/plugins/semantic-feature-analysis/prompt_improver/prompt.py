"""Prompts and schemas for prompt improver plugin."""

# ── Recommendation Analysis ───────────────────────────────────

RECOMMENDATION_SYSTEM_PROMPT = (
    "You are an expert system prompt engineer analyzing agent execution patterns. "
    "Your goal is to identify what causes failures and recommend prompt improvements."
)

RECOMMENDATION_USER_TEMPLATE = """You have access to:
1. **The current system prompt** being evaluated
2. **Semantic features** extracted from agent traces
3. **Decision tree analysis** showing which features differentiate successful from failed traces
4. **Feature importance** scores

Your task is to recommend system prompt improvements that would guide agents toward success patterns.

**IMPORTANT**: The user has defined:
- **{success_label_name}** (label={success_label}) = the DESIRED behavior (good cluster)
- **{failure_label_name}** (label={failure_label}) = the UNDESIRED behavior (bad cluster)

## CURRENT SYSTEM PROMPT (the prompt being evaluated):

{original_prompt}

## DISCOVERED SEMANTIC FEATURES:

{feature_descriptions_text}

## DECISION TREE RULES:

The following tree was trained to classify traces into {success_label_name} ({success_label}) vs {failure_label_name} ({failure_label}):

{tree_rules}

## FEATURE IMPORTANCE (Top Features):

{feature_importance_text}

## {success_label_name} (label={success_label}) - Feature Values (first 3 examples):
{success_examples_text}

## {failure_label_name} (label={failure_label}) - Feature Values (first 5 examples):
{failure_examples_text}

## ANALYSIS TASK:

Based on the semantic features and decision tree analysis:

1. **Critical Issues**: What specific feature values or patterns appear in failures but not successes?
2. **Success Patterns**: What specific feature values consistently appear in successful traces?
3. **Prompt Additions**: What concrete instructions should be added to prevent failures?
   - Reference specific sections of the current system prompt that need changes.
4. **Prompt Warnings**: What specific mistakes should agents avoid?
   - Identify any existing instructions that may be causing the failures.
5. **Examples**: Provide actionable examples based on the feature differences.

Focus on the features with high importance scores and the decision tree splits.

## OUTPUT FORMAT:

Return ONLY valid JSON with this structure (no markdown, no code blocks):
{{
  "critical_issues": ["issue 1", "issue 2"],
  "success_patterns": ["pattern 1", "pattern 2"],
  "prompt_additions": ["addition 1", "addition 2"],
  "prompt_warnings": ["warning 1", "warning 2"],
  "example_good_behavior": "description of correct behavior",
  "example_bad_behavior": "description of incorrect behavior"
}}"""

RECOMMENDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "critical_issues": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Feature values or patterns that appear in failures but not successes",
        },
        "success_patterns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Feature values consistently appearing in successful traces",
        },
        "prompt_additions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Concrete instructions to add to prevent failures",
        },
        "prompt_warnings": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific mistakes agents should avoid",
        },
        "example_good_behavior": {
            "type": "string",
            "description": "Description of correct/desired behavior",
        },
        "example_bad_behavior": {
            "type": "string",
            "description": "Description of incorrect/undesired behavior",
        },
    },
    "required": ["critical_issues", "success_patterns", "prompt_additions", "prompt_warnings"],
}

# ── Prompt Rewriting ──────────────────────────────────────────

PROMPT_REWRITE_SYSTEM_PROMPT = (
    "You are a system prompt engineer. Produce improved system prompts "
    "by incorporating analysis-based recommendations while preserving all existing content."
)

PROMPT_REWRITE_USER_TEMPLATE = """Rewrite the ORIGINAL PROMPT below by incorporating the recommendations. Return ONLY the improved prompt text — no commentary, no code fences, no section headers like "RECOMMENDATIONS" or "RULES".

Rules:
- Return the COMPLETE improved prompt, not a diff or summary.
- Keep ALL existing content from the original. Do not remove existing rules.
- Integrate recommendations naturally into appropriate sections.
- Add new sections only when recommendations don't fit existing ones.
- Do NOT echo back these instructions, the recommendations list, or any meta-content. Your entire response must be the improved prompt and nothing else.

=== ORIGINAL PROMPT (start) ===
{original_prompt}
=== ORIGINAL PROMPT (end) ===

=== ANALYSIS FINDINGS (incorporate these into the prompt above) ===

Critical issues causing failures:
{issues_text}

Additions to make:
{additions_text}

Warnings / constraints:
{warnings_text}

Example of good behavior: {good_example}
Example of bad behavior: {bad_example}

=== END OF ANALYSIS ===

Now return ONLY the complete improved prompt text:"""
