import zmq, datetime,  os, subprocess, sys, yaml, glob

import myinotifier,util,math,time
import analysis.level0.pedestal_run_analysis as analyzer
import zmq_controler as zmqctrl
from nested_dict import nested_dict 

A_T = 3.9083e-3
B_T = -5.7750e-7
R0 = 1000

def run(i2csocket, daqsocket, nruns, odir, testName):
    index=0
    for run in range(nruns):
        util.acquire_scan(daq=daqsocket)
        chip_params = { }
        util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,
                          runid=index,testName=testName,keepRawData=1,
                          chip_params=chip_params)
        index=index+1
    return
        

def beam_run(i2csocket,daqsocket, clisocket, basedir,device_name, nruns):
    if type(i2csocket) != zmqctrl.i2cController:
        print( "ERROR in beam_run : i2csocket should be of type %s instead of %s"%(zmqctrl.i2cController,type(i2csocket)) )
        sleep(1)
        return
    if type(daqsocket) != zmqctrl.daqController:
        print( "ERROR in beam_run : daqsocket should be of type %s instead of %s"%(zmqctrl.daqController,type(daqsocket)) )
        sleep(1)
        return
    
    if type(clisocket) != zmqctrl.daqController:
        print( "ERROR in beam_run : clisocket should be of type %s instead of %s"%(zmqctrl.daqController,type(clisocket)) )
        sleep(1)
        return
    	
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    testName = "beam_run"
    odir = "%s/%s/beam_run/run_%s/"%( os.path.realpath(basedir), device_name, timestamp )
    os.makedirs(odir)
    
    #======================measure temperature and bias voltage=====================
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


    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)
    
    clisocket.yamlConfig['client']['outputDirectory'] = odir
    clisocket.yamlConfig['client']['run_type'] = testName
    clisocket.configure()
    daqsocket.yamlConfig['daq']['active_menu']='externalL1A'
    daqsocket.yamlConfig['daq']['menus']['externalL1A']['NEvents']=200000
    daqsocket.yamlConfig['daq']['menus']['externalL1A']['loopBack']=False
    daqsocket.yamlConfig['daq']['menus']['externalL1A']['prescale']=0
    daqsocket.yamlConfig['daq']['menus']['externalL1A']['trg_fifo_latency']=5
    daqsocket.yamlConfig['daq']['menus']['externalL1A']['trgphase_fifo_latency']=20
    daqsocket.configure()

    nestedConf = nested_dict()
    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            nestedConf[key]['sc']['DigitalHalf']['all']['CalibrationSC'] = 0
            nestedConf[key]['sc']['DigitalHalf']['all']['L1Offset'] = 13 #13
            nestedConf[key]['sc']['Top']['all']['phase_ck']= 14
    i2csocket.update_yamlConfig(yamlNode=nestedConf.to_dict())
    i2csocket.configure()
    i2csocket.resettdc()
    	
    util.saveFullConfig(odir=odir,i2c=i2csocket,daq=daqsocket,cli=clisocket)
    clisocket.start()
    mylittlenotifier.start()
    run(i2csocket, daqsocket, nruns, odir, testName)
    mylittlenotifier.stop()
    clisocket.stop()
    
    #======================measure temperature and bias voltage=====================    
    fout.write("####  After data capture ####" + '\n')
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

    parser.add_option("-n", "--nruns",type=int,default=1,
                      action="store", dest="nruns",
                      help="number of subruns")

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

    print(" ############## Starting up the MASTER TDCs #################")
    nestedConf = nested_dict()
    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            nestedConf[key]['sc']['MasterTdc']['all']['EN_MASTER_CTDC_VOUT_INIT']=1
            nestedConf[key]['sc']['MasterTdc']['all']['VD_CTDC_P_DAC_EN']=1
            nestedConf[key]['sc']['MasterTdc']['all']['VD_CTDC_P_D']=16
            nestedConf[key]['sc']['MasterTdc']['all']['EN_MASTER_FTDC_VOUT_INIT']=1
            nestedConf[key]['sc']['MasterTdc']['all']['VD_FTDC_P_DAC_EN']=1
            nestedConf[key]['sc']['MasterTdc']['all']['VD_FTDC_P_D']=16
            # nestedConf[key]['sc']['MasterTdc']['all']['INV_FRONT_40MHZ']=1

    i2csocket.update_yamlConfig(yamlNode=nestedConf.to_dict())
    i2csocket.configure()
    nestedConf = nested_dict()
    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            nestedConf[key]['sc']['MasterTdc']['all']['EN_MASTER_CTDC_VOUT_INIT']=0
            nestedConf[key]['sc']['MasterTdc']['all']['EN_MASTER_FTDC_VOUT_INIT']=0
    i2csocket.update_yamlConfig(yamlNode=nestedConf.to_dict())
    i2csocket.configure()

    beam_run(i2csocket,daqsocket,clisocket,options.odir,options.dut,options.nruns)
