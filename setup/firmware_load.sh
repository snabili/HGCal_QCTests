#!/bin/bash

sudo fw-loader load tileboard-tester-v2p0 #Name of the current rpm file
sudo chmod og+rw /dev/gpiochip* /dev/i2c-1 /dev/i2c-2
