import logging
import json
from abc import ABC, abstractmethod
from pydantic import ValidationError

from app.schemas.ai_schema import RouterOutput
from app.core.llm_client import get_current_llm_response, USE_MOCK_LLM

logger = logging.getLogger(__name__)

# --- Constants (Copied from graph.py for clarity, could be central) ---
ROUTE_SEARCH = "search"
ROUTE_DETAILS = "details"
ROUTE_COMPARE = "compare"
ROUTE_NO_INFO = "no_info"
VALID_INTENTS = [ROUTE_SEARCH, ROUTE_DETAILS, ROUTE_COMPARE, ROUTE_NO_INFO]

# --- Custom Exception ---
class RoutingError(Exception):
    """Custom exception for errors during the routing task."""
    pass

# --- Abstract Base Class (Interface) ---
class BaseRouterTask(ABC):
    @abstractmethod
    def execute(self, question: str) -> RouterOutput:
        """Processes the question and returns structured routing information."""
        pass

# --- Real LLM Implementation ---
class RouterTask(BaseRouterTask):
    def _build_prompt(self, question: str) -> str:
        # Describe the desired structure and provide examples of the data
        prompt = f"""
Analyze the user question about Indian mutual funds: "{question}"

Determine the user's primary intent. Choose ONE intent from: {VALID_INTENTS}.
- Use '{ROUTE_SEARCH}' for finding funds based on criteria.
- Use '{ROUTE_DETAILS}' for questions about ONE specific fund.
- Use '{ROUTE_COMPARE}' for comparing TWO or MORE funds.
- Use '{ROUTE_NO_INFO}' for general questions or unclear requests.

Extract the necessary information based on the intent:
- If intent is '{ROUTE_DETAILS}' or '{ROUTE_COMPARE}': Extract scheme codes (numeric) or fund name placeholders (e.g., "FUND_NAME_CODE") into a JSON list called "scheme_codes". Prioritize numeric codes if available.
- If intent is '{ROUTE_SEARCH}': Extract the search criteria into a JSON string called "query".
- For other intents, these fields should be null.

Respond ONLY with a single, valid JSON object containing the extracted data. The JSON object must have these keys:
- "intent": (string) The determined intent.
- "scheme_codes": (list of strings or null) Extracted codes/placeholders.
- "query": (string or null) Extracted search query.

Example Output Formats:
Search: {{"intent": "{ROUTE_SEARCH}", "scheme_codes": null, "query": "large cap funds"}}
Details by Code: {{"intent": "{ROUTE_DETAILS}", "scheme_codes": ["120503"], "query": null}}
Details by Name: {{"intent": "{ROUTE_DETAILS}", "scheme_codes": ["AXIS_BLUECHIP_CODE"], "query": null}}
Compare by Codes: {{"intent": "{ROUTE_COMPARE}", "scheme_codes": ["120503", "119660"], "query": null}}
Compare by Names: {{"intent": "{ROUTE_COMPARE}", "scheme_codes": ["SBI_BLUECHIP_CODE", "ICICI_BLUECHIP_CODE"], "query": null}}
No Info: {{"intent": "{ROUTE_NO_INFO}", "scheme_codes": null, "query": null}}

Ensure your entire response is ONLY the JSON object.
JSON Response:
"""
        return prompt

    def _validate_output(self, output: RouterOutput) -> None:
        """Performs logical validation on the parsed RouterOutput."""
        intent = output.intent
        codes = output.scheme_codes
        query = output.query

        if intent not in VALID_INTENTS:
            raise RoutingError(f"LLM returned invalid intent: '{intent}'")

        if intent == ROUTE_DETAILS and (not codes or len(codes) == 0):
            raise RoutingError(f"Intent is '{intent}' but no scheme codes were extracted.")

        if intent == ROUTE_COMPARE and (not codes or len(codes) < 2):
            raise RoutingError(f"Intent is '{intent}' but less than two scheme codes were extracted: {codes}")

        if intent == ROUTE_SEARCH and not query:
            raise RoutingError(f"Intent is '{intent}' but no search query was extracted.")

        if intent != ROUTE_SEARCH and query:
             logger.warning(f"Router extracted query '{query}' but intent is '{intent}'. Ignoring query.")
             output.query = None # Clean up state
        if intent not in [ROUTE_DETAILS, ROUTE_COMPARE] and codes:
             logger.warning(f"Router extracted codes {codes} but intent is '{intent}'. Ignoring codes.")
             output.scheme_codes = None # Clean up state

    def execute(self, question: str) -> RouterOutput:
        logger.info(f"Executing RouterTask for question: '{question}'")
        prompt = self._build_prompt(question)
        llm_response_str = get_current_llm_response(prompt, max_tokens=250)

        if not llm_response_str or llm_response_str.startswith("Error:"):
            raise RoutingError(f"LLM router call failed: {llm_response_str or 'No response'}")

        try:
            cleaned_response = llm_response_str.strip().strip('```json').strip('```').strip()
            parsed_output = RouterOutput.parse_raw(cleaned_response)
            logger.info(f"LLM Router Raw Output Parsed: {parsed_output}")

            # Perform logical validation
            self._validate_output(parsed_output)
            logger.info(f"LLM Router Output Validated: {parsed_output}")
            return parsed_output

        except (ValidationError, json.JSONDecodeError) as e:
            logger.error(f"Failed to parse/validate router LLM JSON: {e}\nResponse: {llm_response_str}")
            raise RoutingError(f"Invalid format from LLM router: {e}") from e
        except RoutingError as e:
             logger.error(f"Routing validation failed: {e}")
             raise e # Re-raise specific routing errors
        except Exception as e:
            logger.error(f"Unexpected error during router task execution: {e}", exc_info=True)
            raise RoutingError(f"Unexpected error in router task: {e}") from e

