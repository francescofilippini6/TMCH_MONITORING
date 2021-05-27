from dotenv import load_dotenv
import os
import subprocess
import shlex
import time


load_dotenv()

os.mkdir('/grafanarepo')
du=os.environ['DETECTION_UNITS']
duname=du.split(',')
for i in duname:
    dua='IO_DU'+str(i)
    subprocess.call(shlex.split(f"./GrafanaScript_azione.sh {dua}"))

while True:
    time.sleep(100)
