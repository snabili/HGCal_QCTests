import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep
import json
import signal
import subprocess

import myinotifier
import zmq_controler as zmqctrl

from optparse import OptionParser

sigint_interrupt = False

def sigint_handler(sig, frame):
    global sigint_interrupt
    sigint_interrupt = True

def run(i2csocket, daqsocket, clisocket, basedir, device_name, options, runNum):
    if type(i2csocket) != zmqctrl.i2cController:
        print( "ERROR in pedestal_run : i2csocket should be of type %s instead of %s"%(zmqctrl.i2cController,type(i2csocket)) )
        sleep(1)
        return

    if type(daqsocket) != zmqctrl.daqController:
        print( "ERROR in pedestal_run : daqsocket should be of type %s instead of %s"%(zmqctrl.daqController,type(daqsocket)) )
        sleep(1)
        return

    if type(clisocket) != zmqctrl.daqController:
        print( "ERROR in pedestal_run : clisocket should be of type %s instead of %s"%(zmqctrl.daqController,type(clisocket)) )
        sleep(1)
        return
        
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    testName = "run"
    odir = "%s/%s/run_%s/"%( os.path.realpath(basedir), device_name, timestamp )
    os.makedirs(odir)

    #start the zmq_client
    zmq_client = subprocess.Popen(["zmq-client"])
    
    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)
    mylittlenotifier.start()

    clisocket.yamlConfig['global']['outputDirectory'] = odir
    clisocket.yamlConfig['global']['run_type'] = testName
    clisocket.yamlConfig['global']['serverIP'] = daqsocket.ip
    clisocket.yamlConfig['global']['run_num'] = runNum
    clisocket.configure()

    daqsocket.yamlConfig['daq']['NEvents']=options.nevts
    daqsocket.yamlConfig['daq']['NSamples']=options.samples
    #daqsocket.yamlConfig['daq']['L1A_type']=options.trigger
    if options.trigger == 'ext':
        daqsocket.yamlConfig['daq']['l1a_enables']['external_l1a'] = 0xf
    elif options.trigger == 'rand':
        daqsocket.yamlConfig['daq']['l1a_enables']['random_l1a'] = 0x1
    else:
        if 'A' in options.trigger: daqsocket.yamlConfig['daq']['l1a_enables']['periodic_l1a_A'] = 0x1
        if 'B' in options.trigger: daqsocket.yamlConfig['daq']['l1a_enables']['periodic_l1a_B'] = 0x1
        if 'C' in options.trigger: daqsocket.yamlConfig['daq']['l1a_enables']['periodic_l1a_C'] = 0x1
        if 'D' in options.trigger: daqsocket.yamlConfig['daq']['l1a_enables']['periodic_l1a_D'] = 0x1
        
    daqsocket.yamlConfig['daq']['l1a_settings']['bx_spacing'] = 43 + 2
    daqsocket.yamlConfig['daq']['l1a_settings']['length'] = (options.samples-1) * 43 + 2
    for gen in daqsocket.yamlConfig['daq']['l1a_generator_settings']:
        gen['length'] = (options.samples-1) * 43 + 2

    
    daqsocket.configure()

    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            i2csocket.yamlConfig[key]['sc']['DigitalHalf']['all']['L1Offset'] = options.offset
    i2csocket.configure()
        
    initial_full_config={}
    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            initial_full_config[key] = i2csocket.yamlConfig[key]
            initial_full_config['daq'] = daqsocket.yamlConfig['daq']
            initial_full_config['global'] = clisocket.yamlConfig['global']


    with open(odir+"/initial_full_config.yaml",'w') as fout:
        yaml.dump(initial_full_config,fout)
            
    with open('./configs/meta.yaml') as fin:
        meta_yaml = yaml.safe_load(fin)
        meta_yaml['metaData']['hexactrl'] = i2csocket.ip
        meta_yaml['metaData']['NEvents']  = daqsocket.yamlConfig['daq']['NEvents']
        meta_yaml['metaData']['hw_type']  = 'TB'
        meta_yaml['metaData']['testName'] = testName
        meta_yaml['metaData']['keepRawData'] = 1
        with open(odir + "/" + meta_yaml['metaData']['testName']+'_%d_0.yaml'%runNum, 'w') as fout: #the 0 is important for the myinotifier server (matching between yaml file and raw data file)
#        with open(odir + "/" + meta_yaml['metaData']['testName']+'0.yaml', 'w') as fout: #the 0 is important for the myinotifier server (matching between yaml file and raw data file)
            yaml.dump(meta_yaml, fout)

    signal.signal(signal.SIGINT, sigint_handler)
    clisocket.start()
    daqsocket.start()
    while not sigint_interrupt:
        if daqsocket.is_done() == True:
            break
        else:
            sleep(0.01)
    daqsocket.stop()
    clisocket.stop()

    zmq_client.terminate()
    zmq_client.wait()

    # I'm sorry, there is probably a better fix - but this stopped the race condition 
    sleep(1)
    

    mylittlenotifier.stop()



def main(options, args):

    base_directory = options.datadirname
    hexactrl = options.testerip

    if len(args) > 0 :
        device_name = str(args[0])
    else:
        print("Must specify a run name")
        exit(1)

    try:
        with open("runnumbers", "r") as f_runnum:
            runnums = json.load(f_runnum)
            maxRunNum = max(runnums)
            nextRunNum = maxRunNum + 1
    except:
        nextRunNum = 0
        runnums = [nextRunNum]

    if options.runnum > 0:
        nextRunNum = options.runnum
    else:
        with open("runnumbers", "w") as f_runnum:
            runnums.append(nextRunNum)
            f_runnum.write(json.dumps(runnums))

    yamlCfg = options.cfg

    daqsocket = zmqctrl.daqController(hexactrl,"6000", yamlCfg)
    clisocket = zmqctrl.daqController("localhost","6001", yamlCfg)
    i2csocket = zmqctrl.i2cController(hexactrl,"5555", yamlCfg)
    i2csocket.initialize()
    run(i2csocket,daqsocket,clisocket,base_directory,device_name,options,nextRunNum)

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-c", "--cfg",     dest="cfg",          default="./configs/SPE_peaksConvGain8.yaml", help="Configuration file")
    parser.add_option("-n", "--nevts",   dest="nevts",        default=10000,  type=int,                    help="Number of triggers to take")
    parser.add_option("-i", "--ip",      dest="testerip",     default="192.168.133.200",                   help="IP or network name of ZYNQ")
    parser.add_option("-d", "--datadir", dest="datadirname",  default="/data/TestBeam/2020_19_December_TASS/TASS/",  help="Path to the data directory in which the data will be stored")
    parser.add_option("-t", "--trigger", dest="trigger",      default="ext",                               help="Trigger type (A, B, AB, rand, ext")
    parser.add_option("-o", "--offset",  dest="offset",       default=10,  type=int,                       help="L1A buffer offset")
    parser.add_option("-s", "--samples", dest="samples",      default=5,   type=int,                       help="Number of TS to record per trigger")
    parser.add_option("-r", "--runnum",  dest="runnum",       default=-1,  type=int,                       help="Run number to use for the current run")
    
    (options, args) = parser.parse_args()
    
    main(options, args)
