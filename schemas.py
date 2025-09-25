# schemas.py
from pydantic import BaseModel
from typing import List, Dict, Any

class QueryRequest(BaseModel):
    question: str
    previous_sql: str | None = None
    feedback: str | None = None

class QueryResponse(BaseModel):
    analysis: str
    sql_query: str
    # The data can be any list of JSON objects (records)
    data: List[Dict[str, Any]]

class FeedbackRequest(BaseModel):
    question: str
    sql_query: str
    is_good: bool # True if the user liked it, False if not