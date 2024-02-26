import sqlite3
from datetime import datetime

def _calculate_age(dob: str) -> int:
    """Calculates a person's age in years based on their date of birth.

    Args:
        dob (str): The date of birth in "YYYYMMDD" format.

    Returns:
        int: The calculated age in years.
    """
    dob_datetime = datetime.strptime(dob, "%Y%m%d")
    current_datetime = datetime.now()

    age = current_datetime.year - dob_datetime.year - (
            (current_datetime.month, current_datetime.day) <
            (dob_datetime.month, dob_datetime.day))

    return age

def update_patient_info_from_txt(db_path: str, info_path: str):
    """Updates patient information in the database from a .txt file containing HL7 message segments.
    
    Args:
        db_path (str): The file path to the SQLite database.
        info_path (str): The file path to the .txt file containing the new information.
    """
    with open(info_path, 'r') as file:
        for line in file:
            if line.startswith("PID"):
                # Extract MRN, DOB, and Sex from the PID line
                parts = line.strip().split("|")
                mrn = parts[3]
                dob = parts[7]
                sex_str = parts[8]

                # Calculate age using the dob
                age = _calculate_age(dob)
                sex = 1 if sex_str == "F" else 0
                # Connect to the SQLite database
                with sqlite3.connect(db_path) as conn:
                    c = conn.cursor()
                    
                    # Update the patient's information in the database
                    c.execute('''
                        UPDATE patient_history
                        SET age = ?, sex = ?
                        WHERE mrn = ?
                    ''', (age, sex, mrn))
                    
    print("Patient information updated successfully.")

# Example usage
db_path = "state/my_database.db"
info_path = "data/recovery-data/messages.txt"
update_patient_info_from_txt(db_path, info_path)
