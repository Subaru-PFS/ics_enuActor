#!/bin/bash
echo "setup ..."
source ~/mhsls/products/eups/1.2.33/bin/setups.sh
setup -v ics_mhs_root
echo "starting tron..."
tron start
hubclient &
echo "launching enuActor"
python ~/mhsls/devel/enuActor/python/enuActor/main.py
#exit 1
