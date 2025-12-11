# SUFFIXES
TOOL_SUFF = '.tool'
TASK_SUFF = '.task'
CHAT_SUFF = '.chat'
WORKFLOW_SUFF = '.workflow'

# SPAN RELATED
SPAN_ATTRIBUTES = 'attributes'
SPAN_INPUTS = 'inputs'
SPAN_OUTPUTS = 'outputs'
HTTP_SPANS = ['POST', 'GET']
LANGTRACE_SERVICE = 'langtrace.service.name'
SERVICE_NAME = 'service.name'

# TRACELOOP RELATED
TRACELOOP_INPUT = 'traceloop.entity.input'
TRACELOOP_OUTPUT = 'traceloop.entity.output'
TRACELOOP_NAME = 'traceloop.entity.name'
TRACELOOP_WORKFLOW = 'traceloop.workflow.name'
TRACELOOP_LANGGRAPH_NODE = 'traceloop.association.properties.langgraph_node'

FRAMEWORK_SPAN_IDENTIFIERS = [TRACELOOP_WORKFLOW, LANGTRACE_SERVICE, SERVICE_NAME]

# LLM RELATED
LLM_CALL_SPAN_NAMES = ['ChatOpenAI.chat', 'openai.chat', 'chat.completions.create', 'ChatWatsonx.chat', 'WatsonxLLM.completion', 'watsonx.generate']
LLM_CALL_EXCLUDE_SPANS = ['AzureChatOpenAI.chat']
LLM_CALL_STARTSWITH_ATTR = ['llm.request.functions.']
LLM_PROMPT_PRE = 'gen_ai.prompt'
LLM_COMPLETE_PRE = 'gen_ai.completion'
LLM_ATTR_FIELDS = [
    'gen_ai.prompt.0.role', 'gen_ai.prompt.0.content',
    'gen_ai.prompt.1.role', 'gen_ai.prompt.1.content',
    'gen_ai.completion.0.role', 'gen_ai.completion.0.content',
    'gen_ai.completion.0.finish_reason',
    'gen_ai.completion.0.tool_calls.0.name', 'gen_ai.completion.0.tool_calls.0.arguments'
]
LLM_METADATA_FIELDS = ['gen_ai.request.model', 'gen_ai.request.temperature', 'gen_ai.response.model']
LLM_INPUT_TOKENS =  'num_input_tokens'
LLM_OUTPUT_TOKENS = 'num_output_tokens'
LLM_TOTAL_TOKENS = 'num_total_tokens'
TOKEN_ATTR_MAP = {
    LLM_INPUT_TOKENS: ['gen_ai.usage.prompt_tokens', 'gen_ai.usage.input_tokens'],
    LLM_OUTPUT_TOKENS: ['gen_ai.usage.completion_tokens', 'gen_ai.usage.output_tokens'],
   LLM_TOTAL_TOKENS: ['llm.usage.total_tokens', 'gen_ai.usage.total_tokens']
}
GEN_AI_PROMPT = 'gen_ai.prompt'
GEN_AI_COMPLETION = 'gen_ai.completion'
GEN_AI_EVENT_PROMPT = 'gen_ai.content.prompt'
GEN_AI_EVENT_COMPLETE = 'gen_ai.content.completion'
TASK_CHAT_COMPLETIONS_CREATE = 'chat.completions.create'
TASK_OPENAI_CHAT_COMPLETIONS_CREATE = 'openai.chat.completions.create'

# FRAMEWORK TAGS
CREWAI = 'CrewAI'
LANGGRAPH = 'LangGraph'
LANGCHAIN_AGENT = 'AgentExecutor'
RUNNABLE_SEQUENCE = 'RunnableSequence'
CREWAI_KICKOFF = 'Crew Kickoff'
CREWAI_TASK_TAG = 'CrewAI Task'
CREWAI_AGENT_TAG = 'CrewAI Agent'
LANGGRAPH_WORKFLOW = 'LangGraph Workflow'
LANGGRAPH_NODE = 'LangGraph Node'
LANGCHAIN_WORKFLOW_TAG = 'Langchain Workflow'
LANGCHAIN_AGENT_TAG = 'Langchain Agent'

FRAMEWORK_TAGS = {
    'CrewAI': [CREWAI_KICKOFF, CREWAI_TASK_TAG, CREWAI_AGENT_TAG],
    'LangGraph': [LANGGRAPH_WORKFLOW, LANGGRAPH_NODE],
    'Langchain': [LANGCHAIN_AGENT_TAG],
}

MAIN_WORKFLOW_SPAN_NAMES = [LANGGRAPH_WORKFLOW, CREWAI_KICKOFF, LANGCHAIN_WORKFLOW_TAG]

