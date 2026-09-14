import os

import psycopg
from dotenv import load_dotenv


load_dotenv()


DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


print("Connecting to PostgreSQL...")

conn = psycopg.connect(
    host=DB_HOST,
    port=DB_PORT,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
)

try:
    with conn.cursor() as cur:
        # Check which PostgreSQL user/database Python connected to
        cur.execute("SELECT current_user, current_database();")
        current_user, current_database = cur.fetchone()

        print("Connected successfully!")
        print("PostgreSQL user:", current_user)
        print("Database:", current_database)

        print("\n=== Conversations ===")

        cur.execute(
            """
            SELECT id, title, created_at
            FROM conversations
            ORDER BY id;
            """
        )

        conversations = cur.fetchall()

        for conversation in conversations:
            print(conversation)

        print("\n=== Messages ===")

        cur.execute(
            """
            SELECT id, conversation_id, role, content, created_at
            FROM messages
            ORDER BY id;
            """
        )

        messages = cur.fetchall()

        for message in messages:
            print(message)

finally:
    conn.close()
    print("\nDatabase connection closed.")
