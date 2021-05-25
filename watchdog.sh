#!/bin/bash

while true
do
        pid=$(ps aux | grep grafanaUPLOADER_dotenv.py);        
        if [ -z "$pid" ];
        then
                python3 grafanaUPLOADER_dotenv.py;
        else
                sleep $1;
        fi
done
