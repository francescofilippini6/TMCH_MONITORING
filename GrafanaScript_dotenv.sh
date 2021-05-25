#!/bin/bash

TARGET=/grafanarepo
mkdir $TARGET
#PROCESSED=~/processed/prog1 & prog2 && fg
python3 grafanaUPLOADER_dotenv.py &
./watchdog.sh &

inotifywait --monitor -r -e close_write --format "%f" $TARGET | while read FILENAME
do
    echo Copied $FILENAME 
    python3 csv-to-influxdb_UTC_RP.py --dbname monitoring --create --user km3net --password pyrosoma --server influxdb:8086 --input $TARGET/$FILENAME --tagcolumns source,DU --fieldcolumns delay,check100ms,loss_ratio_machinetime,expected_from_datatime,expected_from_machinetime,run,clock_reset_counter,loss_ratio_datatime,total_udp_packets_arrived -tc machine_time -tf "%Y-%m-%d %H:%M:%S.%f" --timezone Europe/Rome
    rm -f $TARGET/$FILENAME
done 