# --- Mock Implementation ---
class MockRouterTask(BaseRouterTask):
    def execute(self, question: str) -> RouterOutput:
        logger.warning(f"Executing MOCK RouterTask for question: '{question}'")
        q_lower = question.lower()

        if "compare" in q_lower and "120503" in q_lower and "119660" in q_lower:
             return RouterOutput(intent=ROUTE_COMPARE, scheme_codes=["120503", "119660"])
        elif "compare" in q_lower and "sbi" in q_lower and "icici" in q_lower:
             return RouterOutput(intent=ROUTE_COMPARE, scheme_codes=["SBI_BLUECHIP_CODE", "ICICI_BLUECHIP_CODE"])
        elif "compare" in q_lower:
             # Simulate compare intent but maybe not enough codes extracted by LLM
             return RouterOutput(intent=ROUTE_COMPARE, scheme_codes=["MOCK_COMPARE_CODE"])
        elif "details for 120503" in q_lower or "summarize 120503" in q_lower:
            return RouterOutput(intent=ROUTE_DETAILS, scheme_codes=["120503"])
        elif "details" in q_lower or "summarize" in q_lower and "axis" in q_lower:
            return RouterOutput(intent=ROUTE_DETAILS, scheme_codes=["AXIS_BLUECHIP_CODE"])
        elif "details" in q_lower or "summarize" in q_lower:
             # Simulate details intent but maybe no code extracted
              return RouterOutput(intent=ROUTE_DETAILS, scheme_codes=[])
        elif "search" in q_lower or "find" in q_lower:
            query = q_lower.split("search for ")[-1] if "search for " in q_lower else q_lower.split("find ")[-1]
            return RouterOutput(intent=ROUTE_SEARCH, query=query.strip() or "mock search term")
        elif "what is" in q_lower or "explain" in q_lower:
             return RouterOutput(intent=ROUTE_NO_INFO)
        else:
            # Default mock case if no keywords match
            return RouterOutput(intent=ROUTE_NO_INFO)

# --- Factory Function (Optional but convenient) ---
def get_router_task() -> BaseRouterTask:
    if USE_MOCK_LLM:
        logger.info("Using MockRouterTask")
        return MockRouterTask()
    else:
        logger.info("Using RouterTask")
        return RouterTask() 