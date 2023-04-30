#python transmitter.py -a addr=192.168.20.2 --tx-freq=1e6 --rx-freq=1e6 -r 200e3 --modulation=gmsk --demodulation=gmsk



from gnuradio import gr, gru
from gnuradio import blocks
from gnuradio import eng_notation
from gnuradio.eng_option import eng_option
from optparse import OptionParser
from gnuradio import digital

import gnuradio.gr.gr_threading as _threading
import random, time, struct, sys,socket

from numpy.core.fromnumeric import size

# from current dir (GNURadio->digital->narrowband)
from transmit_path import transmit_path
from receive_path import receive_path
from uhd_interface import uhd_transmitter,uhd_receiver

global tb, pktno, server
ack_flag = False
ALOHA_flag = False
data_buffer = []


class my_top_block(gr.top_block):
    def __init__(self, modulator,demodulator,rx_callback, options):
        gr.top_block.__init__(self)
        if(options.tx_freq is not None):
            args=modulator.extract_kwargs_from_options(options)
            symbol_rate=options.bitrate/modulator(**args).bits_per_symbol()
            self.sink=uhd_transmitter(options.args,symbol_rate,
                                        options.samples_per_symbol,options.tx_freq,
                                        options.lo_offset,options.tx_gain,
                                        options.spec,options.antenna,
                                        options.clock_source,options.verbose)
            options.samples_per_symbol=self.sink._sps
        self.txpath=transmit_path(modulator,options)
        self.connect(self.txpath,self.sink)  
        # listener setup
        if(options.rx_freq is not None):
            args=demodulator.extract_kwargs_from_options(options)
            symbol_rate=options.bitrate/demodulator(**args).bits_per_symbol()
            self.source=uhd_receiver(options.args, symbol_rate,
                                    options.samples_per_symbol,options.rx_freq,
                                    options.lo_offset,options.rx_gain,
                                    options.spec,options.antenna,
                                    options.clock_source,options.verbose)
            options.samples_per_symbol=self.source._sps
        self.rxpath=receive_path(demodulator,rx_callback,options)
        self.start_listen = self.rxpath.packet_receiver.start_listen
        self.stop_listen = self.rxpath.packet_receiver.stop_listen
        self.listen_status = self.rxpath.packet_receiver.status
        self.connect(self.source,self.rxpath)

class timer(_threading.Thread):
    '''set a timer and kill a thread'''
    def __init__(self, status,interval = None, object = None):
        _threading.Thread.__init__(self)
        self.setDaemon(1)
        self.target = object
        self.time = interval
        self.status = status

    def run(self):
        start_time = time.time()
        end_time = time.time()
        while not ack_flag:
            end_time = time.time()
            if end_time - start_time > self.time:
                # print('ACK Timeout')
                break
        self.target()

class ALOHA_listener(_threading.Thread): # <--------------------------change listener behavior
    def __init__(self, status,listener, stopper):
        _threading.Thread.__init__(self)
        self.setDaemon(1)
        self.status = status
        self.listener = listener
        self.stopper = stopper
        self.start()

    def run(self):
        run_inteval = 1   # <--------------------------change listening interval
        self._timer = timer(self.status, run_inteval,self.stopper)
        tb.rxpath.packet_receiver._rcvd_pktq.flush()
        self.listener()
        self._timer.start()
        self._timer.join()


class SERVER(_threading.Thread):
    def __init__(self):
        _threading.Thread.__init__(self)
        self.setDaemon(1)
        self.start()
    
    def run(self):
        global data_buffer
        while True:
            packet,_ = server.recvfrom(BUFF_SIZE)
            # print(data_buffer)
            data_buffer.append(packet)

def rx_callback(ok, payload):
        global ack_flag, ALOHA_flag
        if ok:
            if struct.unpack('!H', payload[2:4]) == (75,):
                # print('ACK  Received')
                ack_flag = True
                ALOHA_flag = True



def send_pkt(payload='', eof=False):
    return tb.txpath.send_pkt(payload, eof)
    
def ALOHA(pktno):
    payload = struct.pack('!H',pktno) +  struct.pack('!H',74)
    send_pkt(payload)
    tb.rxpath.packet_receiver._rcvd_pktq.flush()
    ALOHA = ALOHA_listener(tb.listen_status,tb.start_listen,tb.stop_listen)
    while ALOHA.is_alive():
        continue
    if ALOHA_flag:
        return True
    else:
        return False

