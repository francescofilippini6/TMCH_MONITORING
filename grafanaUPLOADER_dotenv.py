#!/usr/bin/env python                                                                                                                                                                                                                                               
# coding=utf-8                                                                                                                                                                                                                                                      
# vim: ts=4 sw=4 et                                                                                                                                                                                                                                                 
# Original Author: Alba Domi - COPYRIGHT 2018                                                                                                                                                                                                                       
# Modified by T. Chiarusi 2018, 2019/04/24 Francescos                                                                                                                                                                                                               
# Compatible with KM3PIPE 9 beta                                                                                                                                                                                                                                    

import signal
import sys
import subprocess

import collections
from collections import defaultdict
import io
import os
import time
import km3pipe as kp
import numpy as np
from km3pipe.io.daq import TMCHData
from km3pipe import Module
import pandas as pd
import km3db as db
#from km3pipe.core import Pump                                                                                                                                                                                                                                      
from datetime import datetime
#from datetime import datetime as dt                                                                                                                                                                                                                                
from dotenv import load_dotenv

log = kp.logger.get_logger("udpAnalyser")

#import logging                                                                                                                                                                                                                                                     
#db = kp.db.DBManager()                                                                                                                                                                                                                                             
#det_id = 29                                                                                                                                                                                                                                                        

UDP_RATE_PER_DOM = 10  # Hz                                                                                                                                                                                                                                         
LIMIT_TIME_SYNC  = 60    #3701 # .5  # s   value tuned after several trials (3700 trigger the warning printing)                                                                                                                                                     
TIME_OFFSET = 0 # 32.0481 # s                                                                                                                                                                                                                                       
#added_second = datetime.timedelta(0,1)                                                                                                                                                                                                                             
#logging.basicConfig(filename='prova.log',filemode='w',force=True)                                                                                                                                                                                                  

