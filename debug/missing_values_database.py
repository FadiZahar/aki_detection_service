import sqlite3

def find_unassigned_mrn(db_path: str = 'state/my_database.db'):
    """Finds MRNs with missing information in the database.

    Args:
        db_path (str): The file path to the SQLite database.

    Returns:
        list: A list of MRNs that are considered 'not assigned' based on
              missing information criteria.
    """
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        query = '''
        SELECT mrn FROM patient_history
        WHERE age IS NULL OR sex IS NULL 
        OR test_1 IS NULL OR test_2 IS NULL OR test_3 IS NULL 
        OR test_4 IS NULL OR test_5 IS NULL
        '''
        c.execute(query)
        # Fetch all MRNs that match the query
        unassigned_mrns = c.fetchall()
        # Extract MRN values from the query result tuples
        unassigned_mrns = [mrn[0] for mrn in unassigned_mrns]
        return unassigned_mrns

# Define the database path
db_path = "state/copied_database.db"

# Find and print MRNs with missing information
unassigned_mrns = find_unassigned_mrn(db_path)
print("MRNs with missing information:")
for mrn in unassigned_mrns:
    print(mrn)

