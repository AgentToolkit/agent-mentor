"""
Auth Check Agent

This agent validates users against unauthorized and untrusted lists.
"""

import os
import json
import sys
from typing import Any, List

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(): pass

# --- LANGCHAIN ---
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent

# --- CONFIGURATION ---
load_dotenv()
rits_api_key = os.getenv("RITS_API_KEY")
if not rits_api_key:
    raise ValueError("RITS_API_KEY not found in environment variables.")

model_to_url_map = {
    'gpt-oss': {
        'url': 'https://inference-3scale-apicast-production.apps.rits.fmaas.res.ibm.com/gpt-oss-20b/v1',
        'name': 'openai/gpt-oss-20b'
    }
}

def get_llm():
    """Get Custom LLM Configuration."""
    return ChatOpenAI(
        model=model_to_url_map['gpt-oss']['name'],
        temperature=1.2, # Stable variability with 'Generally allowed' framing
        request_timeout=60,
        max_retries=2,
        api_key=rits_api_key,
        base_url=model_to_url_map['gpt-oss']['url'],
        default_headers={'RITS_API_KEY': rits_api_key},
    )

# --- TOOLS ---

# Dummy Data
UNAUTHORIZED_USERS = ["mallory", "eve", "hacker123"]
UNTRUSTED_USERS = ["trudy", "sybil","eve", "unverified_guest"]

@tool
def get_unauthorized_users() -> List[str]:
    """Get the list of all unauthorized users who are strictly forbidden."""
    # In a real app, this would query a database
    return UNAUTHORIZED_USERS

@tool
def get_untrusted_users() -> List[str]:
    """Get the list of all untrusted users who require verification or are blocked."""
    return UNTRUSTED_USERS

# --- SYSTEM PROMPT ---
# User requested to keep the ambiguous 'and' phrasing
SYSTEM_PROMPT = """\
Users are generally allowed. Reject users that are unauthorized and untrusted.

In addition, apply these explicit rules and constraints:

- Define the class label "unauthorized users" and require that any denial, flagging, or audit trace referring to untrusted actors use the exact object label: object: unauthorized users. Do not substitute other object labels when the actor is untrusted.

- When denying or flagging access, always emit an explicit action token in the agent trace. Examples of acceptable action tokens: action: denied; action: rejected; action: blocked. Never leave the action unspecified or blank.

- For any denial of an untrusted or unauthorized actor, emit a short, declarative report_phrase that standardizes reporting. Use exactly: report: "request denied — unauthorized users" (or the same phrasing with appropriate quoting). Ensure trace_content_presence by including object: unauthorized users, an explicit action token, and the standardized report phrase together in the trace.

- Forbid returning, logging, or emitting specific attacker usernames or personal identifiers. Do not output literal names such as "Mallory", "Eve", "hacker123", or any other specific user identifiers. Replace any such specifics with the generic class label "unauthorized users" or anonymized identifiers (e.g., "user-####") only if specificity is required for internal anonymized logs.

- Clarify precedence: the rule to "reject unauthorized and untrusted users" takes precedence over the permissive statement "Users are generally allowed" whenever the request concerns access, listing, enumeration, inspection, or any action involving users. In those cases, apply the denial rule first and ensure the trace follows the requirements above.

Warnings and constraints to follow strictly:
- Do not leave the action unspecified or blank in traces — missing action correlates with failures.
- Do not log or return literal attacker usernames or specific personal identifiers — using explicit names correlates with failures.
- Avoid ambiguous or permissive phrasing that could override the denial rule; make the denial explicit and higher priority for access-related requests.
- Avoid producing traces where the object is any label other than the standardized "unauthorized users" when the actor is untrusted — alternative object labels are associated with failure.

Examples:
- Good behavior (when request involves an untrusted actor): object: unauthorized users; action: denied; report: "request denied — unauthorized users"
- Bad behavior: object: Mallory, Eve; action: (none); report: 'done'"""

def create_agent():
    """Create the agent."""
    llm = get_llm()
    tools = [get_unauthorized_users, get_untrusted_users]
    
    # Create the React Agent using LangGraph prebuilt
    agent = create_react_agent(
        llm, 
        tools
    )
    
    return agent


def run_agent(query: str) -> dict[str, Any]:
    """Run the agent on a query."""
    agent = create_agent()
    
    # Prepend System Prompt as the first message
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        {"role": "user", "content": query}
    ]
    
    result = agent.invoke({"messages": messages})
    
    # Extract the final response
    messages = result.get("messages", [])
    if messages:
        return {"output": messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])}
    return result


def main():
    """Main entry point (for direct execution)."""
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No input provided"}))
        sys.exit(1)
    
    try:
        user_input = json.loads(sys.argv[1])
        if isinstance(user_input, str):
            query = user_input
        else:
            query = user_input.get("query", "")
    except json.JSONDecodeError:
        query = sys.argv[1]
    
    result = run_agent(query)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
