import sqlite3
import random

# Assuming this is your list of all possible MRNs
all_possible_mrns = ["4321", "3212", "54343", "41341", "68164"]

def find_random_missing_mrns_from_list(db_path: str, all_mrns: list, count: int = 500):
    """Finds a specified number of random MRNs from a Python list that have no records in the patient_history table.
    
    Args:
        db_path (str): The file path to the SQLite database.
        all_mrns (list): The list containing all possible MRNs.
        count (int): The number of random MRNs to find.
    
    Returns:
        list: A list of random MRNs with no records in the database.
    """
    # Convert the list to a set for faster lookups
    all_mrns_set = set(all_mrns)

    # Fetch all MRNs from the patient_history table
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute('SELECT mrn FROM patient_history')
        existing_mrns = {mrn[0] for mrn in c.fetchall()}

    # Find MRNs not in existing_mrns
    missing_mrns = list(all_mrns_set - existing_mrns)

    # Select a random subset if there are enough MRNs
    if len(missing_mrns) >= count:
        return random.sample(missing_mrns, count)
    else:
        print("Not enough MRNs missing to provide the requested count.")
        return missing_mrns

db_path = "state/my_database.db"
# Use the function with your MRN list
missing_mrns = find_random_missing_mrns_from_list(db_path, all_possible_mrns)
print(f"Random MRNs with no records (up to {len(missing_mrns)}):")
for mrn in missing_mrns:
    print(mrn)
