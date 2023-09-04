#!/bin/bash

sudo mv /home/pi/HardwareHistory/HardwareHistory.service /etc/systemd/system/ && sudo systemctl daemon-reload
python3 -m pip install requests yagmail --no-cache-dir
chmod +x -R /home/pi/HardwareHistory/*