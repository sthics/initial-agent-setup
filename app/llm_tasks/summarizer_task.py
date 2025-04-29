# app/llm_tasks/summarizer_task.py

import logging
import json
from abc import ABC, abstractmethod
from typing import Dict, Any

from app.schemas.ai_schema import AgentState # To understand state structure
from app.core.llm_client import get_current_llm_response, USE_MOCK_LLM

logger = logging.getLogger(__name__)

# --- Custom Exception ---
class SummarizationError(Exception):
    """Custom exception for errors during the summarization task."""
    pass

# --- Abstract Base Class (Interface) ---
class BaseSummarizerTask(ABC):
    @abstractmethod
    def execute(self, state: AgentState) -> str:
        """Processes the agent state and returns a final summary string."""
        pass

# --- Real LLM Implementation ---
class SummarizerTask(BaseSummarizerTask):

    def _prepare_data_context(self, state: AgentState) -> str:
        """Formats the data from the state for the LLM prompt."""
        data_context = ""
        search_results = state.get('search_results')
        fund_details = state.get('fund_details')
        comparison_data = state.get('comparison_data')

        if search_results is not None:
            max_results_to_show = 5
            # Ensure items are serializable, handle potential non-dict items defensively
            serializable_results = [item if isinstance(item, dict) else {"error": "Invalid item format"} for item in search_results]
            results_str = json.dumps(serializable_results[:max_results_to_show], indent=2)
            if len(search_results) > max_results_to_show:
                results_str += f"\n... ({len(search_results) - max_results_to_show} more results truncated)"
            data_context += f"Search Results Found:\n{results_str}\n\n"

        if fund_details is not None and isinstance(fund_details, dict):
            meta = fund_details.get('meta', {})
            data_list = fund_details.get('data', [])
            latest_nav = data_list[0].get('nav') if data_list and isinstance(data_list[0], dict) else None
            details_summary = {
                "name": meta.get('scheme_name'),
                "category": meta.get('scheme_category'),
                "fund_house": meta.get('fund_house'),
                "latest_nav": latest_nav
            }
            data_context += f"Details for Specific Fund:\n{json.dumps(details_summary, indent=2)}\n\n"

        if comparison_data is not None and isinstance(comparison_data, dict):
            comp_summary = {}
            for code, details in comparison_data.items():
                if details and isinstance(details, dict):
                    meta = details.get('meta', {})
                    data_list = details.get('data', [])
                    latest_nav = data_list[0].get('nav') if data_list and isinstance(data_list[0], dict) else None
                    comp_summary[code] = {
                        "name": meta.get('scheme_name'),
                        "category": meta.get('scheme_category'),
                        "latest_nav": latest_nav
                    }
                else:
                    comp_summary[code] = "Failed to fetch details"
            data_context += f"Comparison Data:\n{json.dumps(comp_summary, indent=2)}\n\n"

        return data_context.strip()

    def _build_prompt(self, question: str, data_context: str) -> str:
        prompt = f"""
You are Arth, a helpful financial assistant specialized in Indian mutual funds.

The user asked: "{question}"

Based ONLY on the following retrieved data, provide a concise and informative summary answering the user's question:

{data_context if data_context else "No specific data was retrieved."}

- If search results are present, list the names and scheme codes.
- If specific fund details are present, summarize the key information like name, category, fund house, and latest NAV.
- If comparison data is present, briefly compare the funds based on the available information (e.g., latest NAV, category). Mention if any fund details failed to load.
- If no specific data was retrieved, state that you couldn't find the requested information.
- Do not invent information not present in the data context.
- Keep the response focused on answering the original question.
- Format the response clearly for the user.

Summary:
"""
        return prompt

    def execute(self, state: AgentState) -> str:
        logger.info("Executing SummarizerTask...")
        question = state.get('question', "No question found in state")
        data_context = self._prepare_data_context(state)

        if not data_context:
            logger.warning("Summarizer task called with no data context.")
            # Return a specific message instead of calling LLM if no data
            return "I couldn't find any specific data from the tools to summarize based on your request."

        prompt = self._build_prompt(question, data_context)
        summary = get_current_llm_response(prompt, max_tokens=450)

        if not summary or summary.startswith("Error:"):
            raise SummarizationError(f"LLM summarizer call failed: {summary or 'No response'}")

        logger.info(f"SummarizerTask generated summary: {summary[:100]}...")
        return summary.strip()

# --- Mock Implementation ---
class MockSummarizerTask(BaseSummarizerTask):
    def execute(self, state: AgentState) -> str:
        logger.warning("Executing MOCK SummarizerTask...")
        question = state.get('question', 'Unknown question')
        context = []
        if state.get('search_results') is not None:
            context.append(f"mock search results for '{state.get('search_query', 'unknown query')}'")
        if state.get('fund_details') is not None:
            context.append(f"mock details for schemes {state.get('final_scheme_codes')}")
        if state.get('comparison_data') is not None:
            context.append(f"mock comparison for schemes {state.get('final_scheme_codes')}")

        if not context:
             return f"Mock Summary: I looked into '{question}' but found no specific data."
        else:
             return f"Mock Summary for '{question}': Based on {', '.join(context)}."

# --- Factory Function ---
def get_summarizer_task() -> BaseSummarizerTask:
    if USE_MOCK_LLM:
        logger.info("Using MockSummarizerTask")
        return MockSummarizerTask()
    else:
        logger.info("Using SummarizerTask")
        return SummarizerTask() 