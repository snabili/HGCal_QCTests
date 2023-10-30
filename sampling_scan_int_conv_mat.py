import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep
from nested_dict import nested_dict

import myinotifier,util
import analysis.level0.sampling_scan_analysis as analyzer
import zmq_controler as zmqctrl

def scan(i2csocket, daqsocket, startBX, stopBX, stepBX, startPhase, stopPhase, stepPhase, injectedChannels, odir):
    testName='sampling_scan'

    index=0
    # added for ROCv3 configuration ------------------------
    my_calib = injectionConfig['calib']
    gain = injectionConfig['gain'] # 0 for low range ; 1 for high range
    gain=1   # keep Highrange=1 for conveyor injection
    nestedConf = nested_dict()
    # pre-configure the injection
    
    print("Marke 1")
    update = lambda conf, chtype, channel, Range, val : conf[chtype][channel].update({Range:val})
    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            print("Marke 2")
            nestedConf[key]['sc']['ReferenceVoltage']['all']['IntCtest'] = 0   # '0' for conveyor injection
            nestedConf[key]['sc']['ReferenceVoltage']['all']['Calib_2V5'] = my_calib  # Calib_2V5: Conveyor injection, Calib: preamp injection
            nestedConf[key]['sc']['ReferenceVoltage']['all']['choice_cinj'] = 0   # "1": inject to preamp input, "0": inject to conveyor input
            nestedConf[key]['sc']['ReferenceVoltage']['all']['cmd_120p'] = 1 # cmd_120p=0: Cinj=3pF, cmd_120p=1: Cinj=120pF. Only Conveyor!!
            nestedConf[key]['sc']['ch']['all']['HighRange'] = 0   # Reset injection first.
            nestedConf[key]['sc']['ch']['all']['LowRange'] = 0   # Reset injection first.
            print(" prog calib: ", my_calib)
            if gain==2:
                for inj_chs in injectedChannels:
                   print(" Gain=2, Channel: ", inj_chs)
                   [nestedConf[key]['sc']['ch'][inj_chs].update({'LowRange':1}) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ] 
                   [nestedConf[key]['sc']['ch'][inj_chs].update({'HighRange':1}) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ]             
                
            elif gain==1:
                for inj_chs in injectedChannels:
                   print(" Gain=1, Channel: ", inj_chs)
                   [nestedConf[key]['sc']['ch'][inj_chs].update({'LowRange':0}) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ] 
                   [nestedConf[key]['sc']['ch'][inj_chs].update({'HighRange':1}) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ] 
                
            elif gain==0:
                for inj_chs in injectedChannels:
                   print(" Gain=0, Channel: ", inj_chs)
                   [nestedConf[key]['sc']['ch'][inj_chs].update({'LowRange':1}) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ] 
                   [nestedConf[key]['sc']['ch'][inj_chs].update({'HighRange':0}) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ] 
                
            else:
                pass
    i2csocket.configure(yamlNode=nestedConf.to_dict())
    
    # --------------------
       
    for BXrun in range(startBX, stopBX, stepBX):
        
        # daqsocket.l1a_generator_settings(name='A',enable=1,BX=0x10,length=1,flavor='CALPULINT',prescale=0,followMode='DISABLE')
        # daqsocket.l1a_generator_settings(name='B',enable=1,BX=BXrun,length=1,flavor='L1A',prescale=0,followMode='A')
        daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['calibType']="CALPULINT"
        daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['lengthCalib']=1
        daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['bxCalib']=0x10
        daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['prescale']=1   
         
        #daqsocket.l1a_generator_settings(name='B',enable=1,BX=BX,length=1,flavor='L1A',prescale=0,followMode='A')  #--------added for sampling scan ext 
        daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['lengthL1A']=1
        daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['bxL1A']=BXrun
        # daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['prescale']=0
        daqsocket.configure()
        
        print(BXrun)

        for phase in range(startPhase,stopPhase+1,stepPhase):
            nestedConf = nested_dict()
            for key in i2csocket.yamlConfig.keys():
                if key.find('roc_s')==0:
                    # nestedConf[key]['sc']['Top']['all']['phase_strobe']=15-phase
                    nestedConf[key]['sc']['Top']['all']['phase_ck']=phase
            i2csocket.configure(yamlNode=nestedConf.to_dict())
            i2csocket.resettdc()	# Reset MasterTDCs

            util.acquire_scan(daq=daqsocket)
            chip_params = { 'BX' : BXrun-startBX, 'Phase' : phase }
            util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,
                              runid=index,testName=testName,keepRawData=1,
                              chip_params=chip_params)
            index=index+1
    return