def set_socket():
    BUFF_SIZE = 65536
    server_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    server_socket.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,BUFF_SIZE)
    HOST='127.0.0.1'
    PORT=1234
    socket_address = (HOST,PORT)
    server_socket.bind(socket_address)
    print('Listening at',socket_address)
    _,client_addr = server_socket.recvfrom(BUFF_SIZE)
    print 'Got connection from', client_addr
    return server_socket, BUFF_SIZE
# /////////////////////////////////////////////////////////////////////////////
#                                   main
# /////////////////////////////////////////////////////////////////////////////

def main():
    global tb,ALOHA_flag,ack_flag
    global server, BUFF_SIZE, data_buffer

    mods=digital.modulation_utils.type_1_mods()
    demods = digital.modulation_utils.type_1_demods()
    server, BUFF_SIZE = set_socket()
    s = SERVER()
    
    parser = OptionParser(option_class=eng_option, conflict_handler="resolve")
    expert_grp = parser.add_option_group("Expert")

    parser.add_option("-m", "--modulation", type="choice", choices=mods.keys(),
                      default='gmsk',
                      help="Select modulation from: %s [default=%%default]"
                            % (', '.join(mods.keys()),))
    parser.add_option("-m", "--demodulation", type="choice", choices=demods.keys(), 
                      default='gmsk',
                      help="Select modulation from: %s [default=%%default]"
                            % (', '.join(demods.keys()),))
    parser.add_option("-s", "--size", type="eng_float", default=4000,
                      help="set packet size [default=%default]")
    parser.add_option("-M", "--megabytes", type="eng_float", default=1.2,
                      help="set megabytes to transmit [default=%default]")
    parser.add_option("","--discontinuous", action="store_true", default=False,
                      help="enable discontinous transmission (bursts of 5 packets)")
    parser.add_option("","--from-file", default=None,
                      help="use file for packet contents")
    parser.add_option("","--live",action="store_true",default=False,
                        help="live play or not")
    parser.add_option("", "--compress", type="eng_float", default=20,
                      help="compress rate (1-100) [default=%default]")
    transmit_path.add_options(parser, expert_grp)
    uhd_transmitter.add_options(parser)
    receive_path.add_options(parser, expert_grp)
    uhd_receiver.add_options(parser)

    for mod in mods.values():
        mod.add_options(expert_grp)

    for mod in demods.values():
        mod.add_options(expert_grp)

    (options, args) = parser.parse_args ()


    if len(args) != 0:
        parser.print_help()
        sys.exit(1)

    if options.tx_freq is None:
         sys.stderr.write("You must specify -f FREQ or --freq FREQ\n")
         parser.print_help(sys.stderr)
         sys.exit(1)
    
    if options.rx_freq is None:
        sys.stderr.write("You must specify -f FREQ or --freq FREQ\n")
        parser.print_help(sys.stderr)
        sys.exit(1)

    data_buffer = []
    # build the graph
    tb = my_top_block(mods[options.modulation],demods[options.modulation],rx_callback, options)
    r = gr.enable_realtime_scheduling()
    if r != gr.RT_OK:
        print ("Warning: failed to enable realtime scheduling")
    tb.start()                       # start flow graph

    # generate and send packets
    n = 0
    pktno = 0
    while True:
        ALOHA_flag = False
        ack_flag = False
        if len(data_buffer) != 0:
            payload = struct.pack('!H',pktno) + struct.pack('!H',78) + '0' + data_buffer[0]
            print(pktno, "payload sent",payload[5:],data_buffer[0],'removed')
            data_buffer.pop(0)
            send_pkt(payload)

            #-----------------------------------------------
            # UNCOMMENT to enable ALOHA
            flag = ALOHA(pktno)
            while not flag:
                if random.randint(0,1) == 0:
                    print('wait 0.5 second')
                    time.sleep(0.5)
                    print(pktno, "payload sent",payload[5:])
                    send_pkt(payload)
                else:
                    print('wait 1 second')
                    time.sleep(1)
                    print(pktno, "payload sent",payload[5:])
                    send_pkt(payload)
                flag = ALOHA(pktno)
            else:
                ALOHA_flag = False
                ack_flag = False
            
            #-----------------------------------------------
            pktno += 1
            



    print ('\n')
    print ('billibillib: pktno = ', pktno-1, 'n = ', n)
    #must add below 'raw_input' to delay eof!!! otherwise, Thread tp may 
    # have not take out all the messages in the queue!
    input('billibillib : press any key to continue')       
    send_pkt(eof=True)
    tb.wait()                       # wait for it to finish

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass