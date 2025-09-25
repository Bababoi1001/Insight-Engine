# File: database.py

import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Load environment variables from your .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Immediately check if the database URL is set
if not DATABASE_URL:
    raise ValueError("No DATABASE_URL found in environment variables. Please create a .env file.")

# Create the engine instance once when the app starts.
# This acts like a cache, as the code only runs one time.
engine = create_engine(DATABASE_URL, pool_size=5, max_overflow=10)

def get_engine():
    """Returns the globally created engine instance."""
    return engine