import socket

import random
import time

HOST = "192.168.0.20"
PORT = 65432

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    while True:
        s.sendall(b'Hello world (from beaglebone)')
        data = s.recv(1024)
        print(f"Received: {data!r}")

        wait_time = 5 * random.random()
        time.sleep(wait_time)
