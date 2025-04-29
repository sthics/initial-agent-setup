import pytest
from unittest.mock import patch, MagicMock
import requests
from typing import List, Dict, Any, Optional

# Assuming your service file is located at app/services/mfapi_service.py
from app.services.mfapi_service import (
    get_fund_details,
    search_funds_by_name,
    compare_funds,
    _make_request # Import helper if testing it directly or need its structure
)

# --- Mock Data ---

MOCK_SCHEME_CODE_SUCCESS = "123456"
MOCK_SCHEME_CODE_FAIL = "999999"
MOCK_QUERY_SUCCESS = "bluechip"
MOCK_QUERY_NO_RESULTS = "nonexistentfund"
MOCK_QUERY_FAIL = "errorquery"

MOCK_FUND_DETAILS_RESPONSE = {
    "meta": {
        "fund_house": "Test Mutual Fund",
        "scheme_type": "Open Ended Schemes",
        "scheme_category": "Equity Scheme - Large Cap Fund",
        "scheme_code": int(MOCK_SCHEME_CODE_SUCCESS),
        "scheme_name": "Test Bluechip Fund - Growth",
        "isin_growth": "INF123456789",
        "isin_div_reinvestment": None
    },
    "data": [
        {"date": "01-01-2024", "nav": "100.50"},
        {"date": "02-01-2024", "nav": "101.20"}
    ],
    "status": "SUCCESS"
}

MOCK_SEARCH_RESPONSE_SUCCESS = [
    {"schemeCode": 123456, "schemeName": "Test Bluechip Fund - Growth"},
    {"schemeCode": 789012, "schemeName": "Another Bluechip Fund"}
]

MOCK_SEARCH_RESPONSE_EMPTY = []

# --- Test Cases ---

# We patch 'app.services.mfapi_service._make_request' as that's where the actual request happens
@patch('app.services.mfapi_service._make_request')
def test_get_fund_details_success(mock_make_request: MagicMock):
    """Test successful retrieval of fund details."""
    # Configure the mock to return a successful response
    mock_make_request.return_value = MOCK_FUND_DETAILS_RESPONSE

    details = get_fund_details(MOCK_SCHEME_CODE_SUCCESS)

    # Assertions
    assert details is not None
    assert details["meta"]["scheme_code"] == int(MOCK_SCHEME_CODE_SUCCESS)
    assert details["status"] == "SUCCESS"
    assert len(details["data"]) == 2
    mock_make_request.assert_called_once_with(f"https://api.mfapi.in/mf/{MOCK_SCHEME_CODE_SUCCESS}") # Verify URL

@patch('app.services.mfapi_service._make_request')
def test_get_fund_details_api_error(mock_make_request: MagicMock):
    """Test handling of API error (e.g., 404 Not Found) during fund details fetch."""
    # Configure the mock to simulate _make_request returning None (as it handles errors)
    mock_make_request.return_value = None

    details = get_fund_details(MOCK_SCHEME_CODE_FAIL)

    # Assertions
    assert details is None
    mock_make_request.assert_called_once_with(f"https://api.mfapi.in/mf/{MOCK_SCHEME_CODE_FAIL}")

@patch('app.services.mfapi_service._make_request')
def test_get_fund_details_unexpected_format(mock_make_request: MagicMock):
    """Test handling of unexpected data format from the API."""
    # Return data that doesn't match the expected structure (e.g., missing 'meta')
    mock_make_request.return_value = {"data": [], "status": "SUCCESS"}

    details = get_fund_details(MOCK_SCHEME_CODE_SUCCESS)

    # Assertions
    assert details is None # Service should return None if format is wrong
    mock_make_request.assert_called_once_with(f"https://api.mfapi.in/mf/{MOCK_SCHEME_CODE_SUCCESS}")


@patch('app.services.mfapi_service._make_request')
def test_search_funds_success(mock_make_request: MagicMock):
    """Test successful search for funds."""
    mock_make_request.return_value = MOCK_SEARCH_RESPONSE_SUCCESS

    results = search_funds_by_name(MOCK_QUERY_SUCCESS)

    assert results is not None
    assert len(results) == 2
    assert results[0]["schemeCode"] == 123456 # Check against the expected alias key
    mock_make_request.assert_called_once_with(
        f"https://api.mfapi.in/mf/search", # Ensure using correct search path
        params={"q": MOCK_QUERY_SUCCESS}
    )