# LANGGRAPH SPECIFIC
LANGGRAPH_WORKFLOW_SPAN_NAMES = ['LangGraph.task', 'LangGraph.workflow']
LANGGRAPH_WORKFLOW_CREATION_SPAN_NAMES = ['LangGraph.task', 'LangGraph.workflow']
LANGGRAPH_START = '__start__'
LANGGRAPH_STRUCTURE = 'graph_structure'
NODE_SEPARATOR = ":"

# LANGCHAIN SPECIFIC
LANGCHAIN_AGENT_TASK = LANGCHAIN_AGENT + TASK_SUFF

# CREWAI SPECIFIC
CREWAI_VERSION = 'crewai_version'
CREW_CREATED = 'Crew.created'
CREW_KICKOFF = 'Crew.kickoff'
CREWAI_CREW_CREATION_SPAN_NAMES = [CREW_CREATED, CREW_KICKOFF]
TASK_CREATED = 'Task Created'
TASK_EXECUTION = 'Task Execution'
CREWAI_TASK_CREATION = [TASK_CREATED, TASK_EXECUTION]
CREW_TOOL_USAGE = 'Tool Usage'
CREW_AGENT_EXECUTE_TASK = 'Agent.execute_task'
TASK_EXECUTE = 'Task.execute'
CREW_TOOL_USAGE_ERROR = 'Tool Usage Error'
CREW_TAG = 'Crew Kickoff'
CREW_MANAGER = ['Crew Manager', 'Project Manager']
CREWAI_PROPER_NODE_NAMES = ['Task.execute', 'Agent.execute_task', 'Task Execution']

TASK_KEY = 'task_key'
TASK_ID = 'task_id'

CREWAI_TASK_STARTSWITH_ATTR = 'crewai.task'
CREW_AGENT_OUTPUT = 'crewai.agent.result'
CREW_AGENT = 'crewai.agent'
CREW_AGENT_ID = 'crewai.agent.id'
CREW_AGENT_ROLE = 'crewai.agent.role'
CREW_TASK_EXEC_INPUT = 'crewai.task.description'
CREW_TASK_EXEC_OUTPUT = "crewai.task.result"

#vector DB related
#milvus
MILVUS_INSERT_SPAN = 'Milvus Insert'
MILVUS_SEARCH_SPAN = ['Milvus Search', 'milvus.search']
DB_STARTSWITH_ATTR = 'db'

# General
INSTRUMENATATION_SDK_NAME = 'instrumentation.sdk.name'

# LANGFUSE 
LANGFUSE_SDK_NAME = 'langfuse-sdk'
IS_LANGFUSE_OBSERVATION = 'langfuse.observation'

# span-processing context related
LAST_PARENTS = 'last_parents'
SPAN_ID_TO_TASK = 'tasks_by_span_id'
PROCESSED = 'processed'
TASKS = 'tasks'
ROOT_TASKS = 'root_tasks'
AFTER_TRAVERSAL = 'after_traversal'

FRAMEWORK = 'framework'

# TASK RELATED
ROOT_NAME = '_ROOT'
ISSUE_SPAN_IDS = 'issue_span_ids'
ISSUE_PRE = 'Issue-'
ID = 'id'

ANNOT_SPAN_IDS = 'annotation_span_ids'
ANNOT_PRE = 'DataAnnotation-'

#runnables related
RUNNABLES = 'runnables'
ACTIONS = 'actions'
CODE_ID = 'code_id'
INPUT_SCHEMA = 'input_schema'
OUTPUT_SCHEMA = 'output_schema'
RUNNABLE_SPAN_ATTR = [CODE_ID, INPUT_SCHEMA, OUTPUT_SCHEMA]
UNKNOWN = 'unknown'

# === OTEL Action Attribute Names ===
OTEL_ACTION_ID = 'gen_ai.action.id'
OTEL_ACTION_CODE_ID = 'gen_ai.action.code.id'
OTEL_ACTION_CODE_LANGUAGE = 'gen_ai.action.code.language'
OTEL_ACTION_CODE_INPUT_SCHEMA = 'gen_ai.action.code.input_schema'
OTEL_ACTION_CODE_OUTPUT_SCHEMA = 'gen_ai.action.code.output_schema'
OTEL_ACTION_NAME = 'gen_ai.action.name'
OTEL_ACTION_DESCRIPTION = 'gen_ai.action.description'
OTEL_ACTION_IS_GENERATED = 'gen_ai.action.is_generated'

# === OTEL Task Attribute Names ===
OTEL_TASK_ID = 'gen_ai.task.id'

