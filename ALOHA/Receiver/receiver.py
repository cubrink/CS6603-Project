#python receiver.py -a addr=192.168.10.2 --rx-freq=1e6 --tx-freq=1e6 -r 200e3 --demodulation=gmsk --modulation=gmsk

from gnuradio import gr, gru
from gnuradio import blocks
from gnuradio import eng_notation
from gnuradio.blocks.blocks_swig0 import file_sink
from gnuradio.eng_option import eng_option
from optparse import OptionParser
from gnuradio import digital
from gnuradio.filter import firdes


import random,struct,sys,socket,time,os

# from current dir (GNURadio->digital->narrowband)
from receive_path import receive_path
from transmit_path import transmit_path
from uhd_interface import uhd_receiver,uhd_transmitter

global tb
file_count = 0

class my_top_block(gr.top_block):

    def __init__(self, modulator, demodulator, rx_callback, options):
        gr.top_block.__init__(self)
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
    
    def update_thread(self):
        self.start_listen = self.rxpath.packet_receiver.start_listen
        self.stop_listen = self.rxpath.packet_receiver.stop_listen
        self.listen_status = self.rxpath.packet_receiver.status

def send_pkt(payload='', eof=False):
    return tb.txpath.send_pkt(payload, eof)

# /////////////////////////////////////////////////////////////////////////////
#                                   main
# /////////////////////////////////////////////////////////////////////////////

global n_rcvd, n_right

def main():
    global tb, n_rcvd, n_right,temp_message,error, Time_start, Time_end, data_rate

    temp_message=''
    n_rcvd = 0
    n_right = 0
    error = 0
    Time_start = time.time()
    data_rate = 0
    #########
    DATA_FILE_PATH = "/home/ubuntu/CS6603-Project/ALOHA/RECEIVER/DATA/datafile"
    dfNum = 0
    while(os.path.exists(DATA_FILE_PATH+str(dfNUm))):
        dfNum += 1
    DATA_FILE_PATH += str(dfNum)
    #########
    demods = digital.modulation_utils.type_1_demods()
    mods=digital.modulation_utils.type_1_mods()

    # Create Options Parser:
    parser = OptionParser (option_class=eng_option, conflict_handler="resolve")
    expert_grp = parser.add_option_group("Expert")
    parser.add_option("-m", "--demodulation", type="choice", choices=demods.keys(), 
                      default='gmsk',
                      help="Select modulation from: %s [default=%%default]"
                            % (', '.join(demods.keys()),))
    parser.add_option("-m", "--modulation", type="choice", choices=mods.keys(),
                    default='gmsk',
                    help="Select modulation from: %s [default=%%default]"
                        % (', '.join(mods.keys()),))
    parser.add_option("","--to-file",default=None,
                        help="use file for packet contents")
    parser.add_option("","--live",action="store_true",default=False,
                       help="live play or not" )
    receive_path.add_options(parser, expert_grp)
    uhd_receiver.add_options(parser)
    transmit_path.add_options(parser, expert_grp)
    uhd_transmitter.add_options(parser)


    for mod in demods.values():
        mod.add_options(expert_grp)
    for mod in mods.values():
        mod.add_options(expert_grp)

    (options, args) = parser.parse_args ()

    
    def rx_callback(ok, payload):
        global n_rcvd, n_right,temp_message,error,Time_start, Time_end,file_count
        (pktno,) = struct.unpack('!H', payload[0:2])
        n_rcvd += 1
        if ok:
            if struct.unpack('!H',payload[2:4])==(74,):
                ACK = struct.pack('!H',pktno) +  struct.pack('!H',75) + payload[4:17]
                time.sleep(0.1)
                send_pkt(ACK)
                tb.rxpath.packet_receiver._rcvd_pktq.flush()
            n_right += 1
        else: 
            error += 1
        correct_rate = float(n_right) / float(n_rcvd) *100 
        # print "ok = %5s  pktno = %4d  n_rcvd = %4d  n_right = %4d  error = %4d correct = %.2f" % (
        #     ok, pktno, n_rcvd, n_right, error, correct_rate)
        print(payload[4:])
        ########
        datafile = open(DATA_FILE_PATH, 'a')
        datafile.write(payload[4:])
        datafile.close()
        ########
    if len(args) != 0:
        parser.print_help(sys.stderr)
        sys.exit(1)

    if options.rx_freq is None:
        sys.stderr.write("You must specify -f FREQ or --freq FREQ\n")
        parser.print_help(sys.stderr)
        sys.exit(1)
    
    # build the graph
    tb = my_top_block(mods[options.modulation],demods[options.modulation], rx_callback, options)
    tb.start_listen()
    print(tb.source._print_verbage())
    r = gr.enable_realtime_scheduling()
    if r != gr.RT_OK:
        print "Warning: Failed to enable realtime scheduling."

    tb.start()        
    tb.wait()         # wait for it to finish

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
