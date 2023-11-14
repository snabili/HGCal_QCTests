#!/bin/bash

hostarea="/home/HGCAL_dev/sw_0717/" #Check this before running
cd $hostarea"hexactrl-sw/zmq_i2c/gbt-sca-sw/"
source ./env.sh
cd ../
python3 zmq_server.py
