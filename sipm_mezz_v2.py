#!/usr/bin/python

import iic
from ad5593r import ad5593r
import argparse

class sipm_mezz:

    def __init__(self, bus=None):
        if bus:
            self.chip=ad5593r(bus,0x10)
        else:
            self.chip=ad5593r("/dev/i2c-2",0x10)

        self.chip.setup_dac(0) # VLED_CTL
        self.chip.setup_adc(1) # VMONLED
        self.chip.setup_adc(2) # IMONLED

        self.chip.setup_adc(3) # VMONSIPM
        self.chip.setup_adc(4) # IMONSIPM

    def setLED(self, value):
        """ Set the LED voltage (volts) """
        self.chip.dac_write(0,value)

    def vmonLED(self):
        """ Read the LED voltage (volts) """
        value = self.chip.adc_volts(1)
        value = value*15.0/1
        return value
        
    def imonLED(self):
        """ Read the LED current (mA) """
        value = self.chip.adc_volts(2)
        return value*1000.0

    def vmonSIPM(self):
        """ Read the SIPM voltage (volts) """
        value = self.chip.adc_volts(3)
        value = value*15.0/1
        return value

    def imonSIPM(self):
        """ Read the SIPM current (mA) """
        value = self.chip.adc_volts(4)
        return value*1000.0

if __name__=="__main__":
    
    parser=argparse.ArgumentParser(description="SIPM mezzanine")
    parser.add_argument('--status',action='store_true',help='Get the status')
    parser.add_argument('--setLED',type=int,default=None,help='Set LED voltage')
    args=parser.parse_args()

    sipmMezz = sipm_mezz()
    
    if args.setLED is not None:
        sipmMezz.setLED(args.setLED)

    if (args.status):
        print("Vmon LED: %.3f volts"%(sipmMezz.vmonLED()))
        print("Imon LED: %.3f mA"%(sipmMezz.imonLED()))
        print("Vmon SIPM: %.3f volts"%(sipmMezz.vmonSIPM()))
        print("Imon SIPM: %.3f mA"%(sipmMezz.imonSIPM()))
