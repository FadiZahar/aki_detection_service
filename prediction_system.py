import http
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import threading
import http.server
import pandas as pd
import csv
import statistics

ACK = [
    "MSH|^~\&|||||20240129093837||ACK|||2.5",
    "MSA|AA",
]

MLLP_START_OF_BLOCK = 0x0b
MLLP_END_OF_BLOCK = 0x1c
MLLP_CARRIAGE_RETURN = 0x0d

# Global variables
messages = []
results = []
dict = {}
model = None

# Miscelaneous
def from_mllp(buffer):
    return str(buffer[1:-3], "ascii").split("\r") # Strip MLLP framing and final \r

def to_mllp(segments):
    m = bytes(chr(MLLP_START_OF_BLOCK), "ascii")
    m += bytes("\r".join(segments) + "\r", "ascii")
    m += bytes(chr(MLLP_END_OF_BLOCK) + chr(MLLP_CARRIAGE_RETURN), "ascii")
    return m


def preload_history(pathname='history.csv'): # Kyoya
    """
    Load the history of the all patients in a pandas dataframe.
    Index: MRN (patient id)
    Cols: age, sex , creatinine_result_1, creatinine_result_2, creatinine_result_3, creatinine_result_4, creatinine_result_5 
    
    inputs: history.csv
    outputs: database (pandas dataframe)
    """
    
    with open(pathname, 'r') as file:
        
        count = 0
        file = csv.reader(file)
        
        # Initialise lists to store processed data
        all_mrns = []
        all_constants = []
        all_results = []
        
        for row in file:
            # Skip the header row
            if count == 0:
                count += 1
                print('Starting to extract data...')
                continue
            
            # Remove empty fields
            cleaned_row = [value for value in row if value != '']
            
            # Extract age and sex
            mrn = cleaned_row[0]
            age = None
            sex = None

            # Extract all creatine test results
            constants =[age, sex]
            test_results = list(map(float, cleaned_row[2::2]))
            test_results.reverse() # Reverse the list to get the most recent tests first

            # Store the extracted data
            all_mrns.append(mrn)
            all_constants.append(constants)
            all_results.append(test_results)
                
        print(f'Extraction finished.\n')


    # Make all persons have the same number of test results
    number_of_tests = 5 # change as a hyperparameter BUT must change model as well

    all_results_constant = all_results.copy()

    print('Starting to process extracted data...')
    for row in range(len(all_results_constant)):
        # If person has less than 5 test results, add the mean of their test results to make up the difference
        if len(all_results_constant[row]) < number_of_tests:
            list_of_means = [statistics.mean(all_results_constant[row]) for i in range(5-len(all_results_constant[row]))]
            all_results_constant[row].extend(list_of_means)
        # If person has more than 5 test results, remove the oldest test results
        elif len(all_results_constant[row]) > number_of_tests:
            all_results_constant[row] = all_results_constant[row][:5]

    print(f'Processing finished.\n')

    # Combine constants and test results into one list
    processed = all_constants.copy()
    for i in range(len(all_results_constant)):
        processed[i].extend(all_results_constant[i])
        

    # Convert to pandas dataframe with column names
    column_names = ['age', 'sex'] + [f'test_{i}' for i in range(1, number_of_tests+1)]
    df = pd.DataFrame(processed, columns=[column_names], index = all_mrns)
    
    return df



def extract_type_and_mrn(message): 
    """
    Extract the message type and MRN (patient ID) from the HL7 message
    Message type can be: 'admission', 'discharge', 'creatinine_result'
    
    input: message (list of strings)
    output: type (string), id (string)
    """
    pass



def create_record(id, message):
    """
    Create a new record for the new patient in the database
    Index: MRN (patient id)
    Cols: age, sex (creatinine cols will be filled with NaN)
    
    inputs: MRN, HL7 message (list of strings)
    outputs: None
    """
    pass


def extract_features():
    """
    Extract the features from the HL7 message and local database (pandas dataframe)
    
    inputs: MRN, HL7 message (list of strings)
    outputs: features (list)
    """
    pass



# Threads
def processor(): # Carlos? or Kyoya?
    """
    Process messages and depending on the message type, update the database or make a prediction
    If the message is a admission, update the database
    If the message is a discharge, do nothing
    If the message is an creatinine result, make a prediction and notify hospital if positive, 
        (then finally update database)
    
    input: message (list of strings)
    output: None
    """
    pass



def message_reciever(): # Carlos
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(("localhost", 8440))
        while True:
            buffer = s.recv(1024)
            if len(buffer) == 0:
                break
            message = from_mllp(buffer)
            messages.append(message)
            ack = to_mllp(ACK)
            s.sendall(ack)

def main():
    pass
    # # start all threads
    # t1 = threading.Thread(target=message_reciever, args=("0.0.0.0", flags.mllp, hl7_messages, shutdown_mllp), daemon=True)
    # t1.start()
    # t1 = threading.Thread(target=message_reciever, args=("0.0.0.0", flags.mllp, hl7_messages, shutdown_mllp), daemon=True)
    # t1.start()
    # t1 = threading.Thread(target=message_reciever, args=("0.0.0.0", flags.mllp, hl7_messages, shutdown_mllp), daemon=True)
    # t1.start()



if __name__ == "__main__":
    main()
    dataframe = preload_history()
    print(dataframe.head())