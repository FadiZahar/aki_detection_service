import os
import socket
import time
import urllib.error
import urllib.request
import threading
import csv
import statistics
from datetime import datetime
import pickle
import warnings
import argparse
import sqlite3
import csv
import statistics
from sqlite3 import Error
import numpy as np
import logging
from prometheus_client import Counter, start_http_server, Histogram, Gauge
import json

# Define initialize or load counter states functions
def initialize_or_load_counters():
    
    # Initialise gauges with no values
    global MESSAGES_RECEIVED, MESSAGES_PROCESSED, BLOOD_TEST_RESULTS_RECEIVED, POSITIVE_AKI_PREDICTIONS
    global UNSUCCESSFUL_PAGER_REQUESTS, MLLP_SOCKET_RECONNECTIONS, POSITIVE_PREDICTION_RATE
    global BLOOD_TEST_RESULT_MEAN, BLOOD_TEST_RESULT_STDDEV
    
    MESSAGES_RECEIVED = Gauge('messages_received', 'Number of messages received')
    MESSAGES_PROCESSED = Gauge('messages_processed', 'Number of messages processed')
    BLOOD_TEST_RESULTS_RECEIVED = Gauge('blood_test_results_received', 'Number of blood test results received')
    POSITIVE_AKI_PREDICTIONS = Gauge('positive_aki_predictions', 'Number of positive AKI predictions')
    UNSUCCESSFUL_PAGER_REQUESTS = Gauge('unsuccessful_pager_requests', 'Number of unsuccessful pager HTTP requests')
    MLLP_SOCKET_RECONNECTIONS = Gauge('mllp_socket_reconnections', 'Number of reconnections to the MLLP socket')
    POSITIVE_PREDICTION_RATE = Gauge('positive_prediction_rate', 'Rate of positive AKI predictions')
    BLOOD_TEST_RESULT_MEAN = Gauge('blood_test_result_mean', 'Mean of blood test results')
    BLOOD_TEST_RESULT_STDDEV =  Gauge('blood_test_result_stddev', 'Standard deviation of blood test results')
    
    try: # Load saved counter states
        with open('state/counter_state.json', 'r') as f:
            counter_state = json.load(f)

        print("Counter state file found, loading counters from file.")

        MESSAGES_RECEIVED.set(counter_state.get('messages_received', 0))
        MESSAGES_PROCESSED.set(counter_state.get('messages_processed', 0))
        BLOOD_TEST_RESULTS_RECEIVED.set(counter_state.get('blood_test_results_received', 0))
        POSITIVE_AKI_PREDICTIONS.set(counter_state.get('positive_aki_predictions', 0))
        UNSUCCESSFUL_PAGER_REQUESTS.set(counter_state.get('unsuccessful_pager_requests', 0))
        MLLP_SOCKET_RECONNECTIONS.set(counter_state.get('mllp_socket_reconnections', 0))
        BLOOD_TEST_RESULT_MEAN.set(counter_state.get('blood_test_result_mean', 0))
        BLOOD_TEST_RESULT_STDDEV.set(counter_state.get('blood_test_result_stddev', 0))

        # Calculate and set the positive prediction rate based on the loaded values
        if MESSAGES_PROCESSED._value.get() > 0:  # Ensure division by zero is not possible
            rate = POSITIVE_AKI_PREDICTIONS._value.get() / MESSAGES_PROCESSED._value.get()
            POSITIVE_PREDICTION_RATE.set(rate)
            print("positive prediction rate set to: ", rate)
        
    except FileNotFoundError:
        # Create new counters if the state file doesn't exist
        print("No counter state file found, initializing counters at zero.")

# Define function to update the mean of blood test results
def update_blood_test_result_mean(new_result):
    old_mean = BLOOD_TEST_RESULT_MEAN._value.get()
    number_of_results = BLOOD_TEST_RESULTS_RECEIVED._value.get()
    new_mean = (old_mean * (number_of_results - 1) + new_result) / number_of_results
    BLOOD_TEST_RESULT_MEAN.set(new_mean)

# Define function to update the standard deviation of blood test results
def update_blood_test_result_stddev(new_result):
    old_mean = BLOOD_TEST_RESULT_MEAN._value.get()
    old_stddev = BLOOD_TEST_RESULT_STDDEV._value.get()
    number_of_results = BLOOD_TEST_RESULTS_RECEIVED._value.get()
    new_mean = (old_mean * (number_of_results - 1) + new_result) / number_of_results
    new_stddev = np.sqrt((old_stddev ** 2 * (number_of_results - 1) + (new_result - new_mean) ** 2) / number_of_results)
    BLOOD_TEST_RESULT_STDDEV.set(new_stddev)

