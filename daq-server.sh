#!/bin/bash

hostarea="~/sw_0717/" #Check this before running
export LD_LIBRARY_PATH=/opt/cactus/lib:$LD_LIBRARY_PATH # You can add this to ~/.bashrc if needed
cd $hostarea"hexactrl-sw/build"
./daq-server -f /opt/cms-hgcal-firmware/hgc-test-systems/active/uHAL_xml/connections.xml
