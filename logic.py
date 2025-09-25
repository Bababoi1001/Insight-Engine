import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text, inspect
import os
import re
# Assuming prompt_logic.py exists with the necessary functions
from prompt_logic import build_prompt_from_files, query_olama
import sqlparse
from sqlparse.sql import Function, Identifier, Parenthesis
from sqlparse.tokens import Name, Keyword, Whitespace, Punctuation
import time
from sqlalchemy.exc import ProgrammingError
from sqlalchemy import text
from pathlib import Path
from database import get_engine
from sqlalchemy import inspect
from cachetools import cached, TTLCache


def fix_postgres_sql(sql: str) -> str:
    """
    Fixes common MySQL-style SQL issues for PostgreSQL using sqlparse.
    """
    parsed = sqlparse.parse(sql)
    if not parsed:
        return sql.strip()
    statement = parsed[0]

    def reparse_snippet(snippet: str):
        """Helper: turn a raw SQL string back into parsed tokens"""
        return sqlparse.parse(snippet)[0].tokens

    def process_tokens(tokens):
        for i, token in enumerate(tokens):
            if token.is_group:
                process_tokens(token.tokens)

            # Fix 1: `identifier` -> "identifier"
            if token.ttype is Name.Quoted:
                if token.value.startswith('`') and token.value.endswith('`'):
                    token.value = f'"{token.value[1:-1]}"'

            if isinstance(token, Function):
                func_name = None
                for sub_token in token.tokens:
                    if sub_token.is_keyword or isinstance(sub_token, Identifier):
                        func_name = sub_token.normalized
                        break
                if not func_name:
                    continue

                params = list(token.get_parameters())

                # Fix 2: NOW() -> CURRENT_TIMESTAMP
                if func_name == 'NOW' and not params:
                    token.tokens = reparse_snippet("CURRENT_TIMESTAMP")
                    continue

                # Fix 3: IFNULL(a, b) -> COALESCE(a, b)
                if func_name == 'IFNULL' and len(params) == 2:
                    token.tokens = reparse_snippet(
                        f"COALESCE({params[0].value}, {params[1].value})"
                    )

                # Fix 4: DATE(col) -> CAST(col AS DATE)
                if func_name == 'DATE' and len(params) == 1:
                    col = params[0].value
                    token.tokens = reparse_snippet(f"CAST({col} AS DATE)")

                # Fix 5: ROUND(col, n) -> ROUND(CAST(col AS NUMERIC), n)
                if func_name == 'ROUND' and len(params) == 2:
                    col, n = params[0].value, params[1].value
                    token.tokens = reparse_snippet(
                        f"ROUND(CAST({col} AS NUMERIC), {n})"
                    )

                # Fix 6: FORMAT_DATE('%B', col) -> TO_CHAR(col, 'Month')
                if func_name == 'FORMAT_DATE' and len(params) == 2:
                    col = params[1].value
                    token.tokens = reparse_snippet(
                        f"TO_CHAR({col}, 'Month')"
                    )

    process_tokens(statement.tokens)
    return str(statement).strip()

@cached(cache=TTLCache(maxsize=1, ttl=600))
def get_db_schema(engine):
    """Returns a simplified schema summary for LLM prompts."""
    try:
        inspector = inspect(engine)
        schema_context = ""
        schemas = ['public'] # You could make this a parameter if needed
        for schema in schemas:
            tables = inspector.get_table_names(schema=schema)
            for table in tables:
                schema_context += f"Table: {table}\n"
                columns = inspector.get_columns(table, schema=schema)
                for col in columns:
                    schema_context += f"  - {col['name']} ({col['type']})\n"
                schema_context += "\n"
        return schema_context.strip()
    except Exception as e:
        # Instead of using st.error, we print the error to the server's console
        # and re-raise the exception. The API endpoint will catch this and
        # return a proper HTTP 500 error to the front-end.
        print(f"CRITICAL: Error fetching database schema: {e}")
        raise

def is_query_valid(sql_query: str, engine) -> tuple[bool, str]:
    """Checks if a SQL query is valid by asking the database to EXPLAIN it."""

    clean_query = sql_query.strip().upper()

    # ✅ This is the corrected line
    if not (clean_query.startswith('SELECT') or clean_query.startswith('WITH')):
        return False, "Validation failed: Only SELECT or CTE statements can be checked."

    try:
        with engine.connect() as connection:
            connection.execute(text(f"EXPLAIN {sql_query}"))
        return True, "OK"
    except ProgrammingError as e:
        # Return the original, cleaner error message from the database
        return False, f"{e.orig}"
    except Exception as e:
        return False, f"An unexpected error occurred: {e}"


