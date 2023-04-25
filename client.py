import cv2, imutils, socket
import numpy as np
import time
import base64

BUFF_SIZE = 65536
client_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
client_socket.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,BUFF_SIZE)
host_name = socket.gethostname()
host_ip = '127.0.0.1'
print(host_ip)
port = 1234
message = b'Hello'

client_socket.sendto(message,(host_ip,port))
cnt = 0
while True:
	client_socket.sendto(str(cnt),(host_ip,port))
	cnt+=1
	time.sleep(1)
