import requests
from typing import List, Dict, Any, Optional
import logging
import time  # Import time for potential delays

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MFAPI_BASE_URL = "https://api.mfapi.in" 

# Optional: Add a short delay between requests to respect potential rate limits
REQUEST_DELAY_SECONDS = 0.5

def _make_request(url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
    """Helper function to make GET requests with error handling and delay."""
    try:
        # Optional delay before making the request
        if REQUEST_DELAY_SECONDS > 0:
            time.sleep(REQUEST_DELAY_SECONDS)

        response = requests.get(url, params=params, timeout=15) # Increased timeout
        response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.Timeout:
        logger.error(f"Timeout error requesting URL: {url} with params: {params}")
        return None
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err} - URL: {url}, Status Code: {http_err.response.status_code}")
        return None
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request error occurred: {req_err} - URL: {url}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during request to {url}: {e}")
        return None

def get_fund_details(scheme_code: str) -> Optional[Dict[str, Any]]:
    """
    Fetches detailed information for a specific mutual fund scheme.
    """
    endpoint = f"{MFAPI_BASE_URL}/mf/{scheme_code}"
    logger.info(f"Attempting to fetch details for scheme code: {scheme_code} from {endpoint}")

    data = _make_request(endpoint)

    if data:
        # Basic validation: Check if it's a dictionary as expected
        if isinstance(data, dict) and 'meta' in data and 'data' in data:
            logger.info(f"Successfully fetched details for scheme code: {scheme_code}")
            return data
        else:
            logger.warning(f"Received unexpected data format for scheme {scheme_code}: {type(data)}")
            return None
    else:
        # Error already logged in _make_request
        return None


def search_funds_by_name(query: str) -> Optional[List[Dict[str, Any]]]:
    """
    Searches for mutual funds by name.
    Returns a list of matching funds (often basic info like name and scheme code).
    """
    endpoint = f"{MFAPI_BASE_URL}/mf/search"
    params = {"q": query}
    logger.info(f"Attempting to search funds with query: '{query}' from {endpoint}")

    data = _make_request(endpoint, params=params)

    # Explicitly check for None first (indicates request error)
    if data is None:
        # Error already logged in _make_request
        return None

    # Now check if the received data is a list
    if isinstance(data, list):
        # Handle empty list specifically (valid success case)
        if not data:
             logger.info(f"Search for query '{query}' returned no results.")
             return []
        # Handle non-empty list: check format (using schemeCode as discussed)
        elif all(isinstance(item, dict) and 'schemeCode' in item and 'schemeName' in item for item in data):
            logger.info(f"Successfully searched funds for query: '{query}'. Found {len(data)} results.")
            return data
        else:
            # Handle list with items in unexpected format
            logger.warning(f"Search result for '{query}' contained unexpected item format.")
            # Optional: Filter for valid items only, or return None/[] depending on desired strictness
            valid_items = [item for item in data if isinstance(item, dict) and 'schemeCode' in item and 'schemeName' in item]
            logger.info(f"Returning {len(valid_items)} valid items found for query '{query}'.")
            return valid_items
    else:
        # Handle case where data is not None and not a list (unexpected format)
        logger.warning(f"Unexpected search result format for query '{query}': {type(data)}")
        return None


def compare_funds(scheme_codes: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Fetches details for multiple funds to allow comparison.
    Returns a dictionary mapping scheme codes to their details (or None if fetch failed).
    """
    if not scheme_codes:
        return {}

    comparison_data: Dict[str, Optional[Dict[str, Any]]] = {}
    logger.info(f"Attempting to fetch details for comparison for schemes: {scheme_codes}")

    for code in scheme_codes:
        details = get_fund_details(code) # This already includes logging and delays
        comparison_data[code] = details # Store the full details dict or None if failed
        if details is None:
             logger.warning(f"Failed to fetch details for scheme {code} during comparison.")
        # No extra delay needed here as get_fund_details handles it via _make_request

    successful_fetches = sum(1 for details in comparison_data.values() if details is not None)
    logger.info(f"Finished comparison fetch for {len(scheme_codes)} schemes. Successfully fetched {successful_fetches}.")
    return comparison_data 