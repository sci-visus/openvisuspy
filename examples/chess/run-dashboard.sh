#!/usr/bin/env bash

cd /mnt/data1/nsdf/openvisuspy

source "/mnt/data1/nsdf/miniforge3/bin/activate" nsdf-env

export OPENVISUSPY_DASHBOARDS_LOG_FILENAME=/mnt/data1/nsdf/convert-workflow/nsdf-group/dashboards.log 

python -m bokeh serve ./examples/dashboards/app \
   --port 5007 \
   --use-xheaders \
   --allow-websocket-origin='nsdf01.classe.cornell.edu' \
   --dev \
   --auth-module=./examples/chess/auth.py \
   --args "/mnt/data1/nsdf/convert-workflow/nsdf-group/dashboards.json " \
   --prefer local
