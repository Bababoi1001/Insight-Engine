# main.py
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

# Our refactored modules
from database import get_engine
from schemas import QueryRequest, QueryResponse, FeedbackRequest
import logic

# --- App Initialization ---
app = FastAPI(
    title="Chat with Your Database API",
    description="An API that converts natural language questions into SQL queries and insights.",
    version="1.0.0"
)


origins = [
    "http://localhost",
    "http://localhost:8080",
    "null",  # <--- Important for opening local .html files
    "file://",
]
# --- CORS Middleware ---
# Allows your front-end (on a different domain) to communicate with this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your front-end's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Dependency Injection for Engine ---
# This ensures we use the same engine instance across the app
engine = get_engine()

# --- API Endpoints ---
@app.get("/")
def read_root():
    return {"status": "API is running"}

@app.get("/schema")
async def get_database_schema():
    """
    Endpoint to retrieve the database schema summary.
    """
    try:
        # 'engine' is the global engine instance we already created
        schema_summary = logic.get_db_schema(engine)
        return {"schema": schema_summary}
    except Exception as e:
        # If get_db_schema fails, the exception is caught here
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve database schema: {str(e)}"
        )

@app.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest):
    """
    Main endpoint to process a user's question.
    """
    try:
        # Load enhanced schema from file (could be cached)
        with open("schema_documentation.md", "r") as f:
            enhanced_schema = f.read()

        # 1. Generate and Validate SQL
        final_sql = logic.generate_and_validate_sql(
            user_question=request.question,
            enhanced_schema=enhanced_schema,
            engine=engine,
            previous_sql=request.previous_sql,
            user_feedback=request.feedback
        )

        # 2. Execute the SQL Query
        with engine.connect() as connection:
            df = pd.read_sql(text(final_sql), connection)

        # 3. Get LLM Analysis of the results
        llm_summary = logic.get_llm_analysis(
            user_question=request.question,
            df=df,
            sql_query=final_sql
        )
        
        # 4. Format the DataFrame for JSON response
        data_as_json = df.to_dict(orient='records')

        return QueryResponse(
            analysis=llm_summary,
            sql_query=final_sql,
            data=data_as_json
        )

    except ValueError as ve:
        # Raised by our logic for validation failures
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        # Catch all other unexpected errors
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@app.post("/feedback")
async def handle_feedback(request: FeedbackRequest):
    """
    Endpoint to save a query that the user marked as helpful.
    """
    if request.is_good:
        success = logic.save_good_example(request.question, request.sql_query)
        if success:
            return {"status": "success", "message": "Example saved successfully."}
        else:
            raise HTTPException(status_code=500, detail="Failed to save the example.")
    else:
        # If feedback is not good, the front-end should call /query again with feedback text
        return {"status": "received", "message": "Feedback noted. Please re-query with corrections."}