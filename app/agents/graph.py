# app/agents/graph.py

import logging
import re 
from typing import List, Dict, Optional, Any

from langgraph.graph import StateGraph, END

from app.schemas.ai_schema import AgentState, RouterOutput
from app.services import mfapi_service
# Import task classes, factories, and custom exceptions
from app.llm_tasks import (
    get_router_task, BaseRouterTask,
    get_summarizer_task, BaseSummarizerTask,
    RoutingError, SummarizationError
)

logger = logging.getLogger(__name__)
# --- Constants ---
# Defined in router_task, but useful here too
ROUTE_SEARCH = "search"
ROUTE_DETAILS = "details"
ROUTE_COMPARE = "compare"
ROUTE_NO_INFO = "no_info"
# ROUTE_ERROR = "error" # Implicitly handled by error_message now

# --- Instantiate Tasks (using factories) ---
# This allows easy switching between real/mock implementations based on llm_client
router_task: BaseRouterTask = get_router_task()
summarizer_task: BaseSummarizerTask = get_summarizer_task()

# --- Helper --- 
def _is_placeholder_code(code: str) -> bool:
    """Check if a string looks like a placeholder code (non-numeric or ends with _CODE)."""
    if not isinstance(code, str):
         return False
    # Simple check: not purely numeric OR ends with _CODE (case-insensitive)
    return not re.fullmatch(r'\d+', code) or code.upper().endswith('_CODE')

# --- Agent Nodes (Refactored) ---
def route_question_node(state: AgentState) -> Dict[str, Any]:
    """Node that uses the RouterTask to determine intent and extract info."""
    question = state['question']
    logger.info(f"Executing route_question_node for: '{question}'")
    try:
        routing_result: RouterOutput = router_task.execute(question)
        logger.info(f"Routing task successful: {routing_result}")

        needs_mapping = False
        raw_codes = routing_result.scheme_codes
        intent = routing_result.intent

        # Determine if mapping is needed
        if intent in [ROUTE_DETAILS, ROUTE_COMPARE] and raw_codes:
            if any(_is_placeholder_code(code) for code in raw_codes):
                needs_mapping = True
                logger.info("Placeholder codes detected, mapping needed.")

        # Update state
        return {
            "parsed_router_output": routing_result,
            "raw_scheme_codes": raw_codes,
            "search_query": routing_result.query, # Query directly usable
            "needs_mapping": needs_mapping,
            "final_scheme_codes": None if needs_mapping else raw_codes, # Set final if no mapping needed
            "error_message": None # Clear previous errors if router succeeds
        }
    except RoutingError as e:
        logger.error(f"Routing task failed: {e}")
        return {"error_message": str(e)}
    except Exception as e:
        logger.exception(f"Unexpected error in route_question_node: {e}") # Log full traceback
        return {"error_message": f"Unexpected routing error: {e}"}

