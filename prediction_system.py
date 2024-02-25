import os
import socket
import time
import signal
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
import numpy as np
import logging
from prometheus_client import start_http_server, Gauge
import json

#SIGTERM handling
def sigterm_handler(signum, frame):
    print("SIGTERM received, signaling threads to stop...")
    stop_event.set()

signal.signal(signal.SIGTERM, sigterm_handler)

# Configure logging.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Global event to signal threads when to exit, used for graceful shutdown.
stop_event = threading.Event()

# ACK messages formatted for HL7 protocol responses.
ACK = [
    "MSH|^~\&|||||20240129093837||ACK|||2.5",  # Header
    "MSA|AA",  # Acknowledgment Success
]

# Constants defining the MLLP (Minimum Lower Layer Protocol) framing.
MLLP_START_OF_BLOCK = 0x0b
MLLP_END_OF_BLOCK = 0x1c
MLLP_CARRIAGE_RETURN = 0x0d

# Shared state for message processing and acknowledgment signaling.
global messages, send_ack

# Model for processing messages. Load with appropriate model before use.
model = None

# Synchronisation lock for managing access to shared resources.
lock = threading.Lock()


def initialise_or_load_counters(save_path: str = 'state/counter_state.json'):
    # Initialise gauges with no values
    global MESSAGES_RECEIVED, MESSAGES_PROCESSED, BLOOD_TEST_RESULTS_RECEIVED, \
        POSITIVE_AKI_PREDICTIONS
    global UNSUCCESSFUL_PAGER_REQUESTS, MLLP_SOCKET_RECONNECTIONS, \
        POSITIVE_PREDICTION_RATE
    global BLOOD_TEST_RESULT_MEAN, BLOOD_TEST_RESULT_STDDEV

    MESSAGES_RECEIVED = \
        Gauge('messages_received',
              'Number of messages received')
    MESSAGES_PROCESSED = \
        Gauge('messages_processed',
              'Number of messages processed')
    BLOOD_TEST_RESULTS_RECEIVED = \
        Gauge('blood_test_results_received',
              'Number of blood test results received')
    POSITIVE_AKI_PREDICTIONS = \
        Gauge('positive_aki_predictions',
              'Number of positive AKI predictions')
    UNSUCCESSFUL_PAGER_REQUESTS = \
        Gauge('unsuccessful_pager_requests',
              'Number of unsuccessful pager HTTP requests')
    MLLP_SOCKET_RECONNECTIONS = \
        Gauge('mllp_socket_reconnections',
              'Number of reconnections to the MLLP socket')
    POSITIVE_PREDICTION_RATE = \
        Gauge('positive_prediction_rate',
              'Rate of positive AKI predictions')
    BLOOD_TEST_RESULT_MEAN = \
        Gauge('blood_test_result_mean',
              'Mean of blood test results')
    BLOOD_TEST_RESULT_STDDEV = \
        Gauge('blood_test_result_stddev',
              'Standard deviation of blood test results')

    try:  # Load saved counter states
        with open(save_path, 'r') as f:
            counter_state = json.load(f)

        print("Counter state file found, loading counters from file.")

        MESSAGES_RECEIVED.set(
            counter_state.get('messages_received', 0))
        MESSAGES_PROCESSED.set(
            counter_state.get('messages_processed', 0))
        BLOOD_TEST_RESULTS_RECEIVED.set(
            counter_state.get('blood_test_results_received', 0))
        POSITIVE_AKI_PREDICTIONS.set(
            counter_state.get('positive_aki_predictions', 0))
        UNSUCCESSFUL_PAGER_REQUESTS.set(
            counter_state.get('unsuccessful_pager_requests', 0))
        MLLP_SOCKET_RECONNECTIONS.set(
            counter_state.get('mllp_socket_reconnections', 0))
        BLOOD_TEST_RESULT_MEAN.set(
            counter_state.get('blood_test_result_mean', 0))
        BLOOD_TEST_RESULT_STDDEV.set(
            counter_state.get('blood_test_result_stddev', 0))

        # Calculate and set positive prediction rate based on the loaded values
        if MESSAGES_PROCESSED._value.get() > 0:  # Avoid division by zero
            rate = POSITIVE_AKI_PREDICTIONS._value.get() \
                   / MESSAGES_PROCESSED._value.get()
            POSITIVE_PREDICTION_RATE.set(rate)
            print("positive prediction rate set to: ", rate)

    except FileNotFoundError:
        # Create new counters if the state file doesn't exist
        print("No counter state file found, initialising counters at zero.")