@patch('app.services.mfapi_service._make_request')
def test_search_funds_no_results(mock_make_request: MagicMock):
    """Test fund search returning no results."""
    mock_make_request.return_value = MOCK_SEARCH_RESPONSE_EMPTY

    results = search_funds_by_name(MOCK_QUERY_NO_RESULTS)

    assert results is not None
    assert len(results) == 0
    mock_make_request.assert_called_once_with(
        f"https://api.mfapi.in/mf/search",
        params={"q": MOCK_QUERY_NO_RESULTS}
    )

@patch('app.services.mfapi_service._make_request')
def test_search_funds_api_error(mock_make_request: MagicMock):
    """Test handling of API error during fund search."""
    mock_make_request.return_value = None # Simulate _make_request failure

    results = search_funds_by_name(MOCK_QUERY_FAIL)

    assert results is None
    mock_make_request.assert_called_once_with(
        f"https://api.mfapi.in/mf/search",
        params={"q": MOCK_QUERY_FAIL}
    )

@patch('app.services.mfapi_service._make_request')
def test_search_funds_unexpected_format(mock_make_request: MagicMock):
    """Test handling of unexpected data format from search API."""
    # Return something other than a list
    mock_make_request.return_value = {"message": "An error occurred"}

    results = search_funds_by_name(MOCK_QUERY_SUCCESS)

    # Assertions
    assert results is None # Service should return None if format is wrong
    mock_make_request.assert_called_once_with(
        f"https://api.mfapi.in/mf/search",
        params={"q": MOCK_QUERY_SUCCESS}
    )

# --- Tests for compare_funds ---
# compare_funds calls get_fund_details internally. We can patch get_fund_details directly.
@patch('app.services.mfapi_service.get_fund_details')
def test_compare_funds_success(mock_get_details: MagicMock):
    """Test successful comparison by fetching details for multiple funds."""
    codes_to_compare = [MOCK_SCHEME_CODE_SUCCESS, "789012"]
    mock_responses = {
        MOCK_SCHEME_CODE_SUCCESS: MOCK_FUND_DETAILS_RESPONSE,
        "789012": { # Simulate another fund's details
            "meta": {"scheme_code": 789012, "scheme_name": "Another Fund"},
            "data": [], "status": "SUCCESS"
        }
    }
    # Configure the mock to return different values based on the input scheme code
    mock_get_details.side_effect = lambda code: mock_responses.get(code)

    comparison_data = compare_funds(codes_to_compare)

    assert comparison_data is not None
    assert len(comparison_data) == 2
    assert MOCK_SCHEME_CODE_SUCCESS in comparison_data
    assert "789012" in comparison_data
    assert comparison_data[MOCK_SCHEME_CODE_SUCCESS]["meta"]["scheme_code"] == int(MOCK_SCHEME_CODE_SUCCESS)
    assert comparison_data["789012"]["meta"]["scheme_code"] == 789012
    # Check that get_fund_details was called for each code
    assert mock_get_details.call_count == len(codes_to_compare)
    mock_get_details.assert_any_call(MOCK_SCHEME_CODE_SUCCESS)
    mock_get_details.assert_any_call("789012")


@patch('app.services.mfapi_service.get_fund_details')
def test_compare_funds_partial_failure(mock_get_details: MagicMock):
    """Test comparison where fetching details for one fund fails."""
    codes_to_compare = [MOCK_SCHEME_CODE_SUCCESS, MOCK_SCHEME_CODE_FAIL]
    mock_responses = {
        MOCK_SCHEME_CODE_SUCCESS: MOCK_FUND_DETAILS_RESPONSE,
        MOCK_SCHEME_CODE_FAIL: None # Simulate failure for the second code
    }
    mock_get_details.side_effect = lambda code: mock_responses.get(code)

    comparison_data = compare_funds(codes_to_compare)

    assert comparison_data is not None
    assert len(comparison_data) == 2
    assert MOCK_SCHEME_CODE_SUCCESS in comparison_data
    assert MOCK_SCHEME_CODE_FAIL in comparison_data
    assert comparison_data[MOCK_SCHEME_CODE_SUCCESS] is not None
    assert comparison_data[MOCK_SCHEME_CODE_FAIL] is None # Check that failure is recorded as None
    assert mock_get_details.call_count == len(codes_to_compare)


def test_compare_funds_empty_input():
    """Test compare_funds with an empty list of scheme codes."""
    comparison_data = compare_funds([])
    assert comparison_data == {}

# Add more tests as needed, e.g., for edge cases in _make_request if desired. 