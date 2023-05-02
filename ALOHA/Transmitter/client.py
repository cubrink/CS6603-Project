#import cv2, imutils, socket
import socket
#import numpy as np
import time
import base64
import Adafruit_DHT

import Adafruit_DHT

def create_socket(buffer_size):
	client_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
	client_socket.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF, buffer_size)
	return client_socket

def send_handshake(client_socket, host_ip, port):
	message = b'Hello'
	client_socket.sendto(message,(host_ip,port))


DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 66 # Pin 66 on BBB, P8_7
BUFF_SIZE = 65536
host_ip = '127.0.0.1'
port = 1234
WARNING_THRESH_SEC = 60
NS_PER_S = 10**9

use_synthetic_data = False

if __name__ == '__main__':
	data_fields = 	['timestamp', 'temperature', 'humidity', 'time_of_measurement', 'warning', 'uninitialized']
	
	host_name = socket.gethostname()
	client_socket = create_socket(buffer_size=BUFF_SIZE)
	send_handshake(client_socket, host_ip, port)
	print("Host IP: ", host_ip)

	prev_data = dict()
	unintialized = 1
	while True:
		timestamp = int(time.time() * NS_PER_S)
		if use_synthetic_data:
			humidity, temperature = 50, 50
		else:
			humidity, temperature = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN)
		
		if None in [humidity, temperature]:
			if unintialized:
				humidity, temperature = 0, 0
				time_of_measurement = 0
			else: 
				humidity = prev_data['humidity']
				temperature = prev_data['temperature']
				time_of_measurement = prev_data['time_of_measurement']
		else:
			unintialized = 0
			temperature = f"{temperature:0.1f}"
			humidity = f"{humidity:0.1f}"
			time_of_measurement = timestamp

		warning = 0
		if (timestamp - time_of_measurement) > WARNING_THRESH_SEC:
			warning = 1

		data = ','.join(
			map(str, [timestamp, temperature, humidity, time_of_measurement, warning, unintialized])
		)

		client_socket.sendto(data.encode('utf-8'),(host_ip,port))
		prev_data = dict(
			timestamp=timestamp,
			temperature=temperature,
			humidity=humidity,
			time_of_measurement=time_of_measurement,
			warning=warning,
			unintialized=unintialized,
		)
		time.sleep(0.02)
