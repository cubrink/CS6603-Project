#!/usr/bin/python3

import Adafruit_DHT
import time
import os

DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 66 # Pin 66 on BBB, P8_7
 
while True:
    humidity, temperature = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN)
    if humidity is not None and temperature is not None:
        print("Temp={0:0.1f}C Humidity={1:0.1f}%".format(temperature, humidity))
    else:
        print("Sensor failure. Check wiring.");
    time.sleep(3);
