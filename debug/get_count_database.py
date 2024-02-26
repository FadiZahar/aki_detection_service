import sqlite3

def get_record_count(db_path: str = 'state/my_database.db'):
    """Fetches the total number of patient records saved in the database.

    Args:
        db_path (str): The file path to the SQLite database.

    Returns:
        int: The total number of records in the patient_history table.
    """
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        # Query to count the number of rows in the patient_history table
        c.execute('SELECT COUNT(*) FROM patient_history')
        count = c.fetchone()[0]  # Fetch the count from the query result
        return count

# Define the database path
db_path = "state/copied_database.db"

# Get the count of records and print it
record_count = get_record_count(db_path)
print(f"Total number of patient records in the database: {record_count}")