class UDPAnalyser(Module):

    def configure(self):

      # self.detector = self.require("detector")                                                                                                                                                                                                                    
        self.detector_oid = 4 #db.detectors[db.detectors.SERIALNUMBER == det_id].OID.iloc[0]                                                                                                                                                                        

        self.interval = 10  # 10 seconds                                                                                                                                                                                                                            
        self.run_id = defaultdict(int)
        self.timestamp = defaultdict(int)
        self.udp_counts = defaultdict(int)
        self.total_number_udps = defaultdict(int)
        self.data_time = defaultdict(int)
        self.start_of_run_dom = defaultdict(int)
        self.start_of_run_machine = defaultdict(int) #time of the machine when 1st packet arrives --> corresponds to start_of_run_dom, but with the machine time and not with data time                                                                             
        self.end_of_run_dom = defaultdict(int)
        self.end_of_run_machine = defaultdict(int)
        self.run_duration_dom = defaultdict(int)
        self.time = defaultdict(int)
        self.copy_time = defaultdict(int)
        self.time_of_previous_check = defaultdict(int)
        self.first_packet = defaultdict(int)
        self.packet_machine_time = defaultdict(int)
        self.dt_packets = defaultdict(int)
        self.ratio = defaultdict(int)
        self.loss_ratio = defaultdict(int)
        self.timedifference = defaultdict(int)
        self.n_expected_packets = defaultdict(int)
        self.machine_expected = defaultdict(int)
        self.filecounter = 0
        self.dt = defaultdict(int)
        self.datatag = defaultdict(int)
        

        self.total_missing_udps = defaultdict(int) #total number of missing packets as counted by the 100ms check function
        self.clock_reset_counter = defaultdict(int)
               
        #self.filecounter = 0
        
        self.filename = ""
        self.time_run_change = 0
        
        detector=os.getenv('DETECTOR')
        #self.clbmap = db.CLBMap("D_BCI0004")
        self.clbmap = db.CLBMap(detector)
        self.Dom_id_name = 0

        self.testdf=pd.DataFrame(columns=["DU","det_id","run","source","machine_time","packet_time","delay","check100ms","loss_ratio_datatime","loss_ratio_machinetime","total_udp_packets_arrived","expected_from_datatime","expected_from_machinetime","clock_reset_counter"])

    def process(self, blob):
        arrival_time = blob["CHPrefix"].timestamp
        tmch_data = kp.io.daq.TMCHData(io.BytesIO(blob['CHData']))
        dom_id = tmch_data.dom_id

        #--------------------------------------------base-------------------------------                                                                                                                                                                             
        if dom_id ==808976266:
            return blob

        if dom_id == 808982053:
            return blob
        #------------------------------------------------------------------------------                                                                                                                                                                      

        doms = self.clbmap.dom_ids[dom_id]
        self.Dom_id_name = doms.floor

        if not self.run_id[dom_id]: #fill run_id dictionary with run values;@ 1st timeslice per DOM of the run it enters here (run_id = 0) then id is associated and never enters here until run change                                                             
            self.run_id[dom_id] = tmch_data.run

        if tmch_data.run != self.run_id[dom_id]:
            self.reset_data_end_of_run(dom_id)
            self.run_id[dom_id] = tmch_data.run
            self.start_of_run_dom[dom_id] = (tmch_data.utc_seconds*1e9 + tmch_data.nanoseconds)*1e-6
            self.start_of_run_machine[dom_id] = round(time.time(),1)
            print('NEW RUN',self.run_id[dom_id],' (1st detected packet) for DOM',self.Dom_id_name,' START AT ',self.start_of_run_dom[dom_id], "ms")
            print("MACHINE START TIME = ",self.start_of_run_machine[dom_id])


        if not self.start_of_run_dom[dom_id]:  #for the 1st run, initialize the start time in seconds for each DOM. For subsequent run this is done at run change                                                                                                   
            self.start_of_run_dom[dom_id] = (tmch_data.utc_seconds*1e9 + tmch_data.nanoseconds)*1e-6  #NOTE: 'start of run' actually means the time of 1st analyzed packet. If this program is launched when run is already started, start_of_run is NOT the acual start of run time                                                                                                                                                                                                                                                   
            
            self.start_of_run_machine[dom_id] = round(time.time(),1) #need this for the 1st check interval = [ machine time at start, machine time at start + self.interval ]                                                                                    
             #if self.Dom_id_name==2: #to select a specific dom to print                                                                                                                                                                               

            print('NEW RUN',self.run_id[dom_id],' (1st detected packet) for DOM',self.Dom_id_name,' START AT ',self.start_of_run_dom[dom_id], "ms")
            print("MACHINE START TIME = ",self.start_of_run_machine[dom_id])

        #if self.filename == "":
        #    self.filename = "/home/km3net/analysis/grafanarepo/test_grafana_RUN" + str(tmch_data.run)+ ".csv"
        #    self.write_header(tmch_data.run)
            print(self.filename)

        if not self.timestamp[dom_id]: #enter here at first round and assign value to timestamp[dom_id] and udp_counts[dom_id]; timestamp is increased by 10 s, it's the interval time
            self.reset_data(dom_id)
        #----------------------------------------------------------------                                                                                                                                                                                          
 
        self.total_number_udps[dom_id] += 1 #used to count the total number of udp packets, never reset                                                                                                                                                             
       # self.udp_counts[dom_id] += 1 #counts the number of udp packets since it is incremented every time a packet is detected; this is reset to 0 every self.interval seconds, used to check packet loss in the interval                                          

        #----------------------------------------------------------------                                                                                                                                                                                           
        total_time = (tmch_data.utc_seconds*1e9 + tmch_data.nanoseconds)*1e-6  # ms                                                                                                                                                                                 

        self.packet_machine_time[dom_id] = round(time.time(),3)
        self.time[dom_id] = total_time
        
        self.dt[dom_id] = round(self.packet_machine_time[dom_id] - self.time[dom_id]*1e-3,1)

        #----------------------------------------------------------------                                                                                                                                                                                           
        self.check_packet_loss(dom_id)
        self.check_100ms_sync(dom_id)
        self.check_packets_vs_machine(dom_id)
     
        self.copy_time[dom_id] = total_time

        if self.first_packet[dom_id] == 0:
            self.first_packet[dom_id] = 1

        #----------------------------------------------------------------                                                                                                                                                                                           
        #keep ATTENTION to the difference between data_time(s) and times(ms)                                                                                                                                                                                        
        self.data_time[dom_id] = (tmch_data.utc_seconds*1e9 + tmch_data.nanoseconds)*1e-9

        #----------------------------------------------------------------                                                                                                                                                                                           
        #function execution > check done for each dom for each TS                                                                                                                                                                                                   
        self.check_data_machine_time(arrival_time,dom_id)


        #datetime.fromtimestamp(self.packet_machine_time[dom_id]).strftime('%Y-%m-%d %H:%M:%S.%f')
        #datetime.fromtimestamp(self.time[dom_id]*1e-3).strftime('%Y-%m-%d %H:%M:%S.%f')

        
        self.testdf.loc[len(self.testdf)+1] = [1,self.detector_oid,self.run_id[dom_id],self.Dom_id_name,self.packet_machine_time[dom_id],self.time[dom_id],self.dt[dom_id],self.dt_packets[dom_id],self.loss_ratio[dom_id],self.ratio[dom_id],self.total_number_udps[dom_id],self.n_expected_packets[dom_id],self.machine_expected[dom_id],self.clock_reset_counter[dom_id]]

        if self.Dom_id_name==2:
            #print(self.return_timedelta(dom_id))
            if self.return_timedelta(dom_id)>self.interval:
                self.filename = os.getcwd()+'/grafanarepo/test_grafana_RUN'+str(self.run_id[dom_id])+"_"+ str(self.filecounter)+ ".csv"
                print('writing dataframe ',self.filename)                
                #self.write_header(tmch_data.run)
                self.write_data_into_file()
                self.filecounter+=1
                self.testdf = self.testdf.iloc[0:0]
                self.reset_data(dom_id)
        #----------------------------------------------------------------                                                                                                                                                                                           
        return blob

    #----------------------------------------------------------------                                                                                                                                                                                                
    #making the difference of system time.time(s) and timestamp; timestamp changes every self.interval s                                                                                                                                                            
    def return_timedelta(self, dom_id):
        return time.time() - self.timestamp[dom_id]
    #----------------------------------------------------------------                                                                                                                                                                                               
    def reset_data(self, dom_id): #called at the end of every self.interval                                                                                                                                                                                         
        self.udp_counts[dom_id] = 0 #reset to 0 every self.interval                                                                                                                                                                                                 
        self.timestamp[dom_id] = time.time()
        
    #----------------------------------------------------------------                                                                                                                                                                                               
    def write_header(self, run_id):
        """                                                                                                                                                                                                                                                         
        This function is called once (if the outputfile doesn't exist).                                                                                                                                                                                             
        """
        if not os.path.exists(self.filename):
            out = open(self.filename, "w+")
            out.write("tag\tdet_id\trun\tsource")
            out.write("\tmachine_time\tpacket_time\tdelay\tcheck100ms\ttransmission_ratio_datatime\ttransmission_ratio_machinetime\total_udp_packets_arrived\texpected_from_datatime\texpected_from_machinetime\tclock_reset_counter")
            out.write("\n")
            out.close()
    #----------------------------------------------------------------                                                                                                                                                                                               
    def check_packet_loss(self, dom_id, end_run=0):
        """                                                                                                                                                                                                                                                         
        Check if the effective number of packets received by each dom                                                                                                                                                                                               
        is different from what expected.                                                                                                                                                                                                                            
        """
        if  self.first_packet[dom_id] == 0:
            print("Inside check_packet_loss for DOM",self.Dom_id_name, ", 1st packet.")

        else:
            self.dt_packets[dom_id] = self.time[dom_id] - self.copy_time[dom_id]
            
            self.n_expected_packets[dom_id] = ((self.time[dom_id]-self.start_of_run_dom[dom_id])/100)+1  #expected number of packets from start time. +1 is for adding 1st starting packet   
            observed_packets = self.total_number_udps[dom_id]
            self.loss_ratio[dom_id] = observed_packets / self.n_expected_packets[dom_id]
            #if self.n_expected_packets[dom_id] != observed_packets:
                #log.warning("PACKET LOSS for DOM {0} = {1} missing packets (this is cumulative)".format(self.Dom_id_name,self.n_expected_packets[dom_id]-observed_packets))
                #print('PACKET LOSS ratio for DOM {0} --> expected {1}, got {2}, ratio is {3}'.format(self.Dom_id_name,self.n_expected_packets[dom_id],observed_packets,self.loss_ratio[dom_id]))              
                #print("PACKET LOSS for DOM {0} = {1} missing packets (this is cumulative)".format(self.Dom_id_name,self.n_expected_packets[dom_id]-observed_packets))
                
    #----------------------------------------------------------------                                                                                                                                                                                               
    def check_100ms_sync(self, dom_id):
        """                                                                                                                                                                                                                                                         
        Check if there are some consecutive udp packets                                                                                                                                                                                                             
        with delta_t != 100 ms.                                                                                                                                                                                                                                     
        """
        if  self.first_packet[dom_id] == 0:
            print("Inside check_100_ms for DOM",self.Dom_id_name,", 1st packet")

        else:
            self.dt_packets[dom_id] = round(self.time[dom_id],3) - round(self.copy_time[dom_id],3)
            if self.dt_packets[dom_id] < -946080000:
                self.clock_reset_counter[dom_id]+=1
                log.error("!Found a clock reset for DOM {0}!".format(self.Dom_id_name))
           # print("dt between packets for DOM",self.Dom_id_name," = ",self.dt_packets[dom_id])
            if self.dt_packets[dom_id] != 100:
                self.total_missing_udps[dom_id]+= (self.dt_packets[dom_id]-100)/100
                log.error("100ms Error! For DOM {0} = {1} missing packets calculated as consecutive ({2} - {3}) packets check".format(self.Dom_id_name,(self.dt_packets[dom_id]-100)/100,self.time[dom_id],self.copy_time[dom_id]))
                #print("100ms Error! For DOM {0} = {1} missing packets calculated as consecutive ({2} - {3}) packets check".format(self.Dom_id_name,self.total_missing_udps[dom_id],self.time[dom_id],self.copy_time[dom_id]))
    #----------------------------------------------------------------                                                                                                                                                                                               
    def check_packets_vs_machine(self, dom_id):
        """                                                                                                                                                                 
        Check packets expected from data elapsed time vs
        expected number considering machine elapsed time                                                                                                                                                                                                            
        """
        if  self.first_packet[dom_id] == 0:
            print("Inside check_packet_vs_machine for DOM",self.Dom_id_name,", 1st packet")
        else:
            observed = self.total_number_udps[dom_id]
            self.machine_expected[dom_id] = (round((self.packet_machine_time[dom_id]- self.start_of_run_machine[dom_id]),2)*10)+1
            self.ratio[dom_id] = observed/self.machine_expected[dom_id]
            
    #----------------------------------------------------------------                                                                                                                                                                                               
    def check_data_machine_time(self, arrival_time, dom_id): #arrival time on machine vs time of data                                                                                                                                                               
        """                                                                                                                                                                                                                                                         
        Check if the timestamp of each udp packet and                                                                                                                                                                                                               
        its arrival time on the machine is > 1 minute.                                                                                                                                                                                                              
        """
        self.timedifference[dom_id] = arrival_time - self.data_time[dom_id]+TIME_OFFSET
        #if self.Dom_id_name==1:
        #    print('check clock reset for DOM1, dt = ',self.timedifference[dom_id])
        if abs(self.timedifference[dom_id]) > 946080000: #if delay is larger than 30 years                                                                                                                                                                          
            log.error('!CLOCK RESET!  For DOM {2}, packet time = {0} VS arrival time on machine = {1}'.format(self.data_time[dom_id], arrival_time, self.Dom_id_name))
        elif abs(self.timedifference[dom_id]) > LIMIT_TIME_SYNC:
            self.total_error_data_machine_time[dom_id] += 1
            log.error("At {4} for RUN {0} : Packet time = {5} and arrival on machine time {3} not synchronized for DOM {1}: difference is datetime = {2} s "
                      .format(self.run_id[dom_id], self.Dom_id_name, self.timedifference[dom_id], arrival_time,datetime.now(),self.data_time[dom_id]))
    #----------------------------------------------------------------                                                                                                                                                                                               
    
    def write_data_into_file(self):
        #out = open(self.filename, "a+")
        #out.write("{0}\t{1}\t{2}".format(self.detector_oid,self.run_id[dom_id],self.Dom_id_name))
        #out.write("\t{0}\t{1}\t{2}\t{3}\t{4}\t{5}\t{6}\t{7}\t{8}".format(self.packet_machine_time[dom_id],self.time[dom_id]*1e-3,round(self.packet_machine_time[dom_id]-self.time[dom_id]*1e-3,1),self.dt_packets[dom_id],self.loss_ratio[dom_id],self.ratio[dom_id],self.total_number_udps[dom_id],self.n_expected_packets[dom_id],self.machine_expected[dom_id]))
        self.testdf.to_csv(self.filename, mode='a',index=False)
        #out.write("\n")
        #out.close()
        
    #----------------------------------------------------------------                                                                                                                                                                                               
    def reset_data_end_of_run(self, dom_id): #called only at the end of the run                                                                                                                                                                                     
        self.run_id[dom_id] = 0
        self.total_number_udps[dom_id] = 0
        self.total_missing_udps[dom_id] = 0
        self.udp_counts[dom_id] = 0
        self.timestamp[dom_id] = time.time()
        self.first_packet[dom_id] = 0 
        self.start_of_run_dom[dom_id] = 0
        self.start_of_run_machine[dom_id] = 0
        self.filecounter = 0
        self.dt_packets[dom_id] = 0
        self.clock_reset_counter[dom_id] = 0
    #----------------------------------------------------------------                                                                                                                                                                                               
def signal_handler(sig, frame):
        print('You pressed Ctrl+\!')
        print("\nMON quitting time: {0} - {1}\n".format(datetime.timestamp(datetime.now()),datetime.now()));
        sys.exit(0)
    #----------------------------------------------------------------                                                                                                                                                                                               

def main():
    #detector = kp.hardware.Detector(det_id = 29)                                                                                                                                                                                                                   
    load_dotenv()
    host_ip = os.getenv('HOST_IP')
    signal.signal(signal.SIGQUIT, signal_handler)
    print("\n---- Tom's modified udpAnalyser v1.0 ----\n")
    print("\nMON starting time: {0} - {1}".format(datetime.timestamp(datetime.now()),datetime.now()));
    print("\npress Ctrl+\ (SIGQUIT)for quitting gently and getting the stopping time.")
    pipe = kp.Pipeline(timeit=True)
    pipe.attach(kp.io.CHPump, host=host_ip,
                              port=9999,
                              tags='IO_DU1',
                              timeout=60*20,
                              max_queue=10000000000)
    #    pipe.attach(UDPAnalyser, detector=detector)                                                                                                                                                                                                         
    pipe.attach(UDPAnalyser)

    pipe.drain()

if __name__ == "__main__":
    main()
