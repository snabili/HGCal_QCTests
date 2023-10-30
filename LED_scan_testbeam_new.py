import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep
from nested_dict import nested_dict

import myinotifier,util,math,time
import analysis.level0.sampling_scan_analysis as analyzer
import zmq_controler as zmqctrl

A_T = 3.9083e-3
B_T = -5.7750e-7
R0 = 1000

def scan(i2csocket, daqsocket, startBX, stopBX, stepBX, startPhase, stopPhase, stepPhase, trimstart, trimstop, trimstep, injectedChannels, odir):
    testName='sampling_scan'

    index=0
#=============================================added for sampling scan ext======================
# added for ROCv3 configuration ------------------------
    my_calib=0
    gain=1
    nestedConf = nested_dict()
    # pre-configure the injection
    
    #======================measure temperature and bias voltage=====================
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fout=open(odir+"TB2_info.txt", "x")
    fout.write("####  Before data capture ####" + '\n')
    fout.write("#  Tileboard2 Slow Control Data" + '\n')
    fout.write("#  Date, Time: " + timestamp + '\n')
    
    SCA_ADC_range = range(0, 8)
    for sca_adc in SCA_ADC_range:
       ADC = i2csocket.read_gbtsca_adc(sca_adc)
       T1 = round(float((-R0*A_T + math.sqrt(math.pow(R0*A_T, 2) - 4*R0*B_T*(R0-(1800 / ((2.5*4095/float(ADC))-1))))) / (2*R0*B_T)),1)
       print("T", sca_adc,  ":", str(T1))
       fout.write("T" + str(sca_adc) +": "+str(T1) + '\n')

    ADC = i2csocket.read_gbtsca_adc(9)
    MPPC_BIAS1 = round(float(ADC)/4095*204000/4000, 4)
    print("MPPC_BIAS1 = ", str(MPPC_BIAS1))
    fout.write("MPPC_BIAS1: " + str(MPPC_BIAS1) + '\n')

    ADC = i2csocket.read_gbtsca_adc(10)
    MPPC_BIAS2 = round(float(ADC)/4095*204000/4000, 4)
    print("MPPC_BIAS2 = ", str(MPPC_BIAS2))
    fout.write("MPPC_BIAS2: " + str(MPPC_BIAS2) + '\n')

    ADC = i2csocket.read_gbtsca_adc(12)
    LED_BIAS = round(float(ADC)/4095*15000/1000, 3)
    print("LED_BIAS = ", str(LED_BIAS))
    fout.write("LED_BIAS: " + str(LED_BIAS) + '\n')

    #===============================================================================

    for trim_val in range(trimstart, trimstop, trimstep):
   
        print("Marke 1")
        update = lambda conf, chtype, channel, Range, val : conf[chtype][channel].update({Range:val})
        for key in i2csocket.yamlConfig.keys():
            if key.find('roc_s')==0:
                nestedConf[key]['sc']['ReferenceVoltage']['all']['IntCtest'] = 0
                print("Marke 2")
                nestedConf[key]['sc']['ReferenceVoltage']['all']['Calib'] = my_calib
                nestedConf[key]['sc']['ReferenceVoltage']['all']['choice_cinj'] = 1   # "1": inject to preamp input, "0": inject to conveyor input
                nestedConf[key]['sc']['ReferenceVoltage']['all']['cmd_120p'] = 0
                nestedConf[key]['sc']['ch']['all']['trim_inv'] = trim_val
                # nestedConf[key]['sc']['ReferenceVoltage']['all'].update({'Calib':my_calib})
                if gain==2:
                    for inj_chs in injectedChannels:
                       [nestedConf[key]['sc']['ch'][inj_chs].update({'LowRange':0}) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ]
                       [nestedConf[key]['sc']['ch'][inj_chs].update({'HighRange':0}) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ]
                    # [update(nestedConf[key]['sc'],chtype,injectedChannel,'HighRange',1) for chtype in injectedChannels.keys() for injectedChannel in injectedChannels[chtype] ]
                    # [update(nestedConf[key]['sc'],chtype,injectedChannel,'LowRange',1) for chtype in injectedChannels.keys() for injectedChannel in injectedChannels[chtype] ]
                elif gain==1:
                    for inj_chs in injectedChannels:
                       print("Marke 3")
                       [nestedConf[key]['sc']['ch'][inj_chs].update({'LowRange':0}) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ]
                       [nestedConf[key]['sc']['ch'][inj_chs].update({'HighRange':0}) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ]
                    # [update(nestedConf[key]['sc'],chtype,injectedChannel,'HighRange',1) for chtype in injectedChannels.keys() for injectedChannel in injectedChannels[chtype] ]
                    # [update(nestedConf[key]['sc'],chtype,injectedChannel,'LowRange',0) for chtype in injectedChannels.keys() for injectedChannel in injectedChannels[chtype] ]
                elif gain==0:
                    for inj_chs in injectedChannels:
                       [nestedConf[key]['sc']['ch'][inj_chs].update({'LowRange':0}) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ]
                       [nestedConf[key]['sc']['ch'][inj_chs].update({'HighRange':0}) for key in i2csocket.yamlConfig.keys() if key.find('roc_s')==0 ]
                    # [update(nestedConf[key]['sc'],chtype,injectedChannel,'HighRange',0) for chtype in injectedChannels.keys() for injectedChannel in injectedChannels[chtype] ]
                    # [update(nestedConf[key]['sc'],chtype,injectedChannel,'LowRange',1) for chtype in injectedChannels.keys() for injectedChannel in injectedChannels[chtype] ]
                else:
                    pass
        i2csocket.configure(yamlNode=nestedConf.to_dict())
        



    #=========================================================================================
        
        for BX in range(startBX, stopBX, stepBX):

            #daqsocket.l1a_generator_settings(name='A',enable=1,BX=0x10,length=4,flavor='CALPULEXT',prescale=10,followMode='DISABLE') #--------added for sampling scan ext 
            daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['calibType']="CALPULEXT"
            daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['lengthCalib']=4
            daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['bxCalib']=0x10
            daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['prescale']=15  # was 15   
             
            #daqsocket.l1a_generator_settings(name='B',enable=1,BX=BX,length=1,flavor='L1A',prescale=0,followMode='A')  #--------added for sampling scan ext 
            daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['lengthL1A']=1
            daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['bxL1A']=BX
            #daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['prescale']=0

            daqsocket.configure()

            for phase in range(startPhase,stopPhase+1,stepPhase):
                print("Phase ", phase)
                nestedConf = nested_dict()
                for key in i2csocket.yamlConfig.keys():
                    if key.find('roc_s')==0:
                        # nestedConf[key]['sc']['Top']['all']['phase_strobe']=15-phase
                        nestedConf[key]['sc']['Top']['all']['phase_ck']=phase
                i2csocket.set_gbtsca_gpio_vals(0x00000080,0x00000080) # LED ON First argument: GPIO value, 2nd argument: Mask    ----> added for sampling scan ext 
                
                i2csocket.configure(yamlNode=nestedConf.to_dict())
                i2csocket.resettdc()	# Reset MasterTDCs
                print("Configure and tdc reset")

                util.acquire_scan(daq=daqsocket)
                print("acquire scan")
                chip_params = { 'BX' : BX-startBX, 'Phase' : phase }
                util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,
                                  runid=index,testName=testName,keepRawData=1,
                                  chip_params=chip_params)
                
                print("finish phase:", phase)
                
                 #======================measure temperature and bias voltage=====================    
                fout.write("####  BX, PHASE, TRIM_VAL ####" + '\n')
                fout.write("sample_scan: {} bx: {} phase: {} trim_val: {} \n".format(index,BX,phase,trim_val))
                fout.write("#  Tileboard2 Slow Control Data" + '\n')
                fout.write("#  Date, Time: " + timestamp + '\n')
               
                SCA_ADC_range = range(0, 8)
                for sca_adc in SCA_ADC_range:
                   ADC = i2csocket.read_gbtsca_adc(sca_adc)
                   T1 = round(float((-R0*A_T + math.sqrt(math.pow(R0*A_T, 2) - 4*R0*B_T*(R0-(1800 / ((2.5*4095/float(ADC))-1))))) / (2*R0*B_T)),1)
                   print("T", sca_adc,  ":", str(T1))
                   fout.write("T" + str(sca_adc) +": "+str(T1) + '\n')

                ADC = i2csocket.read_gbtsca_adc(9)
                MPPC_BIAS1 = round(float(ADC)/4095*204000/4000, 4)
                print("MPPC_BIAS1 = ", str(MPPC_BIAS1))
                fout.write("MPPC_BIAS1: " + str(MPPC_BIAS1) + '\n')

                ADC = i2csocket.read_gbtsca_adc(10)
                MPPC_BIAS2 = round(float(ADC)/4095*204000/4000, 4)
                print("MPPC_BIAS2 = ", str(MPPC_BIAS2))
                fout.write("MPPC_BIAS2: " + str(MPPC_BIAS2) + '\n')
                #===============================================================================
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

    startPhase=0
    stopPhase=15
    stepPhase=1
    
    trimstart=0
    trimstop=1   # was 3
    trimstep=1
    
    calibreq = 0x10
    bxoffset = 24 #  was 24--------24 in mathias's script
    noofoffsets = 2  # was 3
    startBX=calibreq+bxoffset #----------calibreq+bxoffset-1 in Mathias's script
    stopBX=calibreq+bxoffset+noofoffsets
    print("StartBX: ",startBX)
    print("StopBX: ",stopBX)
    stepBX=1
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    voltages = injectionConfig['OV']#-----------added for sampling scan ext
    LEDvolt = injectionConfig['LEDvolt']#------------added for sampling scan ext
    if suffix:
        timestamp = timestamp + "_" + suffix
    #odir = "%s/%s/LED_scan/run_%s/TB3_1_LED_scan_Rf14_ConvGain12_OV%iV_extLED%imV"%( os.path.realpath(basedir), device_name, timestamp,voltages,LEDvolt) # a comlete path is needed #-----------------original
    odir = "%s/%s/LED_scan/TB3_LED_scan_Rf14_ConvGain12_OV%iV_%imV_BXstart%i_BXstop%i_BXstep%i_Phsstart%i_Phsstop%i_Phsstep%i_trimstart%i_trimstop%i_trimstep%i_%s/"%( 
                                                                                    os.path.realpath(basedir), device_name, voltages, LEDvolt,
                                                                                    bxoffset, bxoffset+noofoffsets-1, stepBX,startPhase,stopPhase
                                                                                    ,stepPhase, trimstart, trimstop, trimstep, timestamp) 
    os.makedirs(odir)
    
    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)
    #mylittlenotifier.start()#------------added for sampling scan ext

    
    clisocket.yamlConfig['client']['outputDirectory'] = odir
    clisocket.yamlConfig['client']['run_type'] = "sampling_scan"
    clisocket.configure()
    

    daqsocket.yamlConfig['daq']['active_menu']='calibAndL1A'
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['NEvents']=2500 #-----1000 in original
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['bxCalib']=calibreq
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['lengthCalib']=1
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['lengthL1A']=1
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['prescale']=0
    daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['repeatOffset']=0    # was 700

    #daqsocket.yamlConfig['daq']['NEvents']='500' # disabled in the original
    #daqsocket.enable_fast_commands(0,0,0) ## disable all non-periodic gen L1A sources # ------added for the sampling scan ext 
    #daqsocket.l1a_generator_settings(name='A',enable=1,BX=calibreq,length=1,flavor='CALPULINT',prescale=0,followMode='DISABLE')# ------added for the sampling scan ext 

    print("gain = %i" %injectionConfig['gain'])
    print("calib = %i" %injectionConfig['calib'])
    gain = injectionConfig['gain'] # 0 for low range ; 1 for high range
    calib = injectionConfig['calib'] # 

    voltages = injectionConfig['OV']#------------added for sampling scan ext
    LEDvolt = injectionConfig['LEDvolt']#------------added for sampling scan ext

    injectedChannels=injectionConfig['injectedChannels']

    util.saveFullConfig(odir=odir,i2c=i2csocket,daq=daqsocket,cli=clisocket)

    i2csocket.configure_injection(injectedChannels, activate=0, gain=gain, phase=0, calib_dac=calib)

    clisocket.start()
    mylittlenotifier.start()
    scan(i2csocket=i2csocket, daqsocket=daqsocket, 
	     startBX=startBX, stopBX=stopBX, stepBX=stepBX, 
	     startPhase=startPhase, stopPhase=stopPhase, stepPhase=stepPhase, 
	     trimstart=trimstart, trimstop=trimstop, trimstep=trimstep, injectedChannels=injectedChannels, odir=odir)
    print("scan finish")
    mylittlenotifier.stop()
    print("mylittlenotifier stop")
    clisocket.stop()
    print("clisocket stop")

    
    try:
        scan_analyzer = analyzer.sampling_scan_analyzer(odir=odir)
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
    except:
        with open(odir+"crash_report.log","w") as fout:
            fout.write("analysis went wrong and crash\n")
       
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
    
    if options.initialize==True:
        i2csocket.initialize()
        daqsocket.initialize()
        clisocket.yamlConfig['client']['serverIP'] = daqsocket.ip
        clisocket.initialize()
    else:
        i2csocket.configure()

    #nestedConf = nested_dict()
    #for key in i2csocket.yamlConfig.keys():
    #    if key.find('roc_s')==0:
    #        nestedConf[key]['sc']['ReferenceVoltage']['all']['Toa_vref']=200
    #        nestedConf[key]['sc']['ReferenceVoltage']['all']['Tot_vref']=500
    #i2csocket.update_yamlConfig(yamlNode=nestedConf.to_dict())
    #i2csocket.configure(yamlNode=nestedConf.to_dict())

    injectionConfig = {
        'gain' : 1, # 0 in original
        'calib' : 0, #900 in original
        # 'injectedChannels' : [11,11+18,10+36,10+18+36],
        #'injectedChannels' : [50, 51, 52, 49, 1, 2, 3], # [32, 33, 35, 40, 41, 42, 43],
        'injectedChannels' : [10,46,52, 49, 1, 2, 3],
        #'injectedChannels'  : [i for i in range (1,66)],
        #'injectedChannels' : [10],
        'LEDvolt' : 6200,  # LED_BIAS (LED amplitude) in mV  #------------added for sampling scan ext
        'OV'    : 4   # SiPM overvoltage   #------------added for sampling scan ext
    }
    sampling_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,injectionConfig,suffix="")
