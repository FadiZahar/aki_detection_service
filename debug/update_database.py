import sqlite3
import csv

def update_patient_info_from_txt(db_path: str, info_path: str):
    """Updates patient age and sex information in the database from a .txt file.
    
    Args:
        db_path (str): The file path to the SQLite database.
        info_path (str): The file path to the .txt file containing the new information.
    """
    # Open the .txt file and read the new information
    with open(info_path, 'r') as file:
        # Assuming the file is comma-separated
        info_reader = csv.reader(file, delimiter=',')
        
        # Connect to the SQLite database
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()
            
            # Iterate through each line in the .txt file
            for row in info_reader:
                mrn, age, sex = row
                # Convert age and sex to the correct data types
                age = int(age)
                sex = int(sex)
                
                # Update the patient's information in the database
                c.execute('''
                    UPDATE patient_history
                    SET age = ?, sex = ?
                    WHERE mrn = ?
                ''', (age, sex, mrn))
                
            print("Patient information updated successfully.")

# Path to your database and new information .txt file
db_path = "state/my_database.db"
info_path = "data/new_info.txt"

# Update the database with the new information
update_patient_info_from_txt(db_path, info_path)
