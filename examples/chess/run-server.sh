#!/bin/bash

source /nfs/chess/nsdf01/openvisus/.mod_visus.identity.sh
sudo /usr/bin/systemctl restart httpd
curl --user "$MODVISUS_USERNAME:$MODVISUS_PASSWORD" "https://nsdf01.classe.cornell.edu/mod_visus?action=list"