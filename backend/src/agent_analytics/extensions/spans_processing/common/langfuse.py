from enum import Enum

class LangfuseObservationType(str, Enum):
    """
    """
    EVENT = "EVENT"
    SPAN = "SPAN"
    GENERATION = "GENERATION"
    AGENT = "AGENT"    
    TOOL = "TOOL"
    CHAIN = "CHAIN"
    RETRIEVER = "RETRIEVER"
    EVALUATOR = "EVALUATOR"
    EMBEDDING = "EMBEDDING"
    GUARDRAIL = "GUARDRAIL"