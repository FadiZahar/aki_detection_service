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

def format_to_mllp(message):
    """"""
    pass

def load_model():
    """
    load the model in model variable

    inputs: None
    outputs: None
    """
    pass

def preload_history():
    ""
    pass

def extract_features():
    pass

def create_record():
    pass

def extract_type_id():
    pass

# Threads
def processor():
    i = 0
    while i < 10:
        i += 1
        print("Hiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii")
        time.sleep(1)
    pass

def message_reciever():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            print("Attempting to connect...")
            s.connect(("localhost", 8440))
            print("Connected!")
            while True:
                buffer = s.recv(1024)
                if len(buffer) == 0:
                    break
                message = from_mllp(buffer)
                messages.append(message)
                ack = to_mllp(ACK)
                s.sendall(ack)
                print("Message received and ACK sent.")
                time.sleep(2)
    except Exception as e:
        print(f"An error occurred: {e}")

def main():
    pass
    # start all threads
    #TODO: load history

    t1 = threading.Thread(target=message_reciever, daemon=True)
    t1.start()
    t2 = threading.Thread(target=processor, daemon=True)
    t2.start()

    t1.join()
    t2.join()



if __name__ == "__main__":
    main()