def generate_and_validate_sql(
    user_question: str,
    enhanced_schema: str,
    engine,
    max_syntax_retries: int = 2,
    # NEW: These parameters replace st.session_state
    previous_sql: str | None = None,
    user_feedback: str | None = None
) -> str:
    """
    Generates and validates a SQL query from a user question.
    Can also refine a query based on user feedback.
    Returns the validated SQL string or raises a ValueError on failure.
    """
    base_prompt_instruction = user_question

    # Logic to handle a retry based on user feedback (previously in session_state)
    if previous_sql and user_feedback:
        print("INFO: Re-generating query with user feedback.") # Server-side log
        feedback_context = f"\n**User's Feedback on Why It Was Wrong:**\n{user_feedback}"
        
        base_prompt_instruction = f"""
The user was not satisfied with the result from the previous query.
Analyze the user's original question, the previous query, and the user's feedback.
Create a new, corrected PostgreSQL query. Return ONLY the final SQL.

**User's Original Question:** {user_question}
**Previous Incorrect SQL Query:** {previous_sql}
{feedback_context}
"""

    generated_sql = ""
    error_message = ""

    # This loop is for automatic SYNTAX correction
    for attempt in range(max_syntax_retries + 1):
        prompt = ""
        if attempt == 0:
            prompt = build_prompt_from_files(
                enhanced_schema,
                Path("prompt_components/examples.txt"),
                base_prompt_instruction
            )
        else:
            # This is a syntax-fix retry
            print(f"INFO: Query validation failed. Retrying syntax. (Attempt {attempt + 1})")
            fix_instructions = f"""
The previously generated SQL query failed with a syntax error.
Analyze the schema, examples, user question, failed SQL, and the database error message.
Output ONLY the corrected, valid PostgreSQL query.

**Failed SQL Query:** {generated_sql}
**Database Error Message:** {error_message}
"""
            prompt = build_prompt_from_files(
                enhanced_schema,
                Path("prompt_components/examples.txt"),
                base_prompt_instruction + "\n\n" + fix_instructions
            )

        generated_sql_raw = query_olama(prompt)
        cleaned_sql = clean_sql_output(generated_sql_raw)
        generated_sql = fix_postgres_sql(cleaned_sql)

        is_valid, message = is_query_valid(generated_sql, engine)

        if is_valid:
            print("INFO: SQL query validated successfully.")
            return generated_sql  # SUCCESS! The function ends here.

        # If not valid, store the error message and the loop will continue
        error_message = message
        print(f"ERROR: Syntax Validation Error: {error_message}")

    # If the loop finishes without a 'return', it means all retries have failed.
    # We now raise a specific error instead of returning None.
    raise ValueError(
        f"Failed to generate a syntactically valid SQL query after {max_syntax_retries + 1} attempts. "
        f"Last database error: {error_message}"
    )

def clean_sql_output(raw_output: str) -> str:
    """
    Cleans raw LLM output to extract a pure SQL query.
    
    It strips leading junk by finding the start of 'SELECT' or 'WITH' and
    strips trailing junk by locating the last semicolon.

    Args:
        raw_output: The raw string response from the LLM.

    Returns:
        The cleaned SQL query, or an empty string if no valid
        query start is found.
    """
    if not raw_output:
        return ""

    # Find the start of the query (case-insensitive)
    match = re.search(r'\b(SELECT|WITH)\b', raw_output, re.IGNORECASE)
    
    if not match:
        return "" # No valid query start found

    # Create a substring from the start of the query to the end
    query_candidate = raw_output[match.start():]
    
    # Find the position of the last semicolon
    last_semicolon_pos = query_candidate.rfind(';')
    
    if last_semicolon_pos != -1:
        # If a semicolon is found, trim the query to that point
        final_query = query_candidate[:last_semicolon_pos + 1]
    else:
        # If no semicolon, assume the LLM forgot it and use the whole candidate string
        final_query = query_candidate
        
    # Return the result with any remaining leading/trailing whitespace removed
    return final_query.strip()

def get_llm_analysis(user_question: str, df: pd.DataFrame, sql_query: str) -> str:
    """
    Takes a dataframe and asks the LLM to provide a natural language analysis.
    """
    if df.empty:
        return "The query returned no results. There is nothing to analyze."

    # Convert the dataframe to a string format that's easy for the LLM to read.
    # Markdown is often better than CSV for LLMs.
    data_string = df.to_markdown(index=False)

    # Determine the prompt based on the result type (single vs. multi-value)
    if df.shape == (1, 1):
        # This is a single value result
        analysis_instruction = "You are a senior business strategist and data analyst." \
        "Your task is to transform a draft data analysis into a polished and concise executive summary suitable for leadership. " \
        "briefly explain what this number represents in a formal, easy-to-understand sentence. Dont utilize (**) aur any kinds of special characters." \
        "Keep it extremely professional and formal while displaying your findings."
    else:
        # This is a multi-value (table) result
        analysis_instruction = ""
        """
        You must present your analysis using the exact template structure that follows the data. " 
        "Write in a formal, professional tone using simple, easy-to-understand sentences. " 
        "Do not use any special characters like asterisks for bolding or emphasis.
        Introduction
            This document provides a high-level summary of the recent data analysis conducted on [briefly describe the dataset or area of focus]. The primary objective was to identify key performance indicators and derive actionable insights to inform our strategic decision-making.

            Key Findings
            * [Present the most important takeaway as a clear, complete sentence.]
            * [Present the next significant trend or total identified from the data.]
            * [Present another key observation or critical data point.]
            * [Present a final crucial insight necessary for a comprehensive overview.]

            Strategic Recommendations
            * [State a clear, professional recommendation directly linked to the first or most significant finding.]
            * [State another actionable recommendation based on the other findings to capitalize on opportunities or mitigate risks.]"""

    # Build the new prompt
    analysis_prompt = f"""
The user asked the following question:
"{user_question}"

To answer this, the following SQL query was executed:
```sql
{sql_query}
It produced this result:

Markdown

{data_string}
Your Task:
{analysis_instruction}
"""

    # Use your existing function to query the LLM
    # Note: You might want a different, more "creative" model for analysis
    # than the one you use for strict SQL generation.
    return query_olama(analysis_prompt)