def map_name_to_code_node(state: AgentState) -> Dict[str, Any]:
    """Node to map fund name placeholders to actual scheme codes using search."""
    logger.info("Executing map_name_to_code_node.")
    raw_codes = state.get('raw_scheme_codes')
    if not raw_codes:
        return {"error_message": "Mapper node called without raw scheme codes."}

    final_codes = []
    mapping_errors = []
    placeholders_to_map = [code for code in raw_codes if _is_placeholder_code(code)]
    numeric_codes = [code for code in raw_codes if not _is_placeholder_code(code)]
    final_codes.extend(numeric_codes) # Add already valid codes

    logger.info(f"Attempting to map placeholders: {placeholders_to_map}")

    for placeholder in placeholders_to_map:
        # Simple name extraction (assumes placeholder like NAME_CODE)
        search_name = placeholder.replace("_CODE", "").replace("_", " ")
        logger.info(f"Searching for scheme code for: '{search_name}'")
        search_results = mfapi_service.search_funds_by_name(search_name)

        found_code = None
        if search_results:
            # Simple matching logic: Try to find an exact name match (case-insensitive)
            # More sophisticated matching might be needed in reality
            match = next((r for r in search_results
                          if isinstance(r, dict) and r.get('schemeName')
                          and r['schemeName'].strip().lower() == search_name.lower()), None)

            if match and isinstance(match.get('schemeCode'), int):
                found_code = str(match['schemeCode']) # Convert to string to match state type
                logger.info(f"Mapped '{search_name}' to code: {found_code}")
            elif len(search_results) == 1 and isinstance(search_results[0].get('schemeCode'), int):
                 # If only one result, assume it's the one even if name isn't exact match
                 found_code = str(search_results[0]['schemeCode'])
                 logger.warning(f"Mapped '{search_name}' to code {found_code} based on single search result (name mismatch?).")
            else:
                # Ambiguous (multiple results) or no exact match
                error_detail = f"multiple results ({len(search_results)})" if search_results else "no results"
                mapping_errors.append(f"Could not map '{search_name}' ({error_detail})")
                logger.warning(f"Mapping failed for '{search_name}': {error_detail}.")
        else:
            # Search service failed or returned empty
            mapping_errors.append(f"Search failed for '{search_name}'")
            logger.warning(f"Mapping failed for '{search_name}': Search returned None or empty.")

        if found_code and found_code not in final_codes:
            final_codes.append(found_code)

    if not final_codes: # If even numeric codes were absent and all mapping failed
        return {"final_scheme_codes": [], "error_message": f"Failed to map or find any valid scheme codes. Errors: {'; '.join(mapping_errors)}"}
    elif mapping_errors:
        # Partial success: return found codes but also signal error
         logger.warning(f"Mapping finished with errors: {mapping_errors}")
         return {
             "final_scheme_codes": final_codes,
             "error_message": f"Could not map all funds. Errors: {'; '.join(mapping_errors)}"
         }
    else:
        logger.info(f"Mapping successful. Final codes: {final_codes}")
        return {"final_scheme_codes": final_codes, "error_message": None} # Clear error if successful

def call_search_tool_node(state: AgentState) -> Dict[str, Any]:
    """Node that calls the search tool."""
    logger.info("Executing call_search_tool_node.")
    query = state.get('search_query')
    if not query:
        return {"error_message": "Search node called without a query."}

    try:
        results = mfapi_service.search_funds_by_name(query)
        if results is None:
            return {"error_message": f"Search service failed for query: '{query}'."}
        logger.info(f"Search tool returned {len(results)} results.")
        return {"search_results": results, "error_message": None}
    except Exception as e:
        logger.exception(f"Unexpected error in call_search_tool_node: {e}")
        return {"error_message": f"Unexpected search error: {e}"}

def call_details_tool_node(state: AgentState) -> Dict[str, Any]:
    """Node that calls the details tool."""
    logger.info("Executing call_details_tool_node.")
    codes = state.get('final_scheme_codes') # Use mapped codes
    if not codes or not isinstance(codes, list) or len(codes) != 1:
        return {"error_message": f"Details node called with invalid final codes: {codes}."}

    code = codes[0]
    try:
        details = mfapi_service.get_fund_details(code)
        if details is None:
            return {"error_message": f"Failed to retrieve details for scheme code: {code}."}
        logger.info(f"Details tool returned data for scheme {code}")
        return {"fund_details": details, "error_message": None}
    except Exception as e:
        logger.exception(f"Unexpected error in call_details_tool_node: {e}")
        return {"error_message": f"Unexpected details error: {e}"}

