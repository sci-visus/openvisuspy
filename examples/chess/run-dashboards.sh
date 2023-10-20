#!/usr/bin/env bash

# do it inside a screen so you can debug `screen -S run-dashboards`

cd /mnt/data1/nsdf/openvisuspy

source ./setup.sh

# we need to remove the dev
python -m bokeh serve examples/dashboards/app \
   --port 5007 \
   --use-xheaders \
   --allow-websocket-origin='nsdf01.classe.cornell.edu' \
   --dev  \
   --auth-module=./examples/chess/chess_auth.py \
   --args "/var/www/html/${NSDF_CONVERT_GROUP}.json" \
   --prefer local

# https://nsdf01.classe.cornell.edu/app