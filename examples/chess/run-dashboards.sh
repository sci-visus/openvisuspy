#!/usr/bin/env bash

cd /mnt/data1/nsdf/openvisuspy

source "/mnt/data1/nsdf/miniforge3/bin/activate" nsdf-env

function RunDashboards() {
   OPENVISUSPY_DASHBOARDS_LOG_FILENAME=${3} python -m bokeh serve examples/dashboards/app \
      --port ${1} \
      --use-xheaders \
      --allow-websocket-origin='nsdf01.classe.cornell.edu' \
      --dev \
      --auth-module=./examples/chess/auth.py \
      --args "${2}" \
      --prefer local
}

RunDashboards 5007 /var/www/html/test-group-bitmask.json /mnt/data1/nsdf-convert-workflow/test-group-bitmask/dashboards.log



