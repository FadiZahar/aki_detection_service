import sqlite3
import csv
import statistics
from sqlite3 import Error

def preload_history_to_sqlite(db_path='my_database.db', pathname='data/history.csv'):
    """
    Loads historical patient data from a specified CSV file and inserts it into an SQLite database.
    
    The function processes the CSV file, extracting patient identifiers (MRN) along with demographic 
    information (age and sex, if available) and up to five most recent creatinine test results, 
    filling in missing values as needed to ensure uniformity.
    
    Parameters:
    - db_path (str): The file path to the SQLite database. Defaults to 'my_database.db'.
    - pathname (str): The file path to the CSV file containing historical patient data.
                      Defaults to 'data/history.csv'.
    """
    
    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Create the table if it doesn't exist
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
        file = csv.reader(file)
        next(file)  # Skip the header row
        
        for row in file:
            cleaned_row = [value for value in row if value != '']
            
            mrn = cleaned_row[0]
            age = None
            sex = None
            test_results = list(map(float, cleaned_row[2::2]))
            test_results.reverse()  # Reverse to get the most recent tests first
            
            # Ensure exactly 5 test results per patient
            while len(test_results) < 5:
                test_results.append(statistics.mean(test_results))  # Fill with mean
            test_results = test_results[:5]  # Ensure no more than 5 results
            
            # Insert data into the database
            c.execute('''
                INSERT INTO patient_history (mrn, age, sex, test_1, test_2, test_3, test_4, test_5)
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
    
    # Commit the changes and close the connection
    conn.commit()
    conn.close()

    print("Data preloaded into SQLite database successfully.")


def examine_message_and_predict_aki(message, db_path, model):
    """
    Examines an HL7 message, updating the patient database or making a prediction based on the
    message content using an SQLite database. If an AKI prediction is made, updates the test
    results in the database, shifting older readings.
    
    Parameters:
    - message (list of str): The HL7 message split into segments.
    - db_path (str): Path to the SQLite database.
    - model: A trained machine learning model for predicting AKI.
    """
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        if message[0].split("|")[8] == "ORU^R01":
            if message[3].split("|")[3] == "CREATININE":
                mrn = message[1].split("|")[3]
                creatinine_result = float(message[3].split("|")[5])

                # Fetch current test results for the MRN
                c.execute("""SELECT test_1, test_2, test_3, test_4, test_5 FROM patient_history WHERE mrn=?""", (mrn,))
                row = c.fetchone()

                if row:
                    # Prepare data for prediction
                    current_tests = np.array(row).reshape(1, -1)
                    aki_prediction = model.predict(current_tests)  # Assume this returns 1 for AKI, 0 otherwise
                    
                    # Update database with new test result and shift older readings
                    c.execute("""UPDATE patient_history
                                 SET test_5=test_4, test_4=test_3, test_3=test_2, test_2=test_1, test_1=?
                                 WHERE mrn=?""", (creatinine_result if aki_prediction == 0 else some_aki_indicator_value, mrn))
                else:
                    # If no existing records, insert new
                    c.execute("""INSERT INTO patient_history (mrn, test_1, test_2, test_3, test_4, test_5)
                                 VALUES (?, ?, ?, ?, ?, ?)""", (mrn, creatinine_result, creatinine_result, creatinine_result, creatinine_result, creatinine_result))

        elif message[0].split("|")[8] == "ADT^A01":
            mrn = message[1].split("|")[3]
            # Extract and calculate age, update database
            dob = message[1].split("|")[7]
            age = calculate_age(dob)  # Implement calculate_age based on your requirements
            # Extract sex and update database
            sex = message[1].split("|")[8]
            sex_bin = 1 if sex == "F" else 0
            
            # Update or insert demographic information
            c.execute("""INSERT INTO patient_history (mrn, age, sex) VALUES (?, ?, ?)
                         ON CONFLICT(mrn) DO UPDATE SET age=excluded.age, sex=excluded.sex""",
                      (mrn, age, sex_bin))

        conn.commit()

    except Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

    return None
