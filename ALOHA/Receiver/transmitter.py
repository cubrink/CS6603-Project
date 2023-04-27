#python benchmark_transmitter.py -a addr=192.168.20.2 --tx-freq=2.45e9 -m gmsk -r 500e3 --from-file='/home/yue/Desktop/sample.png'


from gnuradio import gr, gru
from gnuradio import blocks
from gnuradio import eng_notation
from gnuradio.eng_option import eng_option
from optparse import OptionParser
from gnuradio import digital

import gnuradio.gr.gr_threading as _threading
import random, time, struct, sys
import cv2,imutils,base64

from numpy.core.fromnumeric import size

# from current dir (GNURadio->digital->narrowband)
from transmit_path import transmit_path
from receive_path import receive_path
from uhd_interface import uhd_transmitter,uhd_receiver

global tb, pktno
ack_flag = False
file_count = 0
random.seed(12)
random_pool = []
random_time_pool = []
handshake_break_flag = False
count_jump = 0

# f1 = open("/home/yue/Desktop/wnis/FHSS/f1.txt",'w')
# f2 = open("/home/yue/Desktop/wnis/FHSS/f2.txt",'w')
# file1 = open("/home/yue/Desktop/BENCHMARK/RTT.txt",'w')

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
        # listener setup for FHSS
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
        global ack_flag
        start_time = time.time()
        end_time = time.time()
        while not ack_flag:
            end_time = time.time()
            if end_time - start_time > self.time:
                # print('Listening timeout')
                break
        self.target()
        ack_flag = False

class handshake_listener(_threading.Thread): # <--------------------------change listener behavior
    def __init__(self, status,listener, stopper):
        _threading.Thread.__init__(self)
        self.setDaemon(1)
        self.status = status
        self.listener = listener
        self.stopper = stopper
        self.start()

    def run(self):
        run_inteval = 1
        self._timer = timer(self.status, run_inteval,self.stopper)
        tb.rxpath.packet_receiver._rcvd_pktq.flush()
        self.listener()
        self._timer.start()
        self._timer.join()

def rx_callback(ok, payload):
        global pktno,ack_flag,file_count, handshake_break_flag
        if ok:
            if struct.unpack('!H', payload[2:4]) == (75,):
                ack_flag = True
                handshake_break_flag = True


def send_pkt(payload='', eof=False):
    return tb.txpath.send_pkt(payload, eof)
    
# receive can't receive beacon and therad have problem
def jump(start_time, stop_time, pktno, frequency,frequency_offset, jump_tx, jump_rx):
    global handshake_break_flag,count_jump
    if stop_time - start_time < random_time_pool[0]:
    # if stop_time - start_time < 100000:
        return pktno, start_time
    else:
        payload = struct.pack('!H',pktno) +  struct.pack('!H',74)
        for i in range(4):
            send_pkt(payload)
            pktno += 1
            tb.rxpath.packet_receiver._rcvd_pktq.flush()
            FHSS_handshake = handshake_listener(tb.listen_status,tb.start_listen,tb.stop_listen)
            while FHSS_handshake.is_alive():
                continue
            if handshake_break_flag:
                handshake_break_flag = False
                break
        random_int = random_pool[0]
        random_pool.pop(0)
        random_time_pool.pop(0)
        print(count_jump, 'random int is', random_int)
        jump_tx._freq = jump_tx.set_freq(frequency_pool(random_int),frequency_offset)
        jump_rx._freq = jump_rx.set_freq(frequency_pool(random_int),frequency_offset)
        # jump_tx._freq = jump_tx.set_freq(random_int*100000,frequency_offset)
        # jump_rx._freq = jump_rx.set_freq(random_int*100000,frequency_offset)
        count_jump += 1
        start_time = time.time()
        return pktno, start_time

def frequency_pool(random_int):
    if random_int == 0:
        return 0.8e6
    elif random_int == 1:
        return 1e6
    elif random_int == 2:
        return 1.2e6



# /////////////////////////////////////////////////////////////////////////////
#                                   main
# /////////////////////////////////////////////////////////////////////////////

def main():
    global tb,random_pool,handshake_break_flag, random_time_pool

    random.seed(12)
    for i in range(0,1000000):
        random_pool.append(random.randint(0,2))
    for i in range(0, 10000):
        random_time_pool.append(0.001 * random.randint(1000,1100))
    mods=digital.modulation_utils.type_1_mods()
    demods = digital.modulation_utils.type_1_demods()

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

    if options.from_file is not None:
        if options.live:
            print ("enable live play")
            source_file = cv2.VideoCapture(options.from_file)
            fps,st,frames_to_count,cnt = (0,0,20,0)
        else:
            source_file = open(options.from_file, 'r')

    if options.from_file is None and options.live:
        print ('using webcam')
        source_file = cv2.VideoCapture("/dev/video4")
        fps,st,frames_to_count,cnt = (0,0,20,0)


    # build the graph
    tb = my_top_block(mods[options.modulation],demods[options.modulation],rx_callback, options)
    tb.sink.set_bandwidth(0.5e6)
    tb.source.set_bandwidth(0.5e6)
    print("The BW of TX is", tb.sink.ge_bandwidth(),'!!!!!!!!!!!!!!!!!!!!')
    print("The BW of RX is", tb.source.ge_bandwidth(),'!!!!!!!!!!!!!!!!!!!!')
    r = gr.enable_realtime_scheduling()
    if r != gr.RT_OK:
        print ("Warning: failed to enable realtime scheduling")
    tb.start()                       # start flow graph

    # generate and send packets
    nbytes = int(1e6 * options.megabytes)
    n = 0
    pktno = 0
    pkt_size = int(options.size)
    print ('\n')
    wow=0
    while True:
        fh_timer_start = time.time()
        fh_timer_stop = time.time()
        runing = time.time()
        while True:
            fh_timer_stop = time.time()
            pktno,fh_timer_start = jump(fh_timer_start,fh_timer_stop,pktno,tb.sink._freq - 0.005e9,
                                        options.lo_offset,tb.sink, tb.source)
            payload = struct.pack('!H',pktno) + struct.pack('!H',78) +  + 3996 * '0'
            send_pkt(payload)
            wow += 1
            pktno += 1
            sys.stderr.write('.')
            if time.time() - runing > 120:
                print(wow, count_jump)


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