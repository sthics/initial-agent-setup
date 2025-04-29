# app/schemas/ai_schema.py

from typing import TypedDict, List, Dict, Optional, Any
from pydantic import BaseModel, Field

# --- Pydantic Models for Structured LLM Outputs ---

class RouterOutput(BaseModel):
    """Defines the expected structured output from the routing LLM call."""
    intent: str = Field(..., description="The determined intent (e.g., 'search', 'details', 'compare', 'no_info')")
    scheme_codes: Optional[List[str]] = Field(None, description="List of extracted scheme codes or placeholders (e.g., ['123456', 'SBI_BLUECHIP_CODE'])")
    query: Optional[str] = Field(None, description="The extracted search query term, if intent is 'search'")

    class Config:
        schema_extra = {
            "example_search": {"intent": "search", "scheme_codes": None, "query": "large cap funds"},
            "example_details": {"intent": "details", "scheme_codes": ["120503"], "query": None},
            "example_compare": {"intent": "compare", "scheme_codes": ["SBI_BLUECHIP_CODE", "120503"], "query": None},
            "example_no_info": {"intent": "no_info", "scheme_codes": None, "query": None}
        }

# --- Agent State Definition ---

class AgentState(TypedDict):
    """Defines the state passed between nodes in the LangGraph agent."""

    # Input
    question: str

    # Information extracted/determined by the router
    # route: str # Replaced by parsed_router_output or individual fields
    parsed_router_output: Optional[RouterOutput] # Store the validated output from the router task
    # Extracted scheme codes or placeholders *before* mapping
    raw_scheme_codes: Optional[List[str]]
    # Final, validated scheme codes *after* mapping (if needed)
    final_scheme_codes: Optional[List[str]]
    # Search query determined by router
    search_query: Optional[str]
    # Flag indicating if name->code mapping is required
    needs_mapping: bool

    # Data retrieved from tools
    search_results: Optional[List[Dict[str, Any]]] # Result from search_funds_by_name
    fund_details: Optional[Dict[str, Any]]       # Result from get_fund_details (for single fund)
    comparison_data: Optional[Dict[str, Optional[Dict[str, Any]]]] # Result from compare_funds

    # Final Output
    summary: Optional[str] # The final generated summary or answer
    error_message: Optional[str] # If an error occurred preventing a summary

# --- API Request/Response Models for AI Endpoint ---

class AIQueryRequest(BaseModel):
    """Request model for the /ai/query endpoint."""
    question: str

class AIQueryResponse(BaseModel):
    """Response model for the /ai/query endpoint."""
    summary: Optional[str] = None
    error: Optional[str] = None
    # Optional: Could include intermediate data if useful for debugging/frontend
    # search_results: Optional[List[Dict[str, Any]]] = None
    # comparison_data: Optional[Dict[str, Any]] = None 