# Define save counter states to a file function
def save_counters():
    """
    Saves the current state of all Prometheus gauges to a JSON file.
    """
    counter_state = {
        'messages_received': MESSAGES_RECEIVED._value.get(),
        'messages_processed': MESSAGES_PROCESSED._value.get(),
        'blood_test_results_received': BLOOD_TEST_RESULTS_RECEIVED._value.get(),
        'positive_aki_predictions': POSITIVE_AKI_PREDICTIONS._value.get(),
        'unsuccessful_pager_requests': UNSUCCESSFUL_PAGER_REQUESTS._value.get(),
        'mllp_socket_reconnections': MLLP_SOCKET_RECONNECTIONS._value.get(),
        'blood_test_result_mean': BLOOD_TEST_RESULT_MEAN._value.get(),
        'blood_test_result_stddev': BLOOD_TEST_RESULT_STDDEV._value.get()
    }
    
    with open('state/counter_state.json', 'w') as f:
        json.dump(counter_state, f)
        
    print("Counter states saved to 'state/counter_state.json'.")

# Global gauge for positive prediction rate
def update_positive_prediction_rate():
    global BLOOD_TEST_RESULTS_RECEIVED, POSITIVE_AKI_PREDICTIONS, POSITIVE_PREDICTION_RATE
    current_rate = POSITIVE_AKI_PREDICTIONS._value.get() / BLOOD_TEST_RESULTS_RECEIVED._value.get() if BLOOD_TEST_RESULTS_RECEIVED._value.get() > 0 else 0
    POSITIVE_PREDICTION_RATE.set(current_rate)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Global event to signal threads when to exit, used for graceful shutdown.
stop_event = threading.Event()

# ACK messages formatted for HL7 protocol responses.
ACK = [
    "MSH|^~\&|||||20240129093837||ACK|||2.5",   # Header
    "MSA|AA",   # Acknowledgment Success
]

# Constants defining the MLLP (Minimum Lower Layer Protocol) framing.
MLLP_START_OF_BLOCK = 0x0b  
MLLP_END_OF_BLOCK = 0x1c    
MLLP_CARRIAGE_RETURN = 0x0d 

# Shared state for message processing and acknowledgment signaling.
global messages, send_ack, pending_predictions

# Initialising pending flag in case LIMS is received but age & sex are missing
pending_predictions = []

# Model for processing messages. Load with appropriate model before use.
model = None

# Synchronisation lock for managing access to shared resources.
lock = threading.Lock()


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


def calculate_age(dob: str) -> int:
    """Calculates a person's age in years based on their date of birth.

    The age is computed by comparing the current date with the provided date
    of birth.

    Args:
        dob (str): The date of birth in "%Y%m%d" format.

    Returns:
        int: The calculated age in years.
    """
    dob_format = "%Y%m%d"

    dob_datetime = datetime.strptime(dob, dob_format)

    current_datetime = datetime.now()

    age = current_datetime.year - dob_datetime.year - (
            (current_datetime.month, current_datetime.day) <
            (dob_datetime.month, dob_datetime.day))

    return age


def processor(address: str, model, db_path) -> None:
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
    global messages, send_ack
    # Flag variables
    run_code = False
    message = None

    try:
        while not stop_event.is_set():
            lock.acquire()
            try:
                if len(messages) > 0:
                    message = messages.pop(0)
                    MESSAGES_RECEIVED.inc() # once received, increment the messages received counter
                    run_code = True
            finally:
                lock.release()

            if run_code == True:
                # mrn = examine_message(message, df, model
                mrn = examine_message_and_predict_aki(message,  db_path=db_path, model=model)
                if mrn:
                    r = urllib.request.urlopen(f"http://{address}/page",
                                               data=mrn.encode('utf-8'))
                    if r.status != 200:
                            UNSUCCESSFUL_PAGER_REQUESTS.inc() # Increment counter for unsuccessful pager
                # When the process ends, inform message_receiver to acknowledge
                lock.acquire()
                try:
                    send_ack = True
                    MESSAGES_PROCESSED.inc() # once acknowledged, increment the messages processed counter
                finally:
                    lock.release()
                run_code = False

    except Exception as e:
        print(f"An error occurred: {e}")