def sampling_scan(i2csocket,daqsocket, clisocket, basedir,device_name, injectionConfig,suffix=""):
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
    odir = "%s/%s/sampling_scan/run_%s/"%( os.path.realpath(basedir), device_name, timestamp ) # a comlete path is needed
    os.makedirs(odir)
    
    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)
    mylittlenotifier.start()

    startPhase=0
    stopPhase=15
    stepPhase=1

    clisocket.yamlConfig['client']['outputDirectory'] = odir
    clisocket.yamlConfig['client']['run_type'] = "sampling_scan"
    clisocket.configure()
    
    '''
    clisocket.yamlConfig['global']['outputDirectory'] = odir
    clisocket.yamlConfig['global']['run_type'] = "sampling_scan"
    clisocket.yamlConfig['global']['serverIP'] = daqsocket.ip
    clisocket.configure()
    '''
    
    calibreq = 0x10
    bxoffset = 22   # was 23, 23 is better for phase_strobe clk,  Mathias 26.4.
    startBX=calibreq+bxoffset-2 # -2
    stopBX=calibreq+bxoffset+5 # +5
    print("StartBX: ",startBX)
    print("StopBX: ",stopBX)
    stepBX=1
    
    daqsocket.yamlConfig['daq']['active_menu']='calibAndL1A'
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['NEvents']= 500     # 500 before
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['bxCalib']=calibreq
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['lengthCalib']=1
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['lengthL1A']=1
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['prescale']=0
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['repeatOffset']=0 # was 700
    
    # daqsocket.yamlConfig['daq']['NEvents']='500'
    # daqsocket.enable_fast_commands(0,0,0) ## disable all non-periodic gen L1A sources 
    # daqsocket.l1a_generator_settings(name='A',enable=1,BX=calibreq,length=1,flavor='L1A',prescale=0,followMode='DISABLE')
    # daqsocket.l1a_generator_settings(name='A',enable=1,BX=calibreq,length=1,flavor='CALPULINT',prescale=0,followMode='DISABLE')
    print("gain = %i" %injectionConfig['gain'])
    print("calib = %i" %injectionConfig['calib'])
    gain = injectionConfig['gain'] # 0 for low range ; 1 for high range
    calib = injectionConfig['calib'] # 
    injectedChannels=injectionConfig['injectedChannels']

    util.saveFullConfig(odir=odir,i2c=i2csocket,daq=daqsocket,cli=clisocket)

    i2csocket.configure_injection(injectedChannels, activate=1, gain=gain, phase=0, calib_dac=calib)

    clisocket.start()
    scan(i2csocket=i2csocket, daqsocket=daqsocket, 
	     startBX=startBX, stopBX=stopBX, stepBX=stepBX, 
	     startPhase=startPhase, stopPhase=stopPhase, stepPhase=stepPhase, 
	     injectedChannels=injectedChannels, odir=odir)
    clisocket.stop()
    mylittlenotifier.stop()

    scan_analyzer = analyzer.sampling_scan_analyzer(odir=odir)
    # files = glob.glob(odir+"/"+clisocket.yamlConfig['global']['run_type']+"*.root")
    files = glob.glob(odir+"/"+clisocket.yamlConfig['client']['run_type']+"*.root")
     
    for f in files:
	    scan_analyzer.add(f)
    scan_analyzer.mergeData()
    scan_analyzer.makePlots(injectedChannels)
    scan_analyzer.determine_bestPhase(injectedChannels)

    # return to no injection setting
    i2csocket.configure_injection(injectedChannels,activate=0,calib_dac=0,gain=0) # 14 is the best phase -> might need to extract it from analysis

    with open(odir+'/best_phase.yaml') as fin:
        cfg = yaml.safe_load(fin)
        i2csocket.configure(yamlNode=cfg)
        i2csocket.update_yamlConfig(yamlNode=cfg)
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
    i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)
    '''
    if options.initialize==True:
        i2csocket.initialize()
        daqsocket.initialize()
        clisocket.yamlConfig['client']['serverIP'] = daqsocket.ip
        clisocket.initialize()
    else:
        i2csocket.configure()
    '''
    i2csocket.configure()

    #nestedConf = nested_dict()
    #for key in i2csocket.yamlConfig.keys():
    #    if key.find('roc_s')==0:
    #        nestedConf[key]['sc']['ReferenceVoltage']['all']['Toa_vref']=200
    #        nestedConf[key]['sc']['ReferenceVoltage']['all']['Tot_vref']=500
    #i2csocket.update_yamlConfig(yamlNode=nestedConf.to_dict())
    #i2csocket.configure(yamlNode=nestedConf.to_dict())

    injectionConfig = {
        'gain' : 1,   # gain=0: LowRange, gain=1: HighRange
        'calib' : 120,
        'injectedChannels' : [2, 37]  # for conveyor injection: Only one active channeli!!
       
    }
    sampling_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig,suffix="")
