#!/usr/bin/env python3

import argparse
import socket
import threading
import http.server

VERSION = "0.0.0"
MLLP_BUFFER_SIZE = 1024

def serve_mllp_client(client, source, messages):
    i = 0
    buffer = b""
    while i < len(messages):
        try:
            mllp = MLLP_START_OF_BLOCK.to_bytes() + messages[i] + MLLP_END_OF_BLOCK.to_bytes() + MLLP_CARRIAGE_RETURN.to_bytes()
            client.send(mllp)
            received = []
            while len(received) < 1:
                r = client.recv(MLLP_BUFFER_SIZE)
                if len(r) == 0:
                    raise Exception("client closed connection")
                buffer += r
                received, buffer = parse_mllp_messages(buffer, source)
            acked, error = verify_ack(received)
            if error:
                raise Exception(error)
            elif acked:
                i += 1
            else:
                print(f"mllp: {source}: message not acknowledged")
        except Exception as e:
            print(f"mllp: {source}: {e}")
            print(f"mllp: {source}: closing connection: error")
            break
    else:
            print(f"mllp: {source}: closing connection: end of messages")
    client.close()

HL7_MSA_ACK_CODE_FIELD = 1
HL7_MSA_ACK_CODE_ACCEPT = b"AA"

def verify_ack(messages):
    if len(messages) != 1:
        return False, f"Expected 1 ack message, found {len(messages)}"
    segments =  messages[0].split(b"\r")
    segment_types = [s.split(b"|")[0] for s in segments]
    if b"MSH" not in segment_types:
        return False, "Expected MSH segment"
    if b"MSA" not in segment_types:
        return False, "Expected MSA segment"
    fields = segments[segment_types.index(b"MSA")].split(b"|")
    if len(fields) <= HL7_MSA_ACK_CODE_FIELD:
        return False, "Wrong number of fields in MSA segment"
    return fields[HL7_MSA_ACK_CODE_FIELD] == HL7_MSA_ACK_CODE_ACCEPT, None

def run_mllp_server(host, port, hl7_messages):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen(1)
        print(f"mllp: listening on {host}:{port}")
        while True:
            client, (host, port) = s.accept()
            source = f"{host}:{port}"
            print(f"mllp: {source}: accepted connection")
            client.settimeout(MLLP_TIMEOUT_SECONDS)
            t = threading.Thread(target=serve_mllp_client, args=(client, source, hl7_messages), daemon=True)
            t.start()

MLLP_TIMEOUT_SECONDS = 10
MLLP_START_OF_BLOCK = 0x0b
MLLP_END_OF_BLOCK = 0x1c
MLLP_CARRIAGE_RETURN = 0x0d

def parse_mllp_messages(buffer, source):
    i = 0
    messages = []
    consumed = 0
    expect = MLLP_START_OF_BLOCK
    while i < len(buffer):
        if expect is not None:
            if buffer[i] != expect:
                raise Exception(f"{source}: bad MLLP encoding: want {hex(expect)}, found {hex(buffer[i])}")
            if expect == MLLP_START_OF_BLOCK:
                expect = None
                consumed = i
            elif expect == MLLP_CARRIAGE_RETURN:
                messages.append(buffer[consumed+1:i-1])
                expect = MLLP_START_OF_BLOCK
                consumed = i + 1
        else:
            if buffer[i] == MLLP_END_OF_BLOCK:
                expect = MLLP_CARRIAGE_RETURN
        i += 1
    return messages, buffer[consumed:]

def read_hl7_messages(filename):
    with open(filename, "rb") as r:
        messages, remaining = parse_mllp_messages(r.read(), filename)
        if len(remaining) > 0:
                print(f"messages: {len(messages)} remaining: {len(remaining)}")
                raise Exception(f"{filename}: Unexpected data at end of file")
        return messages

class PagerRequestHandler(http.server.BaseHTTPRequestHandler):

    def do_POST(self):
        self.server_version = f"coursework3-simulator/{VERSION}"
        if self.path == "/page":
            length = 0
            try:
                length = int(self.headers["Content-Length"])
            except Exception:
                print("pager: bad request: no Content-Length")
                self.send_response(http.HTTPStatus.BAD_REQUEST, "No Content-Length")
                self.end_headers()
                return
            mrn = 0
            try:
                mrn = int(self.rfile.read(length))
            except:
                print("pager: bad request: no MRN for /page")
                self.send_response(http.HTTPStatus.BAD_REQUEST, "Bad MRN in body")
                self.end_headers()
                return
            print(f"pager: paging for MRN {mrn}")
            self.send_response(http.HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            print("pager: bad request: not /page")
            self.send_response(http.HTTPStatus.BAD_REQUEST)
            self.end_headers()

    def do_GET(self):
        self.do_POST()

    def log_message(*args):
        pass # Prevent default logging

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--messages", default="messages.mllp", help="HL7 messages to replay, in MLLP format")
    parser.add_argument("--mllp", default=8440, type=int, help="Port on which to replay HL7 messages via MLLP")
    parser.add_argument("--pager", default=8441, type=int, help="Post on which to listen for pager requests via HTTP")
    flags = parser.parse_args()
    hl7_messages = read_hl7_messages(flags.messages)
    t = threading.Thread(target=run_mllp_server, args=("0.0.0.0", flags.mllp, hl7_messages), daemon=True)
    t.start()
    pager = http.server.ThreadingHTTPServer(("0.0.0.0", flags.pager), PagerRequestHandler)
    print(f"pager: listening on 0.0.0.0:{flags.pager}")
    pager.serve_forever()

if __name__ == "__main__":
    main()