def preload_history_to_sqlite(db_path='state/my_database.db', pathname='hospital-history/history.csv'):
    """
    Loads historical patient data from a specified CSV file and inserts it into an SQLite database.
    
    The function processes the CSV file, extracting patient identifiers (MRN) along with demographic 
    information (age and sex, if available) and up to five most recent creatinine test results, 
    filling in missing values as needed to ensure uniformity.
    
    Parameters:
    - db_path (str): The file path to the SQLite database. Defaults to 'my_database.db'.
    - pathname (str): The file path to the CSV file containing historical patient data.
                      Defaults to 'hospital-history/history.csv'.
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

def fill_none(data):
    # Copy the list to avoid modifying the original data
    filled_data = data.copy()
    # Find the rightmost non-None value starting from index 2
    for i in range(len(filled_data) - 1, 1, -1):
        if filled_data[i] is not None:
            rightmost_non_none = filled_data[i]
            break
    else:
        # If all values from index 2 onwards are None, use the value at index 2
        rightmost_non_none = filled_data[2]
    
    # Fill None values with the rightmost non-None value found
    for i in range(2, len(filled_data)):
        if filled_data[i] is None:
            filled_data[i] = rightmost_non_none
    
    return filled_data


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
                BLOOD_TEST_RESULTS_RECEIVED.inc()  # Increment blood test result counter
                update_positive_prediction_rate() # Update positive prediction rate
                
                mrn = message[1].split("|")[3]
                creatinine_result = float(message[3].split("|")[5])
                
                update_blood_test_result_mean(creatinine_result)  # Update mean of blood test results
                update_blood_test_result_stddev(creatinine_result) # Update standard deviation of blood test results
                
                # Fetch current test results for the MRN
                c.execute("""SELECT age, sex, test_1, test_2, test_3, test_4, test_5 FROM patient_history WHERE mrn=?""", (mrn,))
                row = c.fetchone()
                if row:
                    # Prepare data for prediction
                    current_tests = np.array(row)
                    c.execute("""UPDATE patient_history
                            SET test_5=test_4, test_4=test_3, test_3=test_2, test_2=test_1, test_1=?
                            WHERE mrn=?""", (creatinine_result, mrn)) #Check this

                    current_tests_np = np.insert(current_tests, 2, float(creatinine_result))
                    current_tests_np = fill_none(current_tests_np)
                    current_tests_np = current_tests_np[:-1]
                    current_tests_np = current_tests_np.reshape(1, -1)
                    aki_prediction = model.predict(current_tests_np)  # Assume this returns 1 for AKI, 0 otherwise
                    # Update database with new test result and shift older readings
                    if aki_prediction:
                        POSITIVE_AKI_PREDICTIONS.inc() # Increment positive AKI prediction counter
                        update_positive_prediction_rate()
                        return mrn
                    else:
                        return None
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

            c.execute("""SELECT age, sex, test_1, test_2, test_3, test_4, test_5 FROM patient_history WHERE mrn=?""", (mrn,))
            row = c.fetchone()
            
            # Update or insert demographic information
            c.execute("""INSERT INTO patient_history (mrn, age, sex) VALUES (?, ?, ?)
                         ON CONFLICT(mrn) DO UPDATE SET age=excluded.age, sex=excluded.sex""",
                      (mrn, age, sex_bin))
            
            # Test by Carlos
            c.execute("""SELECT age, sex, test_1, test_2, test_3, test_4, test_5 FROM patient_history WHERE mrn=?""", (mrn,))
            row = c.fetchone()
        conn.commit()

    except Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

    return None


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
    global message, send_ack
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            print("Attempting to connect...")
            s.connect(address)
            print("Connected!")
            while not stop_event.is_set():
                buffer = s.recv(1024)
                if len(buffer) == 0:
                    MLLP_SOCKET_RECONNECTIONS.inc()  # Increment MLLP socket reconnection counter
                    continue
                message = from_mllp(buffer)

                lock.acquire()
                try:
                    messages.append(message)
                    MESSAGES_RECEIVED.inc()  # Increment messages received counter
                finally:
                    lock.release()

                # Wait to receive heads-up to acknowledge from processor
                wait_flag = True
                while wait_flag:
                    lock.acquire()
                    try:
                        if send_ack:
                            wait_flag = False
                            send_ack = False
                    finally:
                        lock.release()
                ack = to_mllp(ACK)
                s.sendall(ack)
                MESSAGES_PROCESSED.inc()  # Increment messages processed counter

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
    print("Hola perroooos")
    try:
        warnings.filterwarnings("ignore")
        print("La mano arriba")
        parser = argparse.ArgumentParser()
        parser.add_argument("--pathname", default="hospital-history/history.csv")
        parser.add_argument("--db_path", default="state/my_database.db")
        flags = parser.parse_args()
        print("cintura sola")
        if 'MLLP_ADDRESS' in os.environ:
            mllp_address = os.environ['MLLP_ADDRESS']
            hostname, port_str = mllp_address.split(':')
            port = int(port_str)
            mllp_address = (hostname, port)
            print("MLLP_ADDRESS is set: ", mllp_address)
        else:
            mllp_address = ("localhost", 8440)
        print("da media vuelta")
        if 'PAGER_ADDRESS' in os.environ:
            pager_address = os.environ['PAGER_ADDRESS']
            print("PAGER_ADDRESS is set: ", pager_address)
        else:
            pager_address = "localhost:8441"
        print("danza cuduro")
        # Check if the database file already exists
        # db_path = 'my_database.db'
        print("Hello world")
        if os.path.exists(flags.db_path):
            print("Hello 1")
            print(f"The database file '{flags.db_path}' already exists.")
            # You may choose to exit here or perform any other action as needed
        else:
            print("Hello 2")
            print(f"The database file '{flags.db_path}' does not exist, proceeding to create it.")
            preload_history_to_sqlite(db_path=flags.db_path, pathname=flags.pathname)

        # Initialize or load counters
        initialize_or_load_counters()

        with open("trained_model.pkl", "rb") as file:
            model = pickle.load(file)

        global messages, send_ack
        messages = []
        send_ack = False

        t1 = threading.Thread(target=lambda: message_receiver(mllp_address),
                              daemon=True)
        t2 = threading.Thread(target=lambda: processor(pager_address, model, db_path=flags.db_path), daemon=True)
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
        save_counters() # Save counter states before exiting
        print("Program exited gracefully.")

if __name__ == "__main__":
    start_http_server(8000)
    main()
