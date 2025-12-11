import json
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import Field

from .elements import Element


class DataAnnotation(Element):
    """
    Handles GenAI additional characteristics describing input and output data fields
    """
    class Type(str, Enum):
        """
        Enum representing different types of data annotations.
        """

        # 🔹 STRUCTURAL CLASSIFICATIONS
        RAW_TEXT = "raw_text"  # Unstructured natural language
        STRUCTURED_DATA = "structured_data"  # JSON, XML, Tables
        CODE_SNIPPET = "code_snippet"  # Code blocks in different languages
        MULTIMODAL_DATA = "multimodal_data"  # Mixed formats like images, audio
        
        # 🔹 MEMORY & PERSISTENCE
        SHORT_TERM_MEMORY = "short_term_memory"  # Data remembered for one session
        LONG_TERM_MEMORY = "long_term_memory"  # Persistent stored knowledge
        STATIC_DATA = "static_data"  # Fixed responses or hardcoded facts
        DYNAMIC_DATA = "dynamic_data"  # Real-time generated content
        RAG = "rag"  # RAG content
        
        # 🔹 SEMANTIC & FUNCTIONAL ANNOTATIONS
        HINT = "hint"  # Provides guidance or clarification
        REFERENCE = "reference"  # Links to a specific source or section
        FACTUAL_RESPONSE = "factual_response"  # Verified, objective information
        ANALYTICAL_INSIGHT = "analytical_insight"  # Derived conclusions or insights
        CREATIVE_GENERATION = "creative_generation"  # Fiction, poetry, marketing text
        CODE_GENERATION = "code_generation"  # AI-generated programming code
        DECISION_SUPPORT = "decision_support"  # Recommendations, rankings, evaluations
        
        # 🔹 DATA SECURITY & PRIVACY
        PII = "pii"  # Personally Identifiable Information (e.g., Name, Email)
        CONFIDENTIAL = "confidential"  # Internal or restricted information
        REGULATED = "regulated"  # Compliance-related data (e.g., HIPAA, GDPR)
        PROPRIETARY = "proprietary"  # Company-specific intellectual property
        SENSITIVE_CONTENT = "sensitive_content"  # Potentially offensive or restricted
        
        # 🔹 TRACEABILITY & LLM METADATA
        GENERATED_BY_LLM = "generated_by_llm"  # AI-generated content
        MIRRORED_FROM_INPUT = "mirrored_from_input"  # Directly copied from input
        PARAPHRASED = "paraphrased"  # Reformulated without changing meaning
        SUMMARIZATION = "summarization"  # Condensed version of the original text
        HALLUCINATED_CONTENT = "hallucinated_content"  # Potentially false information
        ACTION = "action"  # action
        OBSERVATION = "observation"  # observation
        THOUGHT = "thought"  # thought
        ARTIFACT = "artifact"

        # 🔹 ERROR DETECTION & DEBUGGING
        SPURIOUS_INFORMATION = "spurious_information"  # Unnecessary or misleading details
        BIAS_FLAGGED = "bias_flagged"  # Potentially biased language
        LOW_CONFIDENCE_RESPONSE = "low_confidence_response"  # Below threshold accuracy
        INCONSISTENT_RESPONSE = "inconsistent_response"  # Contradicts prior knowledge
        AMBIGUOUS_QUERY = "ambiguous_query"  # Unclear input requiring clarification

        # 🔹 PROMPTS and UTTERANCES
        PROMPT = "prompt"  # prompt
        SYSTEM_PROMPT = "system_prompt"  # System prompt
        USER_UTTERANCE = "user_utterance"  # User utterance
        AGENT_UTTERANCE = "agent_utterance" # Agent utterance
                        
        def __str__(self):
            return self.value

    annotation_type: Type = Field(description='The type of annotation for the element')
    path_to_string: Optional[str] = Field(None, description='Navigation path that identifies the location of the annotated text within a structured document')
    segment_start: Optional[int] = Field(None, description='Start index of the segment within text') 
    segment_end: Optional[int] = Field(None, description='End index of the segment within text') 
    annotation_title: Optional[str] = Field(None, description="Title of the annotation")
    annotation_content: Optional[str] = Field(None, description="Content of the annotation")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DataAnnotation':
        """Create a builder from a dictionary"""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'DataAnnotation':
        """Create a builder from a JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
