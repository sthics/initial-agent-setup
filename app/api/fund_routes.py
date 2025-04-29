# app/api/fund_routes.py

from fastapi import APIRouter, Query, Path, HTTPException, Body
from typing import List, Dict, Optional
from pydantic import BaseModel, ValidationError

from app.services import mfapi_service
from app.schemas.fund_schema import FundDetails, FundSearchResultItem
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/funds",
    tags=["Mutual Funds"], # Tag for OpenAPI documentation grouping
)

# --- Request Models ---

class CompareRequest(BaseModel):
    """Request body model for comparing funds."""
    scheme_codes: List[str]

# --- API Endpoints ---
@router.get(
    "/search",
    response_model=List[FundSearchResultItem],
    summary="Search for mutual funds by name",
    description="Searches for funds using a query string and returns basic details (scheme code and name)."
)
async def search_funds(
    q: str = Query(..., min_length=3, description="Search query for fund name (minimum 3 characters)")
):
    """
    Searches for mutual funds based on a query string.
    """
    logger.info(f"Received search request with query: '{q}'")
    results = mfapi_service.search_funds_by_name(q)
    if results is None:
        logger.warning(f"Search service returned None for query: '{q}'. Returning empty list.")
        return []

    try:
        validated_results = [FundSearchResultItem.parse_obj(item) for item in results]
        return validated_results
    except ValidationError as e:
        logger.error(f"Validation error parsing search results for '{q}': {e}")
        raise HTTPException(status_code=500, detail="Error processing search results")
    except Exception as e:
        logger.error(f"Unexpected error parsing search results for '{q}': {e}")
        raise HTTPException(status_code=500, detail="Unexpected error processing search results")

@router.get(
    "/{scheme_code}",
    response_model=FundDetails,
    summary="Get detailed information for a specific fund",
    description="Retrieves comprehensive details including metadata and historical NAV for a given scheme code."
)
async def get_fund(
    scheme_code: str = Path(..., description="The unique scheme code of the mutual fund")
):
    """
    Retrieves details for a specific mutual fund scheme.
    """
    logger.info(f"Received request for fund details: {scheme_code}")
    details_dict = mfapi_service.get_fund_details(scheme_code)
    if details_dict is None:
        logger.warning(f"Fund details not found or error fetching for scheme: {scheme_code}")
        raise HTTPException(status_code=404, detail=f"Fund details not found for scheme code: {scheme_code}")

    try:
        validated_details = FundDetails.parse_obj(details_dict)
        return validated_details
    except ValidationError as e:
        logger.error(f"Validation error parsing fund details for '{scheme_code}': {e}")
        raise HTTPException(status_code=500, detail="Error processing fund details")
    except Exception as e:
        logger.error(f"Unexpected error parsing fund details for '{scheme_code}': {e}")
        raise HTTPException(status_code=500, detail="Unexpected error processing fund details")


@router.post(
    "/compare",
    response_model=Dict[str, Optional[FundDetails]], # Return full details for comparison
    summary="Compare multiple mutual funds",
    description="Fetches details for a list of provided scheme codes to allow comparison."
)
async def compare_funds_api(request: CompareRequest):
    """
    Compares multiple funds by fetching their details.
    """
    scheme_codes = request.scheme_codes
    if not scheme_codes:
        raise HTTPException(status_code=400, detail="No scheme codes provided for comparison.")

    logger.info(f"Received comparison request for schemes: {scheme_codes}")
    comparison_results_dict = mfapi_service.compare_funds(scheme_codes)

    parsed_comparison_results: Dict[str, Optional[FundDetails]] = {}
    validation_errors = []

    for code, details_dict in comparison_results_dict.items():
        if details_dict is not None:
            try:
                parsed_comparison_results[code] = FundDetails.parse_obj(details_dict)
            except ValidationError as e:
                logger.error(f"Validation error parsing comparison details for scheme '{code}': {e}")
                validation_errors.append(code)
                parsed_comparison_results[code] = None
            except Exception as e:
                logger.error(f"Unexpected error parsing comparison details for scheme '{code}': {e}")
                validation_errors.append(code)
                parsed_comparison_results[code] = None
        else:
            parsed_comparison_results[code] = None

    if validation_errors:
        logger.warning(f"Validation failed for schemes during comparison: {validation_errors}")

    return parsed_comparison_results 