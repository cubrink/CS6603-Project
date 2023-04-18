#python benchmark_transmitter.py -a addr=192.168.20.2 --tx-freq=2.45e9 -m gmsk -r 500e3 --from-file='/home/yue/Desktop/sample.png'


from gnuradio import gr, gru
from gnuradio import blocks
from gnuradio import eng_notation
from gnuradio.eng_option import eng_option
from optparse import OptionParser
from gnuradio import digital

import random, time, struct, sys

# from current dir (GNURadio->digital->narrowband)
from transmit_path import transmit_path
from uhd_interface import uhd_transmitter

global tb

class my_top_block(gr.top_block):
    def __init__(self, modulator, options):
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
        elif(options.from_file is not None):
            sys.stderr.write("reading samples from '%s'.\n\n"%(options.from_file))
            self.source=blocks.file_source(gr.sizeof_gr_complex,options.from_file)
        else:
            sys.stderr.write("No source defined,pulling samples from null source. \n\n")
            self.source=blocks.null_source(gr.sizeof_gr_complex)
        self.txpath=transmit_path(modulator,options)
        self.connect(self.txpath,self.sink)  


# /////////////////////////////////////////////////////////////////////////////
#                                   main
# /////////////////////////////////////////////////////////////////////////////

def main():
    global tb

    def send_pkt(payload='', eof=False):
        return tb.txpath.send_pkt(payload, eof)

    mods=digital.modulation_utils.type_1_mods()

    parser = OptionParser(option_class=eng_option, conflict_handler="resolve")
    expert_grp = parser.add_option_group("Expert")

    parser.add_option("-m", "--modulation", type="choice", choices=mods.keys(),
                      default='gmsk',
                      help="Select modulation from: %s [default=%%default]"
                            % (', '.join(mods.keys()),))

    parser.add_option("-s", "--size", type="eng_float", default=4000,
                      help="set packet size [default=%default]")
    parser.add_option("-M", "--megabytes", type="eng_float", default=1.2,
                      help="set megabytes to transmit [default=%default]")
    parser.add_option("","--discontinuous", action="store_true", default=False,
                      help="enable discontinous transmission (bursts of 5 packets)")
    parser.add_option("","--from-file", default=None,
                      help="use file for packet contents")
    transmit_path.add_options(parser, expert_grp)
    uhd_transmitter.add_options(parser)

    for mod in mods.values():
        mod.add_options(expert_grp)

    (options, args) = parser.parse_args ()

    if len(args) != 0:
        parser.print_help()
        sys.exit(1)

    if options.tx_freq is None:
         sys.stderr.write("You must specify -f FREQ or --freq FREQ\n")
         parser.print_help(sys.stderr)
         sys.exit(1)

    if options.from_file is not None:
        source_file = open(options.from_file, 'r')
        

    # build the graph
    tb = my_top_block(mods[options.modulation], options)
    r = gr.enable_realtime_scheduling()
    if r != gr.RT_OK:
        print "Warning: failed to enable realtime scheduling"
    tb.start()                       # start flow graph

    # generate and send packets
    nbytes = int(1e6 * options.megabytes)
    n = 0
    pktno = 0
    pkt_size = int(options.size)
    print '\n'
    while n < nbytes:
        if options.from_file is None:
            data = (pkt_size - 2) * chr(pktno & 0xff)
        else:
            data = source_file.read(pkt_size - 2)
            if data == '':
                break;
        payload = struct.pack('!H', pktno) + data
        send_pkt(payload)
        n += len(payload)
        sys.stderr.write('.')
        if options.discontinuous and pktno % 5 == 4:
            time.sleep(1)
        pktno += 1

    print '\n'
    print 'billibillib: pktno = ', pktno-1, 'n = ', n
    #must add below 'raw_input' to delay eof!!! otherwise, Thread tp may have not take out all the messages in the queue!
    raw_input('billibillib : press any key to continue')       
    send_pkt(eof=True)
    tb.wait()                       # wait for it to finish

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass