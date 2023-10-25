#!/usr/bin/env bash

cd /mnt/data1/nsdf/openvisuspy

source "/mnt/data1/nsdf/miniforge3/bin/activate" nsdf-env

OPENVISUSPY_DASHBOARDS_LOG_FILENAME=/mnt/data1/nsdf-convert-workflow/test-group-bitmask/dashboards.log python -m bokeh serve examples/dashboards/app \
   --port 5007 \
   --use-xheaders \
   --allow-websocket-origin='nsdf01.classe.cornell.edu' \
   --dev \
   --auth-module=./examples/chess/auth.py \
   --args "/var/www/html/test-group-bitmask.json " \
   --prefer local