def call_compare_tool_node(state: AgentState) -> Dict[str, Any]:
    """Node that calls the compare tool."""
    logger.info("Executing call_compare_tool_node.")
    codes = state.get('final_scheme_codes') # Use mapped codes
    if not codes or not isinstance(codes, list) or len(codes) < 2:
        return {"error_message": f"Compare node requires at least two final codes (received: {codes})."}

    try:
        compare_data = mfapi_service.compare_funds(codes)
        if compare_data is None: # Defensive check
             return {"error_message": f"Comparison service returned None for codes: {codes}."}

        successful_fetches = sum(1 for details in compare_data.values() if details is not None)
        logger.info(f"Compare tool returned data for {successful_fetches}/{len(codes)} codes.")

        # Check if *all* failed, which indicates a problem
        if successful_fetches == 0 and len(codes) > 0:
            return {"comparison_data": compare_data, "error_message": f"Failed to retrieve details for all comparison codes: {codes}."}

        # Partial success is okay, summarizer can mention it
        return {"comparison_data": compare_data, "error_message": None}
    except Exception as e:
        logger.exception(f"Unexpected error in call_compare_tool_node: {e}")
        return {"error_message": f"Unexpected comparison error: {e}"}

def summarize_results_node(state: AgentState) -> Dict[str, Any]:
    """Node that uses the SummarizerTask to generate the final response."""
    logger.info("Executing summarize_results_node.")
    try:
        summary = summarizer_task.execute(state)
        logger.info("Summarizer task successful.")
        return {"summary": summary, "error_message": None} # Clear error on successful summary
    except SummarizationError as e:
        logger.error(f"Summarizer task failed: {e}")
        # Keep existing error message if present, otherwise use this new one
        error_msg = state.get('error_message') or str(e)
        return {"summary": f"Error during summarization: {e}", "error_message": error_msg}
    except Exception as e:
        logger.exception(f"Unexpected error in summarize_results_node: {e}")
        error_msg = state.get('error_message') or f"Unexpected summary error: {e}"
        return {"summary": f"Unexpected error generating summary: {e}", "error_message": error_msg}

def handle_no_info_node(state: AgentState) -> Dict[str, Any]:
    """Node for handling ROUTE_NO_INFO."""
    logger.info("Executing handle_no_info_node.")
    # Simple response, could use LLM for more nuanced clarification
    summary = f"I understand you asked: '{state.get('question', '')}'. Could you please provide more specific details, like a fund name or scheme code, or ask a question I can answer with the available tools (search, details, compare)?"
    return {"summary": summary, "error_message": None}

def handle_error_node(state: AgentState) -> Dict[str, Any]:
    """Node for handling errors."""
    error_msg = state.get('error_message', 'Unknown error')
    logger.error(f"Executing handle_error_node: {error_msg}")
    summary = f"Sorry, I encountered an error processing your request: {error_msg}. Please try rephrasing your question."
    # Error is now handled, clear it from state so graph ends cleanly
    return {"summary": summary, "error_message": None}

# --- Conditional Edges Logic (Refactored) ---

def decide_post_router(state: AgentState) -> str:
    """Decides where to go after the router node."""
    if state.get('error_message'):
        return "error_handler"

    # Get the parsed output object
    router_output: Optional[RouterOutput] = state.get('parsed_router_output')
    if not router_output: # Should not happen if router sets output or error
         logger.error("State missing parsed_router_output after router node succeeded.")
         return "error_handler"

    if state.get('needs_mapping'):
        return "mapper"
    else:
        # If no mapping needed, go directly based on intent
        # Access intent via attribute
        intent = router_output.intent
        if intent == ROUTE_SEARCH:
            return "search_tool"
        elif intent == ROUTE_DETAILS:
            return "details_tool"
        elif intent == ROUTE_COMPARE:
            return "compare_tool"
        elif intent == ROUTE_NO_INFO:
            return "no_info_handler"
        else:
            # This case should ideally be caught by RouterTask validation
            logger.error(f"Invalid intent ('{intent}') in parsed_router_output.")
            return "error_handler" # Let error handler report the issue

