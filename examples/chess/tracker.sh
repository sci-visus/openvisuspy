#!/bin/bash
cd /mnt/data1/nsdf/openvisuspy

source "/mnt/data1/nsdf/miniforge3/bin/activate" nsdf-env

# need kerberos ticket for acchessing CHESS metadata
kinit -k -t ~/krb5_keytab -c ~/krb5_ccache gscorzelli

# pass all arguments
python ./examples/chess/tracker.py $@

