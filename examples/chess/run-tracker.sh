#!/bin/bash
cd /mnt/data1/nsdf/openvisuspy
source ./setup.sh
python ./examples/chess/main.py run-tracker "${NSDF_CONVERT_JSON_GLOB_PATTERN}" 
