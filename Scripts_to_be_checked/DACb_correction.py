import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep

import myinotifier,util
import analysis.level0.pedestal_scan_analysis as analyzer
import zmq_controler as zmqctrl
from nested_dict import nested_dict

import uproot
import pandas as pd
import numpy as np

calib_ch = [72,73]
cm_ch    = [74,75,76,77]

cm_dacb_vals = {0:5,1:5,2:5,3:5,4:5,5:5,6:5,7:5,8:5,9:5,10:5,11:5,12:5,13:5,14:5,15:5}

dacb_range_offset = 3   
## pedestal is calculated at two points to get gradient: at cm_dacb_vals[convgain] - dacb_range_offset and + dacb_range_offset

convgain = 4

Sign_dac_default = 0

# DACb scan
def DACb_scan(i2csocket,daqsocket, clisocket, basedir,device_name,configFile,convgain):
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
    odir = "%s/%s/pedestal_scan/run_%s/"%( os.path.realpath(basedir), device_name, timestamp ) # a comlete path is needed
    os.makedirs(odir)
    
    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)
    mylittlenotifier.start()

    clisocket.yamlConfig['client']['outputDirectory'] = odir
    clisocket.yamlConfig['client']['run_type'] = "pedestal_scan"
    clisocket.yamlConfig['client']['serverIP'] = daqsocket.ip
    clisocket.configure()
    daqsocket.yamlConfig['daq']['active_menu']='randomL1A'
    daqsocket.yamlConfig['daq']['menus']['randomL1A']['NEvents']=1000
    daqsocket.yamlConfig['daq']['menus']['randomL1A']['log2_rand_bx_period']=0
    daqsocket.yamlConfig['daq']['menus']['randomL1A']['bx_min']=45
    daqsocket.configure()

    util.saveFullConfig(odir=odir,i2c=i2csocket,daq=daqsocket,cli=clisocket)
            
    clisocket.start()
    #scan_pedDAC(i2csocket, daqsocket, start_val, stop_val, step_val,odir)
    
    testName='pedestal_scan'
    index=0
    
    #for Dacb_val in Dacb_vals:
    nestedConf = nested_dict()
    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
                
            nestedConf[key]['sc']['cm']['all']['dacb']=cm_dacb_vals[convgain]
            nestedConf[key]['sc']['calib']['all']['dacb']=cm_dacb_vals[convgain]
            print("cm and calib set to",cm_dacb_vals[convgain],"for CGain",convgain)
                    
            Dacb_vals = [cm_dacb_vals[convgain]-dacb_range_offset,cm_dacb_vals[convgain]+dacb_range_offset]
            for i,Dacb_val in enumerate(Dacb_vals):
                nestedConf[key]['sc']['ch']['all']['dacb']=Dacb_val
                i2csocket.configure(yamlNode=nestedConf.to_dict())
                util.acquire_scan(daq=daqsocket)
                chip_params = {'dacb' : Dacb_val}
                util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,
                                  runid=i,testName=testName,keepRawData=0,
                                  chip_params=chip_params)
        
        
    clisocket.stop()
    mylittlenotifier.stop()
    
    dataPd = pd.DataFrame()
    
    for i,Dacb_val in enumerate(Dacb_vals):
        f = uproot.open(os.path.join(odir,"pedestal_scan%i.root"%i))
        dataPd[Dacb_val] = f['runsummary']['summary']['adc_mean'].array(library='np')
    
    print("dataPd:")
    print(dataPd)    
        
    with open(configFile) as f:
        cfg = yaml.safe_load(f)
        
    calib_i =0
    cm_i    =0
    chan_i  =0 
    
    ped_needed = dataPd[cm_dacb_vals[convgain]-dacb_range_offset]
    print(ped_needed[ped_needed.index >= np.min(cm_ch)])
    ped_needed = ped_needed[ped_needed.index >= np.min(cm_ch)].mean()
    print("ped_needed:",ped_needed)
    
    
    for chan in range(0,len(dataPd)):  
        y = np.array(dataPd.loc[chan])
        grad  = (y[1]-y[0])/(Dacb_vals[1]-Dacb_vals[0])
        offset = y[0] - Dacb_vals[0]*grad
        if grad == 0:         
            dacb_val_signed = 63
            print("gradient was zero")
        else: 
            dacb_val = int((ped_needed-offset)/grad)
            if dacb_val >63:
                print("signdac=1")
                Sign_dac = 1
                dacb_val_signed = 2*63 - dacb_val
            else:
                dacb_val_signed = dacb_val
                Sign_dac = 0
        
        if chan in calib_ch:
            cfg["roc_s0"]["sc"]["calib"][calib_i]['dacb']= cm_dacb_vals[convgain]
            print("calib_i",calib_i)
            grad = 0
            calib_i += 1
        elif chan in cm_ch:
            cfg["roc_s0"]["sc"]["cm"][cm_i]['dacb']= cm_dacb_vals[convgain]
            print("cm_i",cm_i)
            grad = 0
            cm_i += 1
        else:
            cfg["roc_s0"]["sc"]["ch"][chan_i]["dacb"] = dacb_val_signed
            #cfg["roc_s0"]["sc"]["ch"][chan_i]["sign_dac"] = Sign_dac
            print("chan_i",chan_i)
            chan_i += 1
            
        if grad != 0:
            print(grad,offset)
            print(dacb_val_signed)
            #print(Sign_dac)
            print(grad*dacb_val+offset)
        else :
            print(Sign_dac_default,cm_dacb_vals[convgain])
        
    configFile0 = configFile[:configFile.find(".yaml")]
    with open(configFile0+"_DACbCorrected.yaml", "w") as o:
        yaml.dump(cfg, o)
    print("Saved new config file as:"+configFile0+"_DACbCorrected.yaml")  
    
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
    
    i2csocket.configure()
    DACb_scan(i2csocket,daqsocket,clisocket,options.odir,options.dut,options.configFile,convgain)
    
