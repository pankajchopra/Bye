"""
FastAPI server implementation for DSPy Financial Advisor API
"""

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio

# Import from parent directory
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import FinancialAdvisorSystem

app = FastAPI(title="DSPy Financial Advisor API")

# Global system instance
financial_system = FinancialAdvisorSystem()

@app.post("/query")
async def process_financial_query(query: dict):
    """
    API endpoint to process financial queries
    """
    result = await financial_system.process_complex_query(
        query=query.get("query", ""),
        customer_context=query.get("customer_context", "")
    )
    return result

@app.get("/stream/{query_id}")
async def stream_query_progress(query_id: str):
    """
    SSE endpoint for streaming query progress
    """
    async def generate():
        # In real implementation, this would stream actual progress
        for i in range(5):
            yield f"data: {{\"progress\": {i*20}, \"status\": \"processing\"}}\n\n"
            await asyncio.sleep(1)
        yield f"data: {{\"progress\": 100, \"status\": \"completed\"}}\n\n"
    
    return StreamingResponse(generate(), media_type="text/plain")