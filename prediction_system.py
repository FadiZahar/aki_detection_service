import os
import socket
import time
import urllib.error
import urllib.request
import threading
import pandas as pd
import csv
import statistics
from datetime import datetime
import pickle
import warnings
import argparse


# Global event to signal threads when to exit, used for graceful shutdown.
stop_event = threading.Event()

# ACK messages formatted for HL7 protocol responses.
ACK = [
    "MSH|^~\&|||||20240129093837||ACK|||2.5",   # Header
    "MSA|AA",   # Acknowledgment Success
]

# Constants defining the MLLP (Minimum Lower Layer Protocol) framing.
MLLP_START_OF_BLOCK = 0x0b  # Start block character
MLLP_END_OF_BLOCK = 0x1c    # End block character
MLLP_CARRIAGE_RETURN = 0x0d # Carriage return character

# Shared state for message processing and acknowledgment signaling.
global messages, send_ack   # Global variables

# Model for processing messages. Load with appropriate model before use.
model = None

# Synchronisation lock for managing access to shared resources.
lock = threading.Lock()


# Miscelaneous
def from_mllp(buffer: bytes) -> list[str]:
    """Decodes a buffer from MLLP encoding to a list of HL7 message segments.

    MLLP (Minimum Lower Layer Protocol) is used for the transmission of HL7
    messages over network sockets. This function takes a byte buffer received
    in MLLP format, including start and end block markers, and decodes it into
    a list of strings. Each string represents a segment of the decoded HL7
    message.

    Args:
        buffer (bytes): The byte buffer received in MLLP format, including the
                        start and end block markers and the carriage return.

    Returns:
        list: A list of strings, each representing a segment of the HL7 message.
    """
    # Strip MLLP framing and final \r
    return str(buffer[1:-3], "ascii").split("\r")


def to_mllp(segments: list[str]) -> bytes:
    """Encodes a list of HL7 message segments into MLLP format for transmission.

    This function takes a list of strings, where each string is a segment of an
    HL7 message, and encodes it into MLLP format. It adds the start and end
    block characters as well as a carriage return to conform with the MLLP
    standard for HL7 message transmission over network sockets.

    Args:
        segments (list[str]): A list of strings, where each string is a segment
                              of an HL7 message.

    Returns:
        bytes: A byte string encoded in MLLP format, ready for transmission
               over network sockets.
    """
    m = bytes(chr(MLLP_START_OF_BLOCK), "ascii")
    m += bytes("\r".join(segments) + "\r", "ascii")
    m += bytes(chr(MLLP_END_OF_BLOCK) + chr(MLLP_CARRIAGE_RETURN), "ascii")
    return m


