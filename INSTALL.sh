#!/bin/bash

sudo mv /home/pi/HardwareHistory/HardwareHistory.service /etc/systemd/system/ && sudo systemctl daemon-reload
python3 -m pip install -r /home/pi/HardwareHistory/requirements.txt --no-cache-dir
chmod +x -R /home/pi/HardwareHistory/*