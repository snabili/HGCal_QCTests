import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep

import pandas
from level0.analyzer import *
import myinotifier,util
import analysis.level0.injection_scan_analysis as analyzer
import zmq_controler as zmqctrl
from nested_dict import nested_dict

def scan(i2csocket, daqsocket, injectedChannels, calib_dac_vals, gain, odir,keepRawData=0):
    testName = 'injection_scan'

    index=0
    myphase = 12    # was 7
    
    ### added from Mathias
    nestedConf = nested_dict()
    for key in i2csocket.yamlConfig.keys():
        print("Marke 1")
        if key.find('roc_s')==0:
            print("Marke2")
            nestedConf[key]['sc']['ReferenceVoltage']['all']['IntCtest'] = 0  # "0": injection into conveyor, "1": preamp injection
            print("Marke 3")
            nestedConf[key]['sc']['ReferenceVoltage']['all']['choice_cinj'] = 0   # "1": inject to preamp input, "0": inject to conveyor input
            nestedConf[key]['sc']['ReferenceVoltage']['all']['cmd_120p'] = 1 # cmd_120p=0: Cinj=3pF, cmd_120p=1: Cinj=120pF. Only Conveyor!!
            nestedConf[key]['sc']['Top']['all']['phase_ck']=myphase
            print(" Phase set: ", myphase)
            nestedConf[key]['sc']['ch']['all']['LowRange'] = 0   # Reset injection first.
            nestedConf[key]['sc']['ch']['all']['HighRange'] = 0   # Reset injection first.
            for inj_chs in injectedChannels:
                   print(" Gain=1, Channel: ", inj_chs)
                   [nestedConf[key]['sc']['ch'][inj_chs].update({'LowRange':0}) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ] 
                   [nestedConf[key]['sc']['ch'][inj_chs].update({'HighRange':1}) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ] 
    i2csocket.configure(yamlNode=nestedConf.to_dict())
    ### end added part
    
        
    for calibDAC_val in calib_dac_vals:
        i2csocket.sipm_configure_injection(injectedChannels, activate=1, gain=gain, calib_dac=calibDAC_val)
        # i2csocket.sipm_configure_injection(injectedChannels, activate=1, gain=gain, calib_dac=0)
        
        # nestedConf[key]['sc']['ReferenceVoltage']['all']['Calib_2V5'] = calibDAC_val
        # i2csocket.configure(yamlNode=nestedConf.to_dict())
        
        # i2csocket.configure_injection(injectedChannels, activate=1, gain=gain, calib_dac=calibDAC_val)
        util.acquire_scan(daq=daqsocket)
        # chip_params = { 'Inj_gain':gain, 'Calib_dac':calibDAC_val }
        chip_params = { 'gain':gain, 'Calib':calibDAC_val, 'injectedChannels':injectedChannels[0] }   
        util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,
                          runid=index,testName=testName,keepRawData=keepRawData,
                          chip_params=chip_params)
        index+=1
    return

