#!/usr/bin/env python
# Filename: ligiermirror.py
# Author: Tamas Gal <tgal@km3net.de>
# vim: ts=4 sw=4 et
"""
Subscribes to given tag(s) and sends them to another Ligier.

Usage:
    ligiermirror [options]
    ligiermirror (-h | --help)

Options:
    -q PORT         Target port [default: 5553].
    -m TAGS         Comma separated message tags [default: IO_EVT, IO_SUM].
    -s QUEUE        Maximum queue size for messages [default: 20000].
    -x TIMEOUT      Connection timeout in seconds [default: 604800].
    -d DEBUG_LEVEL  Debug level (DEBUG, INFO, WARNING, ...) [default: WARNING].
    -h --help       Show this screen.

"""
import socket
import io
import os
import km3pipe as kp
import km3db as db
from dotenv import load_dotenv
log = kp.logger.get_logger("ligiermirror")


class LigierSender(kp.Module):
    """Forwards a message to another ligier"""

    def configure(self):
        self.orderedDOM = [806472270,806451575,808981684,808447031,808985194,808971330,808982053,806451239,808952022,808967370,808489098,808976266,809537142,808984748,808982228,808980464,808976292,809544159,808996919]
        self.target_ip = self.get("target_ip", default="127.0.0.1")
        self.port = self.get("port", default=5553)
        s = socket.socket()
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.client = s.connect((self.target_ip, self.port))
        self.socket = s
        detector=os.getenv('DETECTOR')
        self.clbmap = db.CLBMap(detector)


    def process(self, blob):
        tmch_data = kp.io.daq.TMCHData(io.BytesIO(blob['CHData']))
        dom_id = tmch_data.dom_id
        #--------------------------------------------base-------------------------------                                                                                                                                                                       
        if dom_id ==808976266:
            return blob
        #------------------------------------------------------------------------------                                                                                                                                                                             
        dom=self.clbmap.dom_ids[dom_id]
        #print("DU:",dom.du)
        #print("Floor:",dom.floor)
        dutag="IO_DU"+str(dom.du)
        client2 = kp.controlhost.Client(self.target_ip,self.port)
        client2.put_message(dutag, blob["CHData"]) 

        


        return blob
        
    def finish(self):
        self.socket.close()


def main():
    """The main script"""
    from docopt import docopt
    load_dotenv()
    args = docopt(__doc__, version=kp.version)

    kp.logger.set_level("km3pipe", args["-d"])
    
    daq_ligier=os.getenv('IP_LIGIER_DAQ')
    ligier_port=os.getenv('LIGIER_DAQ_PORT')
    host_ip=os.getenv('HOST_IP')

    pipe = kp.Pipeline()
    pipe.attach(
        #kp.io.ch.CHPump,
        kp.io.CHPump,
        #host=args["SOURCE_IP"],
        host=daq_ligier,
        port=int(ligier_port),
        tags=args["-m"],
        timeout=int(args["-x"]),
        max_queue=int(args["-s"]),
        show_statistics=True,
    )
    pipe.attach(LigierSender, target_ip=host_ip, port=int(args["-q"]))
    pipe.drain()


if __name__ == "__main__":
    main()
