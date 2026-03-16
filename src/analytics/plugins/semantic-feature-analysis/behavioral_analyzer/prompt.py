"""Prompts and schemas for behavioral analyzer plugin."""

# ── Feature Discovery ─────────────────────────────────────────

FEATURE_DISCOVERY_SYSTEM_PROMPT = (
    "You are a semantic feature engineering expert. "
    "Analyze agent execution traces to discover meaningful features "
    "that differentiate success from failure patterns."
)

FEATURE_DISCOVERY_USER_TEMPLATE = (
    "The following text holds the recording of an action performed by an agent. "
    "First, think about a single sentence a detailed description of what the agent did. "
    "Then apply the result of the feature extraction to that phrase\n"
    "You are given a corpus of short texts (e.g., sentences or short narratives).\n"
    "Your task is to elicit a list of semantic \"features\" that capture the core meaning "
    "structure of these texts.\n\n"
    "A feature here means a semantic class that can be instantiated by different spans "
    "in different sentences, such as:\n\n"
    "Subject / \"Who?\"\nAction / \"What did they do?\"\n"
    "Object / \"What was acted on?\"\nReason / \"Why?\"\nEtc.\n\n"
    "IMPORTANT: Your feature set MUST include the core SVO features "
    "(Subject, Verb/Action, Object) as a baseline.\n"
    "Then add additional features beyond SVO that help differentiate "
    "between the following clusters:\n"
    "{examples_text}\n"
    "\nOutput as JSON containing the of feature definitions.\n"
    "Ensure descriptions emphasize text values and forbid numbers.\n"
    "When a single feature could be split into finer sub-categories, "
    "create separate features for each level of detail.\n"
    "For example, if texts mention conditions or constraints, distinguish "
    "the broad category of the condition from the exact textual expression "
    "that states it."
)

FEATURE_LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "features": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Feature name (e.g., 'subject', 'action')"},
                    "description": {
                        "type": "string",
                        "description": "What this feature captures (text values only, no numbers)",
                    },
                },
                "required": ["name", "description"],
            },
        }
    },
    "required": ["features"],
}

# ── Feature Extraction ────────────────────────────────────────

FEATURE_EXTRACTION_SYSTEM_PROMPT = (
    "You are a semantic feature extraction engine. "
    "Extract feature values from agent execution traces precisely."
)

FEATURE_EXTRACTION_USER_TEMPLATE = (
    "Analyze the trace history below.\n"
    "Extract ONLY the requested semantic lists.\n"
    "RULES: Return lists as comma-separated strings. NO NUMBERS.\n"
    "Respond in JSON format.\n\n"
    "VARIABLES TO EXTRACT:\n{field_desc}\n\n"
    "TRACE HISTORY (Sequential Steps):\n{trace_text}"
)
