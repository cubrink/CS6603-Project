#!/bin/sh

python transmitter.py -a addr=192.168.20.2 --tx-freq=1e6 --rx-freq=1e6 -r 200e3 --modulation=gmsk --demodulation=gmsk &
sudo python client.py