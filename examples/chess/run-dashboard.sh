#!/usr/bin/env bash

cd /mnt/data1/nsdf/openvisuspy

source "/mnt/data1/nsdf/miniforge3/bin/activate" nsdf-env

export NSDF_GROUP=nsdf-group
export NSDF_CONVERT_DIR=/mnt/data1/nsdf/convert-workflow/${NSDF_GROUP}
export BOKEH_PORT=5007
export OPENVISUSPY_DASHBOARDS_LOG_FILENAME=${NSDF_CONVERT_DIR}/dashboards.log 

python -m bokeh serve ./examples/dashboards/app \
   --port ${BOKEH_PORT} \
   --use-xheaders \
   --allow-websocket-origin='nsdf01.classe.cornell.edu' \
   --dev \
   --auth-module=./examples/chess/auth.py \
   --args "${NSDF_CONVERT_DIR}/dashboards.json " \
   --prefer local