def decide_post_mapper(state: AgentState) -> str:
    """Decides where to go after the mapper node."""
    if state.get('error_message'):
        # Error occurred during mapping
        return "error_handler"
    else:
        # Mapping succeeded, proceed based on original intent
        router_output: Optional[RouterOutput] = state.get('parsed_router_output')
        if not router_output: # Should not happen
             logger.error("State missing parsed_router_output after mapper node succeeded.")
             return "error_handler"

        # Access intent via attribute
        intent = router_output.intent
        if intent == ROUTE_DETAILS:
            return "details_tool"
        elif intent == ROUTE_COMPARE:
            return "compare_tool"
        else:
            # Should not happen if router logic is correct
             logger.error(f"Invalid original intent ('{intent}') after successful mapping.")
             return "error_handler"

def decide_post_tool(state: AgentState) -> str:
    """Decides whether to summarize or handle error after a tool node."""
    if state.get('error_message'):
        logger.warning("Error message found after tool execution. Routing to error handler.")
        return "error_handler"
    else:
        # If no error message set by the tool, proceed to summarizer
        return "summarizer"

# --- Build the Graph (Refactored) ---

workflow = StateGraph(AgentState)

# Add nodes (using new names for clarity)
workflow.add_node("router", route_question_node)
workflow.add_node("mapper", map_name_to_code_node)
workflow.add_node("search_tool", call_search_tool_node)
workflow.add_node("details_tool", call_details_tool_node)
workflow.add_node("compare_tool", call_compare_tool_node)
workflow.add_node("summarizer", summarize_results_node)
workflow.add_node("no_info_handler", handle_no_info_node)
workflow.add_node("error_handler", handle_error_node)

# Set entry point
workflow.set_entry_point("router")

# Add conditional edges from router
workflow.add_conditional_edges(
    "router",
    decide_post_router,
    {
        "mapper": "mapper", # Go to mapper if needed
        "search_tool": "search_tool", # Direct routes if no mapping needed
        "details_tool": "details_tool",
        "compare_tool": "compare_tool",
        "no_info_handler": "no_info_handler",
        "error_handler": "error_handler"
    }
)

# Add conditional edges from mapper
workflow.add_conditional_edges(
    "mapper",
    decide_post_mapper,
    {
        "details_tool": "details_tool", # Routes after successful mapping
        "compare_tool": "compare_tool",
        "error_handler": "error_handler" # Route to error if mapping failed
    }
)

# Add conditional edges after tool execution (search, details, compare)
workflow.add_conditional_edges("search_tool", decide_post_tool, {"summarizer": "summarizer", "error_handler": "error_handler"})
workflow.add_conditional_edges("details_tool", decide_post_tool, {"summarizer": "summarizer", "error_handler": "error_handler"})
workflow.add_conditional_edges("compare_tool", decide_post_tool, {"summarizer": "summarizer", "error_handler": "error_handler"})

# Nodes that lead to the end
workflow.add_edge("summarizer", END)
workflow.add_edge("no_info_handler", END)
workflow.add_edge("error_handler", END)

# Compile the graph
agent_graph = workflow.compile()

logger.info("Agent graph compiled successfully (Refactored).")

# --- Function to run the agent (Mostly unchanged, ensure initial state keys match) ---
def run_agent(question: str) -> Dict[str, Any]:
    """Invokes the compiled agent graph with the user's question."""
    # Use the full AgentState structure for initial input for clarity
    initial_state = AgentState(
        question=question,
        parsed_router_output=None,
        raw_scheme_codes=None,
        final_scheme_codes=None,
        search_query=None,
        needs_mapping=False,
        search_results=None,
        fund_details=None,
        comparison_data=None,
        summary=None,
        error_message=None
    )
    try:
        # LangGraph merges this input; keys here will overwrite initial Nones
        # Add recursion limit for safety
        final_state = agent_graph.invoke(initial_state, {"recursion_limit": 10})
        # Return relevant parts of the final state
        # Note: error_message should be None if handle_error_node was reached successfully
        return {
            "summary": final_state.get('summary'),
            "error": final_state.get('error_message') # Should typically be None here
        }
    except Exception as e:
        logger.exception(f"Error invoking agent graph: {e}") # Log full traceback
        return {"summary": None, "error": f"An internal error occurred during agent execution: {e}"} 