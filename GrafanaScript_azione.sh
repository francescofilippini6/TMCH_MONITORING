#!/bin/bash
#mkdir /grafanarepo
DU=$1
TARGET=$DU
mkdir /grafanarepo/$TARGET

python3 grafanaUPLOADER_dotenv.py $DU &
#./watchdog.sh $DU &
inotifywait --monitor -r -e close_write --format "%f" grafanarepo/$TARGET | while read FILENAME
do
    echo Copied $FILENAME 
    python3 csv-to-influxdb_UTC_RP.py --dbname monitoring --create --user km3net --password pyrosoma --server influxdb:8086 --input /grafanarepo/$TARGET/$FILENAME --tagcolumns source,DU --fieldcolumns delay,check100ms,loss_ratio_machinetime,expected_from_datatime,expected_from_machinetime,run,clock_reset_counter,loss_ratio_datatime,total_udp_packets_arrived -tc machine_time -tf "%Y-%m-%d %H:%M:%S.%f" --timezone Europe/Rome
    rm -f $TARGET/$FILENAME
done &


