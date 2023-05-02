#import cv2, imutils, socket
import socket
import numpy as np
import time
import base64
import os
######
#DATA_FILE_PATH = "/home/ubuntu/CS6603-Project/ALOHA/Receiver/DATA/datafile"
DATA_FILE_PATH = "DATA/datafile"
######
BUFF_SIZE = 65536
server_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
server_socket.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,BUFF_SIZE)
HOST='127.0.0.1'
PORT=4321
socket_address = (HOST,PORT)
server_socket.bind(socket_address)
print('Listening at',socket_address)
_,client_addr = server_socket.recvfrom(BUFF_SIZE)
print 'Got connection from', client_addr

node0 = "WithPD"
node1 = "WoutPD"
node0_pktno = '0'
node1_pktno = '0'
node0_data = '0'
node1_data = '0'
runNum = 0
while(os.path.exists(DATA_FILE_PATH + str(runNum))):
	runNum += 1
datafile = open(DATA_FILE_PATH + str(runNum), 'w')

while True:
	packet,_ = server_socket.recvfrom(BUFF_SIZE)
	data = packet.split()
	if data[0] == '0':
		node0_pktno = data[1]
		node0_data = data[2]
		datastring = ",".join([node0, node0_pktno, node0_data, str(time.time())])
	else:
		node1_pktno = data[1]
		node1_data = data[2]
		datastring = ",".join([node1, node1_pktno, node1_data, str(time.time())])
	printstring = "%5s : node0_pktno = %5s node0_data = %5s  |  %5s : node1_pktno = %5s node1_data = %5s" % (
                        node0, node0_pktno, node0_data, node1, node1_pktno, node1_data)
	
	datafile.write(datastring+"\n")
	print(printstring)
