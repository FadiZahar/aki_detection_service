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
    """
    Decodes a buffer from MLLP (Minimum Lower Layer Protocol) encoding to a string, specifically
    for HL7 message handling. MLLP is a protocol used for the transmission of HL7 messages over
    network sockets.

    Parameters:
    - buffer (bytes): The byte buffer received in MLLP format, including start and end block characters.

    Returns:
    - list of str: A list of strings, where each string represents a segment of the decoded HL7 message.
    """
    return str(buffer[1:-3], "ascii").split("\r") # Strip MLLP framing and final \r


def to_mllp(segments):
    """
    Encodes a list of HL7 message segments into MLLP format, adding start and end block characters
    as well as a carriage return to conform with the MLLP standard for HL7 message transmission.

    Parameters:
    - segments (list of str): A list of strings, where each string is a segment of an HL7 message.

    Returns:
    - bytes: A byte string encoded in MLLP format, ready for transmission over network sockets.
    """
    m = bytes(chr(MLLP_START_OF_BLOCK), "ascii")
    m += bytes("\r".join(segments) + "\r", "ascii")
    m += bytes(chr(MLLP_END_OF_BLOCK) + chr(MLLP_CARRIAGE_RETURN), "ascii")
    return m


def preload_history(pathname='data/history.csv'):
    """
    Loads historical patient data from a specified CSV file into a pandas DataFrame.

    The function processes the CSV file, extracting patient identifiers (MRN) along with
    demographic information (age and sex, if available) and up to five most recent creatinine
    test results, filling in missing values as needed to ensure uniformity.

    Parameters:
    - pathname (str): The file path to the CSV file containing historical patient data.
                      Defaults to 'data/history.csv'.

    Returns:
    - pandas.DataFrame: A DataFrame indexed by MRN with columns for age, sex, and the five
                        most recent creatinine test results for each patient.
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
    Examines an HL7 message, updating the patient database or making a prediction based on the
    message content. The function handles two types of messages: ADT^A01 for admissions, updating
    patient demographic information, and ORU^R01 for laboratory results, specifically creatinine
    test results, which may trigger a prediction for acute kidney injury (AKI) using the provided model.

    Parameters:
    - message (list of str): The HL7 message split into segments.
    - df (pandas.DataFrame): The current patient database.
    - model: A trained machine learning model for predicting AKI based on patient test results.

    Returns:
    - str or None: The MRN of a patient if an AKI prediction is positive; otherwise, None.
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
    Calculates the age of a person based on their date of birth.

    The function computes the age by comparing the current date with the date of birth provided.

    Parameters:
    - dob (str): The date of birth in "%Y%m%d" format.

    Returns:
    - int: The calculated age in years.
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
    Continuously processes messages from a global queue, updates the database or makes a prediction
    based on the message type, and optionally sends a notification if a condition (e.g., AKI) is detected.


    The function loops indefinitely until a global stop event is set. For each message, it determines
    the type of HL7 message received, updates the patient database or makes predictions accordingly,
    and sends notifications based on the outcomes of those predictions.

    Parameters:
    - address (str): The address to send notifications to, if necessary.
    - model: A machine learning model used for making predictions based on the data.
    - df (pd.DataFrame): The patient database represented as a pandas DataFrame.
    """
    # Point to global variables
    global messages, send_ack
    # Initialise flag to run code
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
    """
    Establishes a socket connection to receive HL7 messages, decoding them from MLLP format and adding
    them to a global queue for processing.


    This function continuously listens for incoming messages on the specified socket address. Upon receiving
    a message, it decodes the message from MLLP format and adds it to a global queue. It also handles sending
    acknowledgments back through the socket. The loop runs indefinitely until a global stop event is set.

    Parameters:
    - address (tuple): A tuple containing the hostname and port number for the socket connection.
    """
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
    """
    Main function to initialise and start the HL7 message processing system. It sets up the environment,
    loads necessary resources (such as the patient history database and machine learning model), and starts
    the message receiving and processing threads.

    Command-line arguments and environment variables are used to configure the system, including specifying
    the path to the patient history data file, the addresses for the MLLP and pager services. The function
    waits for a keyboard interrupt or a stop event to gracefully shut down the threads and exit the program.
    """
    try:
        # Suppress all warnings
        warnings.filterwarnings("ignore")

        # Add flag for history datafile
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

        # Initialize threads
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