def update_blood_test_result_mean(new_result):
    old_mean = BLOOD_TEST_RESULT_MEAN._value.get()
    number_of_results = BLOOD_TEST_RESULTS_RECEIVED._value.get()
    new_mean = (old_mean * (number_of_results - 1) + new_result) \
               / number_of_results
    BLOOD_TEST_RESULT_MEAN.set(new_mean)


def update_blood_test_result_stddev(new_result):
    old_mean = BLOOD_TEST_RESULT_MEAN._value.get()
    old_stddev = BLOOD_TEST_RESULT_STDDEV._value.get()
    number_of_results = BLOOD_TEST_RESULTS_RECEIVED._value.get()
    new_mean = (old_mean * (number_of_results - 1) + new_result) \
               / number_of_results
    new_stddev = np.sqrt((old_stddev ** 2 * (number_of_results - 1) +
                          (new_result - new_mean) ** 2) / number_of_results)
    BLOOD_TEST_RESULT_STDDEV.set(new_stddev)


# Global gauge for positive prediction rate
def update_positive_prediction_rate():
    global BLOOD_TEST_RESULTS_RECEIVED, POSITIVE_AKI_PREDICTIONS, \
        POSITIVE_PREDICTION_RATE
    current_rate = POSITIVE_AKI_PREDICTIONS._value.get() \
                   / BLOOD_TEST_RESULTS_RECEIVED._value.get() \
        if BLOOD_TEST_RESULTS_RECEIVED._value.get() > 0 else 0
    POSITIVE_PREDICTION_RATE.set(current_rate)


# Define save counter states to a file function
def save_counters(save_path: str = 'state/counter_state.json'):
    """Saves the current state of all Prometheus gauges to a JSON file.
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

    with open(save_path, 'w') as f:
        json.dump(counter_state, f)

    print("Counter states saved to 'state/counter_state.json'.")


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


def preload_history_to_sqlite(db_path: str = 'state/my_database.db',
                              pathname: str = 'hospital-history/history.csv'):
    """Loads historical patient data from a CSV file into an SQLite database.

    This function processes a specified CSV file to extract patient identifiers
    (MRN: Medical Record Number) and up to five most recent creatinine test
    results. It then inserts the data into an SQLite database.

    Args:
        db_path (str): The file path to the SQLite database. Defaults to
                       'state/my_database.db'.
        pathname (str): The file path to the CSV file containing historical
                        patient data. Defaults to 'hospital-history/history.csv'.

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
    conn = sqlite3.connect(db_path)
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
        file = csv.reader(file)
        next(file)  # Skip the header row.

        for row in file:
            cleaned_row = [value for value in row if value != '']

            mrn = cleaned_row[0]
            age = None
            sex = None
            test_results = list(map(float, cleaned_row[2::2]))
            test_results.reverse()  # Get tests from most to least recent.

            required_number_of_tests = 5

            # Ensure exactly 5 test results per patient.
            if len(test_results) < required_number_of_tests:
                if test_results:  # Ensure the list is not empty
                    average_result = statistics.mean(test_results)
                else:
                    average_result = 0  # Default value if no test available
                test_results += [average_result] * \
                                (required_number_of_tests - len(test_results))
            # Ensure no more than 5 results
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

    # Commit the changes and close the connection.
    conn.commit()
    conn.close()

    print("Data preloaded into SQLite database successfully.")


