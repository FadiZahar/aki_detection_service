import argparse
import os
import sqlite3
import statistics
import csv

def preload_history_to_sqlite(db_path: str = 'state/my_database.db',
                              pathname: str = 'data/hospital-history/history.csv'):
    """Loads historical patient data from a CSV file into an SQLite database.

    This function processes a specified CSV file to extract patient identifiers
    (MRN: Medical Record Number) and up to five most recent creatinine test
    results. It then inserts the data into an SQLite database.

    Args:
        db_path (str): The file path to the SQLite database. Defaults to
                       'state/my_database.db'.
        pathname (str): The file path to the CSV file containing historical
                        patient data. Defaults to 'data/hospital-history/history.csv'.

    Returns:
        None: This function does not return a value but inserts data into the
              SQLite database.

    Note:
        - This function assumes the CSV file has a specific format, with the
          MRN as the first column, and creatinine test dates and results.
        - The SQLite database is structured to hold patient records with
          columns for MRN, age, sex, and the five most recent creatinine test
          results. It ensures each patient's record is unique with MRN serving
          as the primary key (index).
    """
    # Connect to the SQLite database.
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()

        # Create the table if it doesn't exist.
        c.execute('''
            CREATE TABLE IF NOT EXISTS patient_history (
                mrn TEXT PRIMARY KEY,
                age INTEGER,
                sex INTEGER,
                test_1 REAL,
                test_2 REAL,
                test_3 REAL,
                test_4 REAL,
                test_5 REAL
            )
        ''')

        with open(pathname, 'r') as file:
            csv_reader = csv.reader(file)
            next(csv_reader)  # Skip the header row.

            for row in csv_reader:
                cleaned_row = [value for value in row if value != '']
                mrn = cleaned_row[0]
                age = None
                sex = None
                test_results = list(map(float, cleaned_row[2::2]))
                test_results.reverse()  # Get tests from most to least recent.

                required_number_of_tests = 5

                # Ensure exactly 5 test results per patient.
                if len(test_results) < required_number_of_tests:
                    average_result = statistics.mean(test_results) \
                        if test_results else 0
                    test_results += [average_result] * (required_number_of_tests
                                                        - len(test_results))
                
                test_results = test_results[:required_number_of_tests]

                # Insert data into the database.
                c.execute('''
                    INSERT INTO patient_history (
                        mrn, age, sex, test_1, test_2, test_3, test_4, test_5
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(mrn) DO UPDATE SET
                    age=excluded.age,
                    sex=excluded.sex,
                    test_1=excluded.test_1,
                    test_2=excluded.test_2,
                    test_3=excluded.test_3,
                    test_4=excluded.test_4,
                    test_5=excluded.test_5
                ''', (mrn, age, sex, *test_results))

    # Connection is automatically committed & closed when exiting 'with' block.
    print("Data preloaded into SQLite database successfully.")

# define flag
parser = argparse.ArgumentParser()
parser.add_argument("--pathname", default="data/hospital-history/history.csv")
parser.add_argument("--db_path", default="state/my_database.db")
flags = parser.parse_args()

#load database
if os.path.exists(flags.db_path):
    print(f"The database file '{flags.db_path}' already exists.")
else:
    print(f"The database file '{flags.db_path}' does not exist, "
            f"proceeding to create it.")
    preload_history_to_sqlite(db_path=flags.db_path,
                                pathname=flags.pathname)