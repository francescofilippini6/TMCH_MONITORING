# TMCH_monitoring

This python program monitors the UDP packet data-stream from the  KM3NeT detectors (DOMs, Bases etc.).
Is an evolution of  Alba Domi's  origina project https://wiki.km3net.de/index.php/Monitoring_UDP_Analysis.
By F. Filippini and F. Benfenati

mailto: francesco.filippini@bo.infn.it
mailto: francesco.benfenati@bo.infn.it

Prerequisites: a recent version of docker and docker-compose (docker-compose can be installed through git: https://docs.docker.com/compose/install/)

For the execution of the code, follow these steps:


1. `mkdir NewDirectory`

2. `docker build -f km3docker -t km3 .`

3. `docker-compose -f dockercompose1.yml up`

Then on the browser connect to: 

- localhost:3000 

Configure Grafana (user: admin, pwd: admin -> set your password)

From the home page select:

- "Add your first datasource";
- Select Influxdb; 
- Url: http://influxdb:8086, Access: Server (Default), Enable Basic auth (Details-> user:km3net, pwd:p*******);
- Database: monitoring.
Save & Test

Import dashboard uploading JSON files.
