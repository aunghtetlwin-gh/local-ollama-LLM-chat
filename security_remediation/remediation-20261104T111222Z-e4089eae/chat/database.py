"""Shared database configuration. Importing this module never connects to PostgreSQL."""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

DB_NAME = os.getenv("DB_NAME")


def get_db_connection():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=DB_NAME,
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
