"""Prompts for trace analyzer plugin."""

SUMMARIZE_SYSTEM_PROMPT = "You are a log analysis assistant. Summarize trace entries concisely."

SUMMARIZE_USER_TEMPLATE = (
    "Summarize this log entry into one concise English sentence describing the action.\n"
    "Focus on the VERB (action) and the OBJECT (target).\n"
    "Preserve any qualifiers or conditions mentioned.\n"
    "LOG:\n{text}"
)

# ── Cluster Summary (for interactive labeling) ──────────────

CLUSTER_SUMMARY_SYSTEM_PROMPT = (
    "You are an agent behavior analyst. Summarize a cluster of agent execution "
    "traces into a short, distinctive description that helps a human understand "
    "what this behavioral pattern looks like."
)

CLUSTER_SUMMARY_USER_TEMPLATE = (
    "Below are sample trace outputs from a cluster of agent executions "
    "that were grouped together by behavioral similarity.\n\n"
    "Summarize the common pattern in 2-3 sentences. Focus on:\n"
    "- What the agent typically does in these traces\n"
    "- The outcome or result pattern\n"
    "- Any notable behaviors or characteristics\n\n"
    "SAMPLE TRACES (up to {n_samples}):\n{samples_text}"
)