def preload_history(pathname: str = 'data/history.csv') -> pd.DataFrame:
    """Loads historical patient data from a CSV file into a pandas DataFrame.

    This function processes a specified CSV file to extract patient identifiers
    (MRN: Medical Record Number) along with demographic information (age and
    sex, if available), and up to five most recent creatinine test results. It
    ensures data uniformity by filling in missing values as needed.

    Args:
        pathname (str): The file path to the CSV file containing historical
                        patient data. Defaults to 'data/history.csv'.

    Returns:
        pd.DataFrame: A DataFrame indexed by MRN with columns for age, sex, and
                      the five most recent creatinine test results for each
                      patient. Columns include age and sex (if available), and
                      creatinine test results are ordered from most recent
                      (test_1) to least recent (test_5).

    Note:
        - This function assumes the CSV file has a specific format, with the
          MRN as the first column, followed by optional demographic
          information, and creatinine test results.
        - Missing creatinine test results for patients with fewer than five
          records are filled with the mean of their available test results.
          If a patient has more than five test results, only the five most
          recent are kept.
    """
    with open(pathname, 'r') as file:
        
        count = 0
        file = csv.reader(file)
        
        # Initialise lists for storing MRNs, demographic info, and test results.
        all_mrns = []
        all_constants = []
        all_results = []
        
        for row in file:
            # Skip header row and start data extraction.
            if count == 0:
                count += 1
                print('Starting to extract data...')
                continue

            # Filter out empty fields from the row.
            cleaned_row = [value for value in row if value != '']
            
            # Extract MRN and initialise age, sex placeholders.
            mrn = cleaned_row[0]
            age = None
            sex = None

            # Extract creatinine test results and order them most recent first.
            constants =[age, sex]
            test_results = list(map(float, cleaned_row[2::2]))
            test_results.reverse()  # Most recent results first.

            # Append processed data for each patient.
            all_mrns.append(mrn)
            all_constants.append(constants)
            all_results.append(test_results)
                
        print(f'Extraction finished.\n')

    # Make all patients have the same number of test results.
    number_of_tests = 5

    all_results_constant = all_results.copy()

    print('Starting to process extracted data...')
    for row in range(len(all_results_constant)):
        # Extend lists with < 5 test results using the mean of existing results.
        if len(all_results_constant[row]) < number_of_tests:
            list_of_means = [statistics.mean(all_results_constant[row]) for i
                             in range(5-len(all_results_constant[row]))]
            all_results_constant[row].extend(list_of_means)
        # Trim lists with more than 5 test results to the most recent 5.
        elif len(all_results_constant[row]) > number_of_tests:
            all_results_constant[row] = all_results_constant[row][:5]

    print(f'Processing finished.\n')

    # Merge demographic info with test results.
    processed = all_constants.copy()
    for i in range(len(all_results_constant)):
        processed[i].extend(all_results_constant[i])

    # Create a DataFrame with structured patient data, indexed by MRN.
    column_names = ['age', 'sex'] + \
                   [f'test_{i}' for i in range(1, number_of_tests+1)]
    df = pd.DataFrame(processed, columns=[column_names], index=all_mrns)
    
    return df


def examine_message(message: list[str], df: pd.DataFrame, model) -> str | None:
    """Examines an HL7 message for patient data updates or AKI prediction.

    This function handles HL7 messages, updating the patient database with
    demographic information from ADT^A01 (PAS Admission) messages, or
    creatinine test results from ORU^R01 (LIMS) messages.
    For creatinine updates, it may trigger a prediction for acute kidney injury
    (AKI) using the provided pretrained machine learning model.

    Args:
        message (list[str]): The HL7 message split into string segments.
        df (pd.DataFrame): The current patient database.
        model: A pretrained machine learning model for predicting AKI based on
               patient age, sex, and test results.

    Returns:
        Optional[str]: The MRN of a patient if an AKI prediction is positive;
                       otherwise, None.

    Note:
        Assumes messages always conform to their expected format, being valid
        LIMS and PAS messages.
    """
    # Process LIMS (test result) for creatinine.
    if message[0].split("|")[8] == "ORU^R01" and \
            message[3].split("|")[3] == "CREATININE":
        mrn = message[1].split("|")[3]
        creatinine_result = float(message[3].split("|")[5])

        # Initialise or update test results in the patient's record.
        if df.loc[mrn, ['test_1', 'test_2', 'test_3', 'test_4', 'test_5']]\
                .isnull().any():
            # Assuming 'age' and 'sex' are already set through another process,
            # only initialise the test results if MRN is new (new record).
            df.loc[mrn, ['test_1', 'test_2', 'test_3', 'test_4', 'test_5']] \
                = [creatinine_result] * 5
        else:
            # Shift existing test results and insert the new creatinine result
            # at 'test_1' for an existing MRN (existing record).
            df.loc[mrn, 'test_5':'test_2'] = \
                df.loc[mrn, 'test_4':'test_1'].values
            df.at[mrn, 'test_1'] = creatinine_result

        # Use the model to predict AKI based on updated test results.
        features = df.loc[mrn].to_numpy().reshape(1, -1)
        aki = model.predict(features)
        return mrn if aki else None

    # Process PAS (admission message) to update demographic info.
    elif message[0].split("|")[8] == "ADT^A01":
        mrn = message[1].split("|")[3]
        # Extract date of birth (dob), calculate age, then update dataframe
        dob = message[1].split("|")[7]
        age = calculate_age(dob)
        df.loc[mrn, 'age'] = age
        # Extract sex, transform it into one-hot encoding, then update dataframe
        sex = message[1].split("|")[8]
        sex_bin = 1 if sex == "F" else 0
        df.loc[mrn, 'sex'] = sex_bin
        return None


