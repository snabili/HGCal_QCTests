import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep

import myinotifier,util
import zmq_controler as zmqctrl
from nested_dict import nested_dict

# offset scan
def scan(i2csocket, daqsocket, l1offsets, odir, testname):
    index=0
    
    startPhase=0
    stopPhase=14
    stepPhase=1
    
    for iBX, offset in enumerate(l1offsets):
        
        nestedConf = nested_dict()
        for iph, phase in enumerate(range(startPhase,stopPhase+1,stepPhase)):
            for key in i2csocket.yamlConfig.keys():
                if key.find('roc_s')==0:
                    nestedConf[key]['sc']['DigitalHalf']['all']['L1Offset']=offset
                    nestedConf[key]['sc']['DigitalHalf']['all']['Bx_offset']=2
                
                    nestedConf[key]['sc']['Top']['all']['phase_ck']= phase #15-phase
                    i2csocket.configure(yamlNode=nestedConf.to_dict())
                    util.acquire_scan(daq=daqsocket)
                    chip_params = {'L1Aoffset' : offset }
                    util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,
                                      runid=index,testName=testname,keepRawData=1,
                                      chip_params=chip_params)
                    
                    index=index+1
    return

def l1offset_scan(i2csocket,daqsocket, clisocket, basedir,device_name):
    if type(i2csocket) != zmqctrl.i2cController:
	    print( "ERROR in l1offset_scan : i2csocket should be of type %s instead of %s"%(zmqctrl.i2cController,type(i2csocket)) )
	    sleep(1)
	    return

    if type(daqsocket) != zmqctrl.daqController:
	    print( "ERROR in l1offset_scan : daqsocket should be of type %s instead of %s"%(zmqctrl.daqController,type(daqsocket)) )
	    sleep(1)
	    return

    if type(clisocket) != zmqctrl.daqController:
	    print( "ERROR in l1offset_scan : clisocket should be of type %s instead of %s"%(zmqctrl.daqController,type(clisocket)) )
	    sleep(1)
	    return

    testname = "l1offset_scan"
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    odir = "%s/%s/%s/run_%s/"%( os.path.realpath(basedir), device_name, testname, timestamp ) # a comlete path is needed
    os.makedirs(odir)

    l1offsets = [i for i in range(11,14,1)]

    clisocket.yamlConfig['client']['outputDirectory'] = odir
    clisocket.yamlConfig['client']['run_type'] = testname
    clisocket.configure()
    daqsocket.yamlConfig['daq']['active_menu']='externalL1A'
    daqsocket.yamlConfig['daq']['menus']['externalL1A']['NEvents']=10000
    daqsocket.yamlConfig['daq']['menus']['externalL1A']['loopBack']=False
    daqsocket.yamlConfig['daq']['menus']['externalL1A']['prescale']=0
    daqsocket.yamlConfig['daq']['menus']['externalL1A']['trg_fifo_latency']=6
    daqsocket.yamlConfig['daq']['menus']['externalL1A']['trgphase_fifo_latency']=20
    
    daqsocket.configure()

    nestedConf = nested_dict()
    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            nestedConf[key]['sc']['DigitalHalf']['all']['CalibrationSC'] = 0
    i2csocket.update_yamlConfig(yamlNode=nestedConf.to_dict())
    i2csocket.configure()

    util.saveFullConfig(odir=odir,i2c=i2csocket,daq=daqsocket,cli=clisocket)
            
    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)
    clisocket.start()
    mylittlenotifier.start()
    scan(i2csocket=i2csocket, daqsocket=daqsocket, l1offsets=l1offsets, odir=odir, testname=testname)
    mylittlenotifier.stop()
    clisocket.stop()
    return odir


if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser()
    
    parser.add_option("-d", "--dut", dest="dut",
                      help="device under test")
    
    parser.add_option("-i", "--hexaIP",
                      action="store", dest="hexaIP",
                      help="IP address of the zynq on the hexactrl board")
    
    parser.add_option("-f", "--configFile",default="./configs/init.yaml",
                      action="store", dest="configFile",
                      help="initial configuration yaml file")
    
    parser.add_option("-o", "--odir",
                      action="store", dest="odir",default='./data',
                      help="output base directory")
    
    parser.add_option("--daqPort",
                      action="store", dest="daqPort",default='6000',
                      help="port of the zynq waiting for daq config and commands (configure/start/stop/is_done)")
    
    parser.add_option("--i2cPort",
                      action="store", dest="i2cPort",default='5555',
                      help="port of the zynq waiting for I2C config and commands (initialize/configure/read_pwr,read/measadc)")
    
    parser.add_option("--pullerPort",
                      action="store", dest="pullerPort",default='6001',
                      help="port of the client PC (loccalhost for the moment) waiting for daq config and commands (configure/start/stop)")
    
    parser.add_option("-I", "--initialize",default=False,
                      action="store_true", dest="initialize",
                      help="set to re-initialize the ROCs and daq-server instead of only configuring")

    (options, args) = parser.parse_args()
    print(options)
    
    daqsocket = zmqctrl.daqController(options.hexaIP,options.daqPort,options.configFile)
    clisocket = zmqctrl.daqController("localhost",options.pullerPort,options.configFile)
    clisocket.yamlConfig['client']['serverIP'] = options.hexaIP
    i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)

    if options.initialize==True:
        i2csocket.initialize()
        daqsocket.initialize()
        clisocket.yamlConfig['client']['serverIP'] = daqsocket.ip
        clisocket.initialize()
    else:
        i2csocket.configure()
    l1offset_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut)
