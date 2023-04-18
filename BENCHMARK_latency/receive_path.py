#!/usr/bin/env python
#
# Copyright 2005-2007,2011 Free Software Foundation, Inc.
# 
# This file is part of GNU Radio
# 
# GNU Radio is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# GNU Radio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with GNU Radio; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
# 

from gnuradio import gr, gru, filter
from gnuradio import eng_notation
from gnuradio import analog
import gnuradio.gr.gr_threading as _threading
from gnuradio.digital import packet_utils
from gnuradio.digital import digital_swig as digital
import ctypes,inspect

import copy,sys,time

# /////////////////////////////////////////////////////////////////////////////
#                              receive path
# /////////////////////////////////////////////////////////////////////////////

class my_demod_pkts(gr.hier_block2):
    def __init__(self, demodulator, access_code=None, callback=None, threshold=-1):
        gr.hier_block2.__init__(self, "demod_pkts",
                                gr.io_signature(1, 1, gr.sizeof_gr_complex), 
                                gr.io_signature(0, 0, 0))

        self.callback = callback
        self._demodulator = demodulator
        if access_code is None:
            access_code = packet_utils.default_access_code
        if not packet_utils.is_1_0_string(access_code):
            raise ValueError, "Invalid access_code %r. Must be string of 1's and 0's" % (access_code,)
        self._access_code = access_code

        if threshold == -1:
            threshold = 12              # FIXME raise exception

        self._rcvd_pktq = gr.msg_queue()          # holds packets from the PHY
        self.correlator = digital.correlate_access_code_bb(access_code, threshold)

        self.framer_sink = digital.framer_sink_1(self._rcvd_pktq)
        self.connect(self, self._demodulator, self.correlator, self.framer_sink)
        self.listener = _myqueue_watcher_thread(self._rcvd_pktq, self.callback)

    def status(self):
        return self.listener.is_alive()

    def start_listen(self):
        '''Start Listen'''
        print 'listening-------------------------->'
        self.listener = _myqueue_watcher_thread(self._rcvd_pktq, self.callback)
        self.listener.start()

    def stop_listen(self):
        '''Stop listen'''
        self._async_raise(self.listener.ident, SystemExit)
        

    def _async_raise(self, tid, exctype):
        print 'Stoping>>>>>>>'
        tid = ctypes.c_long(tid)
        if not inspect.isclass(exctype):
            exctype = type(exctype)
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid,ctypes.py_object(exctype))
        if res == 0:
            raise ValueError('invalid thread ID')
        elif res != 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(tid,None)
            raise SystemError('PyThreadState_SetAsyncExc faild')

class _myqueue_watcher_thread(_threading.Thread):
    def __init__(self, rcvd_pktq, callback):
        _threading.Thread.__init__(self)
        self.setDaemon(1)
        self.rcvd_pktq = rcvd_pktq
        self.callback = callback
        self.keep_running = True

    def run(self):
        while self.keep_running:
            msg = self.rcvd_pktq.delete_head()
            ok, payload = packet_utils.unmake_packet(msg.to_string(), int(msg.arg1()))
            if self.callback:
                self.callback(ok, payload)

class receive_path(gr.hier_block2):
    def __init__(self, demod_class, rx_callback, options):
        gr.hier_block2.__init__(self, "receive_path",
                    gr.io_signature(1, 1, gr.sizeof_gr_complex),
                    gr.io_signature(0, 0, 0))
            
        options = copy.copy(options)    # make a copy so we can destructively modify

        self._verbose     = options.verbose
        self._bitrate     = options.bitrate  # desired bit rate

        self._rx_callback = rx_callback  # this callback is fired when a packet arrives
        self._demod_class = demod_class  # the demodulator_class we're using

        self._chbw_factor = options.chbw_factor # channel filter bandwidth factor

        # Get demod_kwargs
        demod_kwargs = self._demod_class.extract_kwargs_from_options(options)

        # Build the demodulator
        self.demodulator = self._demod_class(**demod_kwargs)

        # Make sure the channel BW factor is between 1 and sps/2
        # or the filter won't work.
        if(self._chbw_factor < 1.0 or self._chbw_factor > self.samples_per_symbol()/2):
            sys.stderr.write("Channel bandwidth factor ({0}) must be within the range [1.0, {1}].\n".format(self._chbw_factor, self.samples_per_symbol()/2))
            sys.exit(1)
        
        # Design filter to get actual channel we want
        sw_decim = 1
        chan_coeffs = filter.firdes.low_pass(1.0,                  # gain
                                             sw_decim * self.samples_per_symbol(), # sampling rate
                                             self._chbw_factor,    # midpoint of trans. band
                                             0.5,                  # width of trans. band
                                             filter.firdes.WIN_HANN)   # filter type
        self.channel_filter = filter.fft_filter_ccc(sw_decim, chan_coeffs)
        
        # receiver
        self.packet_receiver = \
            my_demod_pkts(self.demodulator,
                               access_code=None,
                               callback=self._rx_callback,
                               threshold=-1)

        # Carrier Sensing Blocks
        alpha = 0.001
        thresh = 30   # in dB, will have to adjust
        self.probe = analog.probe_avg_mag_sqrd_c(thresh,alpha)

        # Display some information about the setup
        if self._verbose:
            self._print_verbage()

	    # connect block input to channel filter
        self.connect(self, self.channel_filter)

        # connect the channel input filter to the carrier power detector
        self.connect(self.channel_filter, self.probe)

        # connect channel filter to the packet receiver
        self.connect(self.channel_filter, self.packet_receiver)

    def bitrate(self):
        return self._bitrate

    def samples_per_symbol(self):
        return self.demodulator._samples_per_symbol

    def differential(self):
        return self.demodulator._differential

    def carrier_sensed(self):
        """
        Return True if we think carrier is present.
        """
        #return self.probe.level() > X
        return self.probe.unmuted()

    def carrier_threshold(self):
        """
        Return current setting in dB.
        """
        return self.probe.threshold()

    def set_carrier_threshold(self, threshold_in_db):
        """
        Set carrier threshold.

        Args:
            threshold_in_db: set detection threshold (float (dB))
        """
        self.probe.set_threshold(threshold_in_db)

    @staticmethod
    def add_options(normal, expert):
        """
        Adds receiver-specific options to the Options Parser
        """
        if not normal.has_option("--bitrate"):
            normal.add_option("-r", "--bitrate", type="eng_float", default=100e3,
                              help="specify bitrate [default=%default].")
        normal.add_option("-v", "--verbose", action="store_true", default=False)
        expert.add_option("-S", "--samples-per-symbol", type="float", default=2,
                          help="set samples/symbol [default=%default]")
        expert.add_option("", "--log", action="store_true", default=False,
                          help="Log all parts of flow graph to files (CAUTION: lots of data)")
        expert.add_option("", "--chbw-factor", type="float", default=1.0,
                          help="Channel bandwidth = chbw_factor x signal bandwidth [default=%default]")

    def _print_verbage(self):
        """
        Prints information about the receive path
        """
        print "\nReceive Path:"
        print "modulation:      %s"    % (self._demod_class.__name__)
        print "bitrate:         %sb/s" % (eng_notation.num_to_str(self._bitrate))
        print "samples/symbol:  %.4f"    % (self.samples_per_symbol())
        print "Differential:    %s"    % (self.differential())