def calculate_age(dob: str) -> int:
    """Calculates a person's age in years based on their date of birth.

    The age is computed by comparing the current date with the provided date
    of birth.

    Args:
        dob (str): The date of birth in "%Y%m%d" format.

    Returns:
        int: The calculated age in years.
    """
    # Define the format of the date of birth
    dob_format = "%Y%m%d"

    # Convert DOB from string to datetime object
    dob_datetime = datetime.strptime(dob, dob_format)

    # Get the current datetime
    current_datetime = datetime.now()

    # Calculate age
    age = current_datetime.year - dob_datetime.year - (
            (current_datetime.month, current_datetime.day) <
            (dob_datetime.month, dob_datetime.day))

    return age


# Threads
def processor(address: str, model, df: pd.DataFrame) -> None:
    """Processes messages, updates database or makes predictions, and sends
    notifications.

    Loops indefinitely until a global stop event is set, handling HL7 messages
    by updating the patient database or making predictions based on the message
    content. Optionally sends a notification if AKI is detected.

    Args:
        address (str): Address to send notifications to, if necessary.
        model: Pretrained Machine learning model for predictions.
        df (pd.DataFrame): Patient database as a pandas DataFrame.

    Note:
        This function relies on global variables including a stop event, a lock,
        and message queues. It requires external setup of these components.
    """
    # Point to global variables
    global messages, send_ack
    # Initialise flag to run code
    run_code = False
    message = None

    try:
        while not stop_event.is_set():
            # Send the acknowledgment
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
                    r = urllib.request.urlopen(f"http://{address}/page",
                                               data=mrn.encode('utf-8'))
                # Send the acknowledgment
                lock.acquire()
                try:
                    send_ack = True
                finally:
                    lock.release()
                # Wait until next message
                run_code = False               
    except Exception as e:
        print(f"An error occurred: {e}")


def message_receiver(address: tuple[str, int]) -> None:
    """Receives HL7 messages over a socket, decodes, and queues them for
    processing.

    Establishes a socket connection to continuously listen for HL7 messages at
    the specified address. Messages are decoded from MLLP format and added to
    a global queue. Sends acknowledgments back through the socket. Continues
    until a global stop event is set.

    Args:
        address (tuple[str, int]): Hostname and port number for the socket
                                   connection.
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

                # Wait for process to send the acknowledgement
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


def main() -> None:
    """Initialises and starts the HL7 message processing system.

    Sets up the environment, loads resources like the patient history database
    and machine learning model, and starts threads for receiving and processing
    messages. Uses command-line arguments and environment variables for
    configuration. Waits for a keyboard interrupt or a stop event to gracefully
    shut down threads and exit the program.

    Note:
        Expects environment variables 'MLLP_ADDRESS' and 'PAGER_ADDRESS' for
        configuring the addresses of the MLLP and pager services, respectively.
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
        t1 = threading.Thread(target=lambda: message_receiver(mllp_address),
                              daemon=True)
        t2 = threading.Thread(target=lambda: processor(pager_address, model,
                                                       database), daemon=True)
        t1.start()
        t2.start()

        # Instead of blocking indefinitely on join(), wait for threads to
        # complete in a loop that checks the stop_event status.
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
