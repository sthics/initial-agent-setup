# app/api/ai_routes.py

from fastapi import APIRouter, HTTPException, Body, status
import logging

from app.schemas.ai_schema import AIQueryRequest, AIQueryResponse
from app.agents.graph import run_agent # Import the function to run the agent

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ai",
    tags=["AI Agent"], # Tag for OpenAPI documentation grouping
)

@router.post(
    "/query",
    response_model=AIQueryResponse,
    summary="Query the AI agent about mutual funds",
    description="Sends a natural language question to the LangGraph agent for processing."
)
async def query_ai_agent(request: AIQueryRequest = Body(...)):
    """
    Processes a user's natural language question through the AI agent.
    """
    question = request.question
    logger.info(f"Received AI query request: '{question}'")

    try:
        # Run the agent graph with the user's question
        result = run_agent(question)

        summary = result.get('summary')
        error_message = result.get('error')

        if error_message:
            logger.warning(f"Agent execution finished with error for query '{question}': {error_message}")
            # Return 200 OK but include the agent's handled error message in the response
            return AIQueryResponse(summary=summary, error=error_message)
        elif not summary:
             # Should not happen if error handling is correct, but handle defensively
             logger.error(f"Agent execution finished with no summary and no error for query: '{question}'")
             raise HTTPException(
                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                 detail="Agent finished without providing a summary or an error."
             )
        else:
            logger.info(f"Successfully processed AI query: '{question}'")
            return AIQueryResponse(summary=summary)

    except Exception as e:
        # Catch unexpected errors during agent invocation
        logger.error(f"Unexpected error processing AI query '{question}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred while processing your request."
        )
    