def sipm_injection_scan(i2csocket,daqsocket,clisocket,basedir,device_name,injectionConfig,suffix='',keepRawData=1,analysis=1):
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
    if suffix:
        timestamp = timestamp + "_" + suffix
    odir = "%s/%s/injection_scan/run_%s/"%( os.path.realpath(basedir), device_name, timestamp ) # a complete path is needed
    os.makedirs(odir)
    
     # do not run the inotifier if the unpacker is not yet ready to read vectors inside metaData yaml file using key "chip_params"
    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)
    
    calibreqA            = 0x10
    calibreqC            = 0x200
    # phase				= injectionConfig['phase']   # was commented out
    BXoffset			= injectionConfig['BXoffset']
    injectedChannels	= injectionConfig['injectedChannels']
    
    calib_dac 			= injectionConfig['calib']
    gain 				= injectionConfig['gain'] # 0 for low range ; 1 for high range
    
    clisocket.yamlConfig['client']['outputDirectory'] = odir
    clisocket.yamlConfig['client']['run_type'] = "injection_scan"
    clisocket.configure()
    
    daqsocket.yamlConfig['daq']['active_menu']='calibAndL1A'
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['calibType']="CALPULINT"  # added Mathias 
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['NEvents']=500
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['bxCalib']=calibreqA
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['bxL1A']=calibreqA+BXoffset
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['lengthCalib']=1
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['lengthL1A']=1 #1
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['prescale']=0
    #Just for external injeciton (to enable the SiPM calib signal):
    #daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['calibType']='CALPULEXT'
    daqsocket.configure()

    # daqsocket.yamlConfig['daq']['active_menu']='calibAndL1AplusTPG'
    # daqsocket.yamlConfig['daq']['menus']['calibAndL1AplusTPG']['NEvents']=1000
    # daqsocket.yamlConfig['daq']['menus']['calibAndL1AplusTPG']['bxCalib']=calibreqA
    # daqsocket.yamlConfig['daq']['menus']['calibAndL1AplusTPG']['bxL1A']=calibreqA+BXoffset
    # daqsocket.yamlConfig['daq']['menus']['calibAndL1AplusTPG']['trg_fifo_latency']=5
    # daqsocket.yamlConfig['daq']['menus']['calibAndL1AplusTPG']['lengthCalib']=1
    # daqsocket.yamlConfig['daq']['menus']['calibAndL1AplusTPG']['lengthL1A']=1
    # daqsocket.yamlConfig['daq']['menus']['calibAndL1AplusTPG']['prescale']=0
    # daqsocket.configure()
    
    util.saveFullConfig(odir=odir,i2c=i2csocket,daq=daqsocket,cli=clisocket)
    
    clisocket.start()
    mylittlenotifier.start()
    scan(i2csocket=i2csocket, daqsocket=daqsocket, injectedChannels=injectedChannels, calib_dac_vals=calib_dac, gain=gain, odir=odir,keepRawData=keepRawData)
    mylittlenotifier.stop()
    clisocket.stop()
    
    # return to no injection setting
    # i2csocket.sipm_configure_injection(injectedChannels, activate=0, gain=0, calib=0) #maybe we should go back to phase 0
    i2csocket.sipm_configure_injection(injectedChannels, activate=0, gain=0, calib_dac=0) #maybe we should go back to phase 0
    # i2csocket.configure_injection(injectedChannels, activate=0, gain=0, calib_dac=0)
    
    if analysis == 1:
        scan_analyzer = analyzer.injection_scan_analyzer(odir=odir)
        files = glob.glob(odir+"/*.root")
        for f in files:
            scan_analyzer.add(f)
            # r_summary = reader(f)
            # r_raw = rawroot_reader(f)
            # r_raw.df['Calib_dac'] = r_summary.df.Calib_dac.unique()[0]
            # scan_analyzer.dataFrames.append(r_raw.df)
        scan_analyzer.mergeData()
        scan_analyzer.makePlots()

        ''' 
        max_dict = scan_analyzer.determineAdcRange(injectedChannels)
        print("max_dict ", max_dict)
        max_calib = min(max_dict.values())
        print("max_calib ", max_calib)
        '''
        
    # return odir, max_dict
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
    
    parser.add_option("-s", "--suffix",
                      action="store", dest="suffix",default='',
                      help="output base directory")

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
    if not options.hexaIP:
        options.hexaIP = '10.254.56.32'
        # was options.hexaIP = '129.104.89.111'
    print(options.hexaIP)
    
    daqsocket = zmqctrl.daqController(options.hexaIP,options.daqPort,options.configFile)
    clisocket = zmqctrl.daqController("localhost",options.pullerPort,options.configFile)
    i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)
    
    if options.initialize==True:
        i2csocket.initialize()
        clisocket.yamlConfig['client']['serverIP'] = daqsocket.ip
        clisocket.initialize()
        daqsocket.initialize()
    else:
        i2csocket.configure()

    injectionConfig = {
        'BXoffset' : 21,   # was 23
        'gain' : 1,
        'phase' : 12,
        # 'calib' : [-1]+[i for i in range(0,4000,100)],
        'calib' : [i for i in range(0,2000,20)],
        'injectedChannels' : [66]
    }
    sipm_injection_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig,suffix=options.suffix,keepRawData=0,analysis=1)
