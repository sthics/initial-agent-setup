from fastapi import FastAPI

# Import routers
from app.api import fund_routes # Assuming fund_routes.py is in app/api
from app.api import ai_routes   # Import the new AI router

app = FastAPI(
    title="Agentic MFAPI AI",
    description="An agentic AI system for querying mutual fund data.",
    version="0.1.0",
)

@app.get("/")
async def read_root():
    return {"message": "Welcome to Agentic MFAPI AI"}

# Include routers
app.include_router(fund_routes.router)
app.include_router(ai_routes.router)