KNOWN_SPAN_NAMES = {
    "Agent.execute_task": {
        "code_id": "crewai/agent/agent.py:142:Agent.execute_task",
        "input_schema": "{\"task\": {\"annotation\": \"Task\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"context\": {\"annotation\": \"Optional[str]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"tools\": {\"annotation\": \"Optional[List[Any]]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}}",
        "output_schema": "TaskOutput"
    },

    "AgentExecutor.workflow": {
        "code_id": "langchain/agents/agent.py:1039:AgentExecutor._call",
        "input_schema": "{\"inputs\": {\"annotation\": \"Dict[str, Any]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"run_manager\": {\"annotation\": \"Optional[CallbackManagerForChainRun]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}}",
        "output_schema": "Dict[str, Any]"
    },

    "AzureChatOpenAI.chat": {
        "code_id": "langchain_openai/chat_models/azure.py:189:AzureChatOpenAI._generate",
        "input_schema": "{\"messages\": {\"annotation\": \"List[BaseMessage]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"stop\": {\"annotation\": \"Optional[List[str]]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"run_manager\": {\"annotation\": \"Optional[CallbackManagerForLLMRun]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"**kwargs\": {\"annotation\": \"Any\", \"default\": null, \"kind\": \"VAR_KEYWORD\"}}",
        "output_schema": "ChatResult"
    },

    "ChatPromptTemplate.task": {
        "code_id": "langchain_core/prompts/chat.py:341:ChatPromptTemplate.format_prompt",
        "input_schema": "{\"**kwargs\": {\"annotation\": \"Any\", \"default\": null, \"kind\": \"VAR_KEYWORD\"}}",
        "output_schema": "PromptValue"
    },

    "Crew Created": {
        "code_id": "crewai/crew/crew.py:89:Crew.__init__",
        "input_schema": "{\"agents\": {\"annotation\": \"List[Agent]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"tasks\": {\"annotation\": \"List[Task]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"process\": {\"annotation\": \"Process\", \"default\": \"Process.sequential\", \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"verbose\": {\"annotation\": \"bool\", \"default\": false, \"kind\": \"POSITIONAL_OR_KEYWORD\"}}",
        "output_schema": "None"
    },

    "Crew.created": {
        "code_id": "crewai/crew/crew.py:89:Crew.__init__",
        "input_schema": "{\"agents\": {\"annotation\": \"List[Agent]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"tasks\": {\"annotation\": \"List[Task]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"process\": {\"annotation\": \"Process\", \"default\": \"Process.sequential\", \"kind\": \"POSITIONAL_OR_KEYWORD\"}}",
        "output_schema": "None"
    },

    "Crew.kickoff": {
        "code_id": "crewai/crew/crew.py:456:Crew.kickoff",
        "input_schema": "{\"inputs\": {\"annotation\": \"Optional[Dict[str, Any]]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}}",
        "output_schema": "CrewOutput"
    },

    "JsonOutputKeyToolsParser.task": {
        "code_id": "langchain_core/output_parsers/openai_tools.py:177:JsonOutputKeyToolsParser.parse_result",
        "input_schema": "{\"result\": {\"annotation\": \"List[Generation]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"partial\": {\"annotation\": \"bool\", \"default\": false, \"kind\": \"POSITIONAL_OR_KEYWORD\"}}",
        "output_schema": "Any"
    },

    "LangGraph.task": {
        "code_id": "langgraph/pregel/__init__.py:1624:Pregel.invoke",
        "input_schema": "{\"input\": {\"annotation\": \"Union[dict, Any]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"config\": {\"annotation\": \"Optional[RunnableConfig]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"**kwargs\": {\"annotation\": \"Any\", \"default\": null, \"kind\": \"VAR_KEYWORD\"}}",
        "output_schema": "Union[dict, Any]"
    },

    "LangGraph.workflow": {
        "code_id": "langgraph/pregel/__init__.py:1703:Pregel._invoke",
        "input_schema": "{\"input\": {\"annotation\": \"Union[dict, Any]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"config\": {\"annotation\": \"RunnableConfig\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}}",
        "output_schema": "Union[dict, Any]"
    },

    "RunnableAssign<agent_scratchpad>.task": {
        "code_id": "langchain_core/runnables/utils.py:78:RunnableAssign.invoke",
        "input_schema": "{\"input\": {\"annotation\": \"Dict[str, Any]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"config\": {\"annotation\": \"Optional[RunnableConfig]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}}",
        "output_schema": "Dict[str, Any]"
    },

    "RunnableLambda.task": {
        "code_id": "langchain_core/runnables/base.py:4496:RunnableLambda.invoke",
        "input_schema": "{\"input\": {\"annotation\": \"Input\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"config\": {\"annotation\": \"Optional[RunnableConfig]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}}",
        "output_schema": "Output"
    },

    "RunnableParallel<agent_scratchpad>.task": {
        "code_id": "langchain_core/runnables/base.py:3187:RunnableParallel.invoke",
        "input_schema": "{\"input\": {\"annotation\": \"Input\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"config\": {\"annotation\": \"Optional[RunnableConfig]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}}",
        "output_schema": "Dict[str, Any]"
    },

    "RunnableSequence.task": {
        "code_id": "langchain_core/runnables/base.py:2789:RunnableSequence.invoke",
        "input_schema": "{\"input\": {\"annotation\": \"Input\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"config\": {\"annotation\": \"Optional[RunnableConfig]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}}",
        "output_schema": "Output"
    },

    "RunnableSequence.workflow": {
        "code_id": "langchain_core/runnables/base.py:2850:RunnableSequence._invoke",
        "input_schema": "{\"input\": {\"annotation\": \"Input\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"config\": {\"annotation\": \"RunnableConfig\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}}",
        "output_schema": "Output"
    },

    "Task Created": {
        "code_id": "crewai/task/task.py:67:Task.__init__",
        "input_schema": "{\"description\": {\"annotation\": \"str\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"expected_output\": {\"annotation\": \"str\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"agent\": {\"annotation\": \"Optional[Agent]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"tools\": {\"annotation\": \"Optional[List[Any]]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}}",
        "output_schema": "None"
    },

    "Task.execute": {
        "code_id": "crewai/task/task.py:181:Task.execute_sync",
        "input_schema": "{\"agent\": {\"annotation\": \"Agent\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"context\": {\"annotation\": \"Optional[str]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"tools\": {\"annotation\": \"Optional[List[Any]]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}}",
        "output_schema": "TaskOutput"
    },

    "Tool Usage": {
        "code_id": "langchain_core/tools/base.py:394:BaseTool._run",
        "input_schema": "{\"tool_input\": {\"annotation\": \"Union[str, Dict[str, Any]]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"verbose\": {\"annotation\": \"Optional[bool]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"start_color\": {\"annotation\": \"Optional[str]\", \"default\": \"green\", \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"color\": {\"annotation\": \"Optional[str]\", \"default\": \"yellow\", \"kind\": \"POSITIONAL_OR_KEYWORD\"}}",
        "output_schema": "Any"
    },

    "ToolsAgentOutputParser.task": {
        "code_id": "langchain/agents/openai_tools/base.py:119:OpenAIToolsAgentOutputParser.parse_result",
        "input_schema": "{\"result\": {\"annotation\": \"List[Generation]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"partial\": {\"annotation\": \"bool\", \"default\": false, \"kind\": \"POSITIONAL_OR_KEYWORD\"}}",
        "output_schema": "Union[AgentAction, AgentFinish, List[Union[AgentAction, AgentFinish]]]"
    },

    "chat.completions.create": {
        "code_id": "openai/resources/chat/completions.py:641:Completions.create",
        "input_schema": "{\"messages\": {\"annotation\": \"Iterable[ChatCompletionMessageParam]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"model\": {\"annotation\": \"Union[str, ChatModel]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"frequency_penalty\": {\"annotation\": \"Optional[float]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"logit_bias\": {\"annotation\": \"Optional[Dict[str, int]]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"logprobs\": {\"annotation\": \"Optional[bool]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"max_tokens\": {\"annotation\": \"Optional[int]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"n\": {\"annotation\": \"Optional[int]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"presence_penalty\": {\"annotation\": \"Optional[float]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"response_format\": {\"annotation\": \"Optional[ResponseFormat]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"seed\": {\"annotation\": \"Optional[int]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"stop\": {\"annotation\": \"Union[Optional[str], List[str]]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"stream\": {\"annotation\": \"Optional[Literal[False]]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"temperature\": {\"annotation\": \"Optional[float]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"tool_choice\": {\"annotation\": \"Optional[ChatCompletionToolChoiceOptionParam]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"tools\": {\"annotation\": \"Optional[Iterable[ChatCompletionToolParam]]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"top_logprobs\": {\"annotation\": \"Optional[int]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"top_p\": {\"annotation\": \"Optional[float]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"user\": {\"annotation\": \"Optional[str]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}}",
        "output_schema": "ChatCompletion"
    },

    "openai.chat": {
        "code_id": "langchain_openai/chat_models/base.py:389:ChatOpenAI._generate",
        "input_schema": "{\"messages\": {\"annotation\": \"List[BaseMessage]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"stop\": {\"annotation\": \"Optional[List[str]]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"run_manager\": {\"annotation\": \"Optional[CallbackManagerForLLMRun]\", \"default\": null, \"kind\": \"POSITIONAL_OR_KEYWORD\"}, \"**kwargs\": {\"annotation\": \"Any\", \"default\": null, \"kind\": \"VAR_KEYWORD\"}}",
        "output_schema": "ChatResult"
    }
}