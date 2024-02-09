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
from datetime import datetime
import pickle
import warnings
from threading import Event
import argparse

# Create a global event that threads can check to know when to exit
stop_event = Event()

ACK = [
    "MSH|^~\&|||||20240129093837||ACK|||2.5",
    "MSA|AA",
]

MLLP_START_OF_BLOCK = 0x0b
MLLP_END_OF_BLOCK = 0x1c
MLLP_CARRIAGE_RETURN = 0x0d

# Global variables
global messages, send_ack
dict = {}
model = None
lock = threading.Lock()


# Miscelaneous
def from_mllp(buffer):
    return str(buffer[1:-3], "ascii").split("\r") # Strip MLLP framing and final \r


def to_mllp(segments):
    m = bytes(chr(MLLP_START_OF_BLOCK), "ascii")
    m += bytes("\r".join(segments) + "\r", "ascii")
    m += bytes(chr(MLLP_END_OF_BLOCK) + chr(MLLP_CARRIAGE_RETURN), "ascii")
    return m


def preload_history(pathname='/data/history.csv'): # Kyoya
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


def examine_message(message, df, model):
    """
    Extract the features from the HL7 message and local database (pandas dataframe)

    inputs: MRN, HL7 message (list of strings)
    outputs: features (list)

    # extract message type and MRN
            # based on the message type,
                # if PAS, retrieve age and sex and update the database
                # if LIMS,
                    # extract the creatinine result
                    # update database
                    # send features to make a prediction (feeding pretrained model)
                    # if prediction is positive, send a page to the hospital
            # send acknoladgement
    """
    # If LIMS message:
    if message[0].split("|")[8] == "ORU^R01":
        if message[3].split("|")[3] == "CREATININE":
            mrn = message[1].split("|")[3]
            creatinine_result = float(message[3].split("|")[5])

            # Initialise test results for new MRN or update existing MRN test results
            if df.loc[mrn, ['test_1', 'test_2', 'test_3', 'test_4', 'test_5']].isnull().any():
                # Assuming 'age' and 'sex' are already set through another process,
                # only initialise the test results if MRN is completely new.
                df.loc[mrn, ['test_1', 'test_2', 'test_3', 'test_4', 'test_5']] = [creatinine_result] * 5
            else:
                # Efficiently shift existing test results and insert the new creatinine result at 'test_1'
                # for an existing MRN.
                df.loc[mrn, 'test_5':'test_2'] = df.loc[mrn, 'test_4':'test_1'].values
                df.at[mrn, 'test_1'] = creatinine_result

            # Predict and handle AKI
            features = df.loc[mrn]
            features = features.to_numpy().reshape(1, -1)
            aki = model.predict(features)
            if aki:
                return mrn
            return None

    elif message[0].split("|")[8] == "ADT^A01":
        mrn = message[1].split("|")[3]
        # Extract age and update dataframe
        dob = message[1].split("|")[7]
        age = calculate_age(dob)
        df.loc[mrn, 'age'] = age
        # Extract sex and update dataframe
        sex = message[1].split("|")[8]
        sex_bin = 1 if sex == "F" else 0
        df.loc[mrn, 'sex'] = sex_bin
        return None


def calculate_age(dob):
    """
    Calculate the age given the date of birth.

    Parameters:
    dob (str): Date of birth in "%Y%m%d" format.

    Returns:
    int: Age
    """
    # Define the format of the date of birth
    dob_format = "%Y%m%d"

    # Convert DOB from string to datetime object
    dob_datetime = datetime.strptime(dob, dob_format)

    # Get the current datetime
    current_datetime = datetime.now()

    # Calculate age
    age = current_datetime.year - dob_datetime.year - (
            (current_datetime.month, current_datetime.day) < (dob_datetime.month, dob_datetime.day))

    return age

# Threads
def processor(address, model, df):
    """
    Process messages and depending on the message type, update the database or make a prediction
    If the message is a admission, update the database
    If the message is a discharge, do nothing
    If the message is an creatinine result, make a prediction and notify hospital if positive, 
        (then finally update database)
    
    input: message (list of strings)
    output: None
    """
    
    # Point to global variables
    global messages, send_ack
    # Initialize flag to run code
    run_code = False
    message = None
    try:
        while not stop_event.is_set():
            # Send the acknolagment
            # Acquire the lock before accessing shared variables
            lock.acquire()
            try:
                if len(messages) > 0:
                    message = messages.pop(0)
                    run_code = True
            finally:
                # Ensure the lock is always released
                lock.release()
            if run_code == True:

                mrn = examine_message(message, df, model)
            
                if mrn:
                    r = urllib.request.urlopen(f"http://{address}/page", data=mrn.encode('utf-8'))

                # Send the acknolagment
                lock.acquire()
                try:
                    send_ack = True
                finally:
                    lock.release()
                # Wait until next message
                run_code = False               
    except Exception as e:
        print(f"An error occurred: {e}")


def message_reciever(address):
    # Point to global
    global message, send_ack
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            print("Attempting to connect...")
            s.connect(address)
            print("Connected!")
            while not stop_event.is_set():
                buffer = s.recv(1024)
                if len(buffer) == 0:
                    continue
                message = from_mllp(buffer)

                # Add message to messages pipeline
                lock.acquire()
                try:
                    messages.append(message)
                finally:
                    lock.release()

                # Wait for proccess to send the acknowledgement
                wait_flag = True
                while wait_flag:
                    lock.acquire()
                    try:
                        if send_ack:
                            wait_flag = False
                            send_ack = False
                    finally:
                        lock.release()
                # Send acknowledgement
                ack = to_mllp(ACK)
                s.sendall(ack)
    except Exception as e:
        print(f"An error occurred: {e}") 
    print("Closing server socket.")
    s.close()


def main():
    try:
        # Suppress all warnings
        warnings.filterwarnings("ignore")

        parser = argparse.ArgumentParser()
        parser.add_argument("--pathname", default="data/history.csv")
        flags = parser.parse_args()

        # Getting environment variables
        if 'MLLP_ADDRESS' in os.environ:
            mllp_address = os.environ['MLLP_ADDRESS']
            hostname, port_str = mllp_address.split(':')
            port = int(port_str)
            mllp_address = (hostname, port)
            print("MLLP_ADDRESS is set: ", mllp_address)

        else:
            mllp_address = ("localhost", 8440)

        if 'PAGER_ADDRESS' in os.environ:
            pager_address = os.environ['PAGER_ADDRESS']
            print("PAGER_ADDRESS is set: ", pager_address)
        else:
            pager_address = "localhost:8441"
        # Load history.csv
        database = preload_history(pathname=flags.pathname)
        
        # Load the trained model
        with open("trained_model.pkl", "rb") as file:
            model = pickle.load(file)

        # Start global variables
        global messages, send_ack
        messages = []
        send_ack = False
        t1 = threading.Thread(target=lambda: message_reciever(mllp_address), daemon=True)
        t2 = threading.Thread(target=lambda: processor(pager_address, model, database), daemon=True)
        t1.start()
        t2.start()

        # Instead of blocking indefinitely on join(), wait for threads to complete
        # in a loop that checks the stop_event status.
        while True:
            if stop_event.is_set():
                print("Stopping threads...")
                break
            time.sleep(1)  # Wait a bit for threads to check the stop_event

    except KeyboardInterrupt:
        print("\nDetected Ctrl+C, setting stop event for threads.")
        stop_event.set()

    finally:
        # Ensure that we attempt to join threads even after Ctrl+C
        # This waits for threads to acknowledge the stop_event and exit
        t1.join()
        t2.join()
        print("Program exited gracefully.")

if __name__ == "__main__":
    main()
