from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import date
import logging

logger = logging.getLogger(__name__)

# --- Models for Fund Details (get_fund_details response) ---

class FundNavData(BaseModel):
    """Represents a single historical NAV data point."""
    date_str: str = Field(..., alias="date")
    nav_value: float = Field(..., alias="nav")
    parsed_date: Optional[date] = None # Field to hold the parsed date

    @validator('parsed_date', always=True, pre=False)
    def parse_date_str(cls, v, values):
        """Parse the date string into a date object after initial validation."""
        date_str = values.get('date_str')
        if date_str:
            try:
                # Assuming format DD-MM-YYYY from the example
                day, month, year = map(int, date_str.split('-'))
                return date(year, month, day)
            except ValueError as e:
                logger.warning(f"Could not parse date string '{date_str}': {e}")
                # Keep parsed_date as None if parsing fails
        return None

    class Config:
        allow_population_by_field_name = True # Allows using alias 'date' and 'nav'
        # If you want validation errors on failure instead of Optional[date]
        # Keep track of aliases for easy export later if needed
        # schema_extra = {
        #     "example": {
        #         "date": "16-09-2022",
        #         "nav": 11.17710
        #     }
        # }

class FundMeta(BaseModel):
    """Represents the metadata part of the fund details response."""
    fund_house: str
    scheme_type: str
    scheme_category: str
    scheme_code: int
    scheme_name: str
    # Based on example, these might be null/None
    isin_growth: Optional[str] = None
    isin_div_reinvestment: Optional[str] = None

    class Config:
        # Example based on https://api.mfapi.in/mf/100364
        schema_extra = {
            "example": {
                "fund_house": "ICICI Prudential Mutual Fund",
                "scheme_type": "Open Ended Schemes",
                "scheme_category": "Debt Scheme - Long Duration Fund",
                "scheme_code": 100364,
                "scheme_name": "ICICI Prudential Long Term Bond Fund - Half Yearly IDCW",
                "isin_growth": None,
                "isin_div_reinvestment": None
            }
        }

class FundDetails(BaseModel):
    """Represents the entire response structure for get_fund_details."""
    meta: FundMeta
    data: List[FundNavData]
    status: str # e.g., "SUCCESS"

# --- Models for Fund Search (search_funds_by_name response) ---

class FundSearchResultItem(BaseModel):
    """Represents a single item in the fund search results list."""
    # Assuming snake_case based on user feedback, verify with actual API response
    scheme_code: int = Field(..., alias="schemeCode") # Keep alias for potential API variation
    scheme_name: str = Field(..., alias="schemeName")

    class Config:
        allow_population_by_field_name = True
        schema_extra = {
            "example": {
                "schemeCode": 120503,
                "schemeName": "Axis Bluechip Fund - Direct Plan - Growth"
            }
        }


#Define comparison model 
# We expect the search endpoint to return a list directly
# Type alias can be useful: FundSearchResponse = List[FundSearchResultItem] 