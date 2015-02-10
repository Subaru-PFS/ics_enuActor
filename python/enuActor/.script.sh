#!/bin/bash
echo "setup ..."
source ~/mhs/products/eups/default/bin/setups.sh
setup -v tron_tron
echo "starting tron..."
tron start
echo "launching enuActor"
stageManager enu start
setup -v ics_enuActor
setup -v tron_actorcore
hubclient &
#exit 1