class AKIPredictor:
    """Class for processing HL7 messages to update patient data and predict AKI.

    Constructor Attributes:
        db_path (str): Path to the SQLite database.
                       Defaults to 'state/my_database.db'.
        model: Machine learning model for AKI prediction.
        metrics_count_flag (bool): Flag to enable or disable Prometheus metrics
                                   counting. Useful for disabling metrics
                                   updates during unit testing to prevent side
                                   effects. Defaults to True, enabling metrics
                                   counting.
        pending_predictions (set): Set of MRNs pending AKI prediction.
                                   Specifically for cases where LIMS test
                                   results messages have been received before
                                   their corresponding PAS admission messages.

    Methods:
        process_lims_message: Processes lab results from LIMS messages.
        process_pas_message: Processes patient admission data from PAS messages.
        _calculate_age: Calculates age from date of birth.
        _is_valid_dob: Validates the format of the date of birth.
        attempt_aki_prediction: Attempts to predict AKI based on patient data.
        examine_message_and_predict_aki: Main method to process HL7 messages.
    """

    def __init__(self, model, db_path: str = 'state/my_database.db',
                 metrics_count_flag=True):
        self.db_path = db_path
        self.model = model
        self.metrics_count_flag = metrics_count_flag
        self.pending_predictions = set()

    def process_lims_message(self, cursor, mrn: str, message: list[str],
                             msg_identifier: str) -> str | None:
        """Processes a LIMS (Laboratory Information Management System) message.

        The LIMS message contains lab test results; we are interested in
        creatinine blood test results -- message type "ORU^R01".
        The function updates the patient's test results in the database, and
        attempts an AKI prediction if possible.

        Args:
            cursor: SQLite database cursor.
            mrn (str): Medical Record Number of the patient.
            message (list[str]): HL7 message segments.
            msg_identifier (str): Identifier for logging purposes.

        Returns:
            Optional[str]: The MRN of a patient if an AKI prediction is
                           positive; otherwise, None.
        """
        test_type = message[3].split("|")[3]
        if test_type != "CREATININE":
            logging.error(f"{msg_identifier}\n>> Invalid test type: "
                          f"{test_type}")
            return None
        creatinine_result_str = message[3].split("|")[5]
        if not creatinine_result_str.replace('.', '', 1).isdigit():
            logging.error(f"{msg_identifier}\n>> Invalid test result format: "
                          f"{creatinine_result_str}")
            return None

        creatinine_result = float(creatinine_result_str)
        if self.metrics_count_flag:
            BLOOD_TEST_RESULTS_RECEIVED.inc()
            update_positive_prediction_rate()
            update_blood_test_result_mean(creatinine_result)
            update_blood_test_result_stddev(creatinine_result)

        # Check if MRN exists in the database
        cursor.execute("SELECT 1 FROM patient_history WHERE mrn = ?", (mrn,))
        exists = cursor.fetchone()
        if not exists:  # occurs if LIMS received before PAS for a specific MRN
            cursor.execute("INSERT INTO patient_history (mrn) VALUES (?)",
                           (mrn,))

        cursor.execute("""SELECT test_1, test_2, test_3, test_4, test_5 
                          FROM patient_history WHERE mrn = ?""", (mrn,))
        tests = cursor.fetchone()

        # Determine if any test results are already recorded
        if any(test is not None for test in tests):
            # Shift existing results to make room for the new one at 'test_1'.
            cursor.execute("""UPDATE patient_history 
                              SET test_5=test_4, test_4=test_3, test_3=test_2, 
                                  test_2=test_1, test_1=?
                              WHERE mrn=?""", (creatinine_result, mrn))
        else:
            # Initialise all test results with the current test result
            cursor.execute("""UPDATE patient_history
                              SET test_1=?, test_2=?, test_3=?, test_4=?, 
                                  test_5=?
                              WHERE mrn=?""",
                           (creatinine_result, creatinine_result,
                            creatinine_result, creatinine_result,
                            creatinine_result, mrn))

        self.pending_predictions.add(mrn)
        return self.attempt_aki_prediction(cursor, mrn, msg_identifier)

    def process_pas_message(self, cursor, mrn: str, message: list[str],
                            msg_identifier: str) -> str | None:
        """ Processes a PAS (Patient Administration System) message.

        The PAS message contains demographic (age and sex) information; we are
        interested in admission messages -- message type "ADT^A01".
        The function updates or inserts the patient's demographic data into the
        database. It also attempts an AKI prediction in case of pending ones
        stored for LIMS messages received for a new patient where the
        corresponding admission PAS message was still not received.

        Args:
            cursor: SQLite database cursor.
            mrn (str): Medical Record Number of the patient.
            message (list[str]): HL7 message segments.
            msg_identifier (str): Identifier for logging purposes.

        Returns:
            Optional[str]: The MRN of a patient if an AKI prediction is
                           positive; otherwise, None.
        """
        date_of_birth = message[1].split("|")[7]
        if not self._is_valid_dob(date_of_birth):
            logging.error(f"{msg_identifier}\n>> Invalid DOB format: "
                          f"{date_of_birth}")
            return None
        sex_str = message[1].split("|")[8]
        if sex_str not in ["F", "M"]:
            logging.error(f"{msg_identifier}\n>> Invalid sex value: "
                          f"{sex_str}")
            return None

        age = self._calculate_age(date_of_birth)
        sex = 1 if sex_str == "F" else 0

        # Update or insert the demographic information
        cursor.execute("""INSERT INTO patient_history (mrn, age, sex) 
                          VALUES (?, ?, ?) ON CONFLICT(mrn) DO 
                          UPDATE SET age=excluded.age, sex=excluded.sex""",
                       (mrn, age, sex))

        if mrn in self.pending_predictions:
            return self.attempt_aki_prediction(cursor, mrn, msg_identifier)
        return None

    @staticmethod
    def _calculate_age(dob: str) -> int:
        """Calculates a person's age in years based on their date of birth.

        The age is computed by comparing the current date with the provided
        date of birth (dob).

        Args:
            dob (str): The date of birth in "%Y%m%d" format.

        Returns:
            int: The calculated age in years.
        """
        dob_datetime = datetime.strptime(dob, "%Y%m%d")
        current_datetime = datetime.now()

        age = current_datetime.year - dob_datetime.year - (
                (current_datetime.month, current_datetime.day) <
                (dob_datetime.month, dob_datetime.day))

        return age

    @staticmethod
    def _is_valid_dob(dob: str) -> bool:
        """Check if the date of birth is in the correct format "%Y%m%d".

        Args:
            dob (str): The date of birth.

        Returns:
            bool: True if dob is in the "%Y%m%d" format, False otherwise.
        """
        try:
            datetime.strptime(dob, "%Y%m%d")
            return True
        except ValueError:
            return False

    def attempt_aki_prediction(self, cursor, mrn: str,
                               msg_identifier: str) -> str | None:
        """
        Attempts to predict AKI based on available patient data.

        Args:
            cursor: SQLite database cursor.
            mrn (str): Medical Record Number of the patient.
            msg_identifier (str): Identifier for logging purposes.

        Returns:
            Optional[str]: The MRN of a patient if an AKI prediction is
                           positive; otherwise, None.
        """
        cursor.execute("SELECT age, sex, test_1, test_2, test_3, test_4, test_5 "
                       "FROM patient_history WHERE mrn=?", (mrn,))
        patient_data = cursor.fetchone()

        # Ensure age and sex are not None (occurs if LIMS received before PAS)
        if patient_data and not any(val is None for val in patient_data[:2]):
            features = np.array(patient_data).reshape(1, -1)
            aki = self.model.predict(features)
            self.pending_predictions.remove(mrn)
            if aki:
                logging.info(f"{msg_identifier}\n>> AKI predicted for "
                             f"MRN: {mrn}")
                if self.metrics_count_flag:
                    POSITIVE_AKI_PREDICTIONS.inc()
                    update_positive_prediction_rate()
                return mrn
        return None

    def examine_message_and_predict_aki(self, message: list[str]) -> str | None:
        """Examines an HL7 message for patient data updates or AKI prediction.

        This function handles HL7 messages, updating the patient database with
        demographic information from ADT^A01 (PAS Admission) messages, or
        creatinine test results from ORU^R01 (LIMS) messages.
        For creatinine updates, it may trigger a prediction for acute kidney
        injury (AKI) using the provided pretrained machine learning model.

        Args:
            message (list[str]): The HL7 message split into string segments.

        Returns:
            Optional[str]: The MRN of a patient if an AKI prediction is
                           positive; otherwise, None.
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()

            message_type = message[0].split("|")[8]
            mrn = message[1].split("|")[3]
            timestamp = message[0].split("|")[6]
            msg_identifier = f"\n[MRN: {mrn} " \
                             f"\nmessage_type <{message_type}>" \
                             f"\ntimestamp: {timestamp}]"
            if not mrn.isdigit():
                logging.error(f"{msg_identifier}\n>> Invalid MRN format: {mrn}")
                return None

            if message_type == "ORU^R01":
                result = self.process_lims_message(c, mrn, message,
                                                   msg_identifier)
            elif message_type == "ADT^A01":
                result = self.process_pas_message(c, mrn, message,
                                                  msg_identifier)
            else:
                result = None

            conn.commit()
            return result

        except IndexError as e:
            logging.error(f"Error processing message due to invalid message "
                          f"format: {e}")
        except sqlite3.Error as e:
            logging.error(f"Database error: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
        finally:
            if conn:
                conn.close()
        return None


def processor(address: str, model,
              db_path: str = 'state/my_database.db') -> None:
    """Processes messages, updates database or makes predictions, and sends
    notifications.

    Loops indefinitely until a global stop event is set, handling HL7 messages
    by updating the patient database or making predictions based on the message
    content. Optionally sends a notification if AKI is detected.

    Args:
        address (str): Address to send notifications to, if necessary.
        model: Pretrained Machine learning model for predictions.
        db_path (str): Path to the SQLite database.

    Note:
        This function relies on global variables including a stop event, a lock,
        and message queues. It requires external setup of these components.
    """
    global messages, send_ack
    # Flag variables.
    run_code = False
    message = None

    aki_predictor = AKIPredictor(model, db_path)

    try:
        while not stop_event.is_set():
            lock.acquire()
            try:
                if len(messages) > 0:
                    message = messages.pop(0)
                    MESSAGES_RECEIVED.inc()
                    run_code = True
            finally:
                lock.release()

            if run_code:
                mrn = aki_predictor.examine_message_and_predict_aki(message)
                if mrn:
                    r = urllib.request.urlopen(f"http://{address}/page",
                                               data=mrn.encode('utf-8'))
                    if r.status != 200:
                        UNSUCCESSFUL_PAGER_REQUESTS.inc()
                # When the process ends, inform message_receiver to acknowledge.
                lock.acquire()
                try:
                    send_ack = True
                    MESSAGES_PROCESSED.inc()
                finally:
                    lock.release()
                run_code = False

    except Exception as e:
        print(f"An error occurred: {e}")

import socket
import time

def message_receiver(address: tuple[str, int], max_retries: int = 900, base_delay: float = 1.0, max_delay: float = 30.0) -> None:
    """Receives HL7 messages over a socket, decodes, and queues them for processing.
    
    Args:
        address (tuple[str, int]): Hostname and port number for the socket connection.
        max_retries (int): Maximum number of reconnection attempts.
        base_delay (float): Initial delay between reconnection attempts in seconds.
        max_delay (float): Maximum delay between reconnection attempts in seconds.
    """
    global message, send_ack
    attempt_count = 0
    delay = base_delay

    while not stop_event.is_set() and attempt_count < max_retries:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                print("Attempting to connect...")
                s.connect(address)
                print("Connected!")
                attempt_count = 0  # Reset attempt count after successful connection

                while not stop_event.is_set():
                    buffer = s.recv(1024)
                    if len(buffer) == 0:
                        MLLP_SOCKET_RECONNECTIONS.inc()
                        continue
                    message = from_mllp(buffer)

                    lock.acquire()
                    try:
                        messages.append(message)
                        MESSAGES_RECEIVED.inc()
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
                    MESSAGES_PROCESSED.inc()

        except Exception as e:
            print(f"An error occurred: {e}")
            time.sleep(delay)
            delay = min(delay * 2, max_delay)  # Exponential backoff with a maximum
            attempt_count += 1
            print(f"Attempting to reconnect, attempt {attempt_count}.")

    if attempt_count == max_retries:
        print("Maximum reconnection attempts reached, stopping.")
    print("Closing server socket.")


def main() -> None:
    """Initialises and starts the HL7 message processing system.

    This function sets up the environment and loads necessary resources such as
    the patient history database and the machine learning model for AKI
    prediction. It also starts threads for receiving HL7 messages and
    processing them.
    Configuration is done via command-line arguments and environment variables.
    The function waits for a keyboard interrupt (Ctrl+C) or a stop event to
    gracefully shut down all threads and exit the program.

    The message receiver thread listens for incoming HL7 messages over a TCP/IP
    socket, while the processor thread dequeues messages for processing,
    updating the SQLite database, and making AKI predictions as appropriate.
    Optionally, it sends notifications if AKI is detected.

    Environment Variables:
        MLLP_ADDRESS: Specifies the address and port of the MLLP server in the
                      format 'hostname:port'.
                      If not set, defaults to 'localhost:8440'.
        PAGER_ADDRESS: Specifies the address of the pager service for sending
                       notifications.
                       If not set, defaults to 'localhost:8441'.

    Command-Line Arguments:
        --pathname: Path to the CSV file containing historical patient data.
                    Defaults to 'hospital-history/history.csv'.
        --db_path: Path to the SQLite database file. Defaults to
                   'state/my_database.db'.

    Notes:
        - The programme relies on a globally shared state for managing incoming
          messages and signaling acknowledgments.
        - It uses a Prometheus server started on port 8000 for monitoring
          various metrics.
        - Upon exit, the state of Prometheus counters is saved for persistence
          across program restarts.
    """
    # Initialise threads to None
    t1 = None
    t2 = None

    try:
        warnings.filterwarnings("ignore")

        parser = argparse.ArgumentParser()
        parser.add_argument("--pathname", default="hospital-history/history.csv")
        parser.add_argument("--db_path", default="state/my_database.db")
        parser.add_argument("--metrics_path", default="state/counter_state.json")
        flags = parser.parse_args()

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

        if os.path.exists(flags.db_path):
            print(f"The database file '{flags.db_path}' already exists.")
        else:
            print(f"The database file '{flags.db_path}' does not exist, "
                  f"proceeding to create it.")
            preload_history_to_sqlite(db_path=flags.db_path,
                                      pathname=flags.pathname)

        initialise_or_load_counters(flags.metrics_path)

        with open("trained_model.pkl", "rb") as file:
            model = pickle.load(file)

        global messages, send_ack
        messages = []
        send_ack = False

        t1 = threading.Thread(target=lambda: message_receiver(mllp_address),
                              daemon=True)
        t2 = threading.Thread(target=lambda: processor(pager_address, model,
                                                       db_path=flags.db_path),
                              daemon=True)
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
        if t1 is not None:
            t1.join()
        if t2 is not None:
            t2.join()
        save_counters(flags.metrics_path)  # Save counter states before exiting
        print("Program exited gracefully.")


if __name__ == "__main__":
    start_http_server(8000)
    main()
