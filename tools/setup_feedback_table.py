"""
tools/setup_feedback_table.py

Adds the 'feedback' table to the SQLite database to store user-submitted adjustments.
"""
import argparse
import sqlite3
from pathlib import Path
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_feedback_table(cursor):
    """Creates the feedback table for storing user adjustments."""
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        record_id TEXT NOT NULL,
        develop_vector TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (record_id) REFERENCES records (id)
    )
    ''')
    logging.info("Table 'feedback' created or already exists.")

def main(args):
    db_path = Path(args.db)

    if not db_path.exists():
        logging.error(f"Database not found at {db_path}. Please run ingest_catalog.py first.")
        return

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        create_feedback_table(cursor)
        conn.commit()
        logging.info("Database schema successfully updated for feedback.")

    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
    finally:
        if conn:
            conn.close()
            logging.info("Database connection closed.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Setup feedback table in the database.")
    parser.add_argument('--db', default='data/nsp_plugin.db', help="Path to the SQLite database file.")
    args = parser.parse_args()
    main(args)
