import sqlite3

def count_unassigned_mrn(db_path: str = 'state/copied_database.db'):
    """Counts MRNs with missing information in the database.

    Args:
        db_path (str): The file path to the SQLite database.

    Returns:
        int: The count of MRNs that are considered 'not assigned' based on
             missing information criteria.
    """
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        query = '''
        SELECT COUNT(mrn) FROM patient_history
        WHERE age IS NULL OR sex IS NULL
        '''
        c.execute(query)
        # Fetch the count of MRNs that match the query
        unassigned_mrn_count = c.fetchone()[0]
        return unassigned_mrn_count

# Define the database path
db_path = "state/copied_database.db"

# Get and print the count of MRNs with missing information
unassigned_mrn_count = count_unassigned_mrn(db_path)
print(f"Count of MRNs with missing information: {unassigned_mrn_count}")
