import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep

import pandas
from level0.analyzer import *
import myinotifier,util
import analysis.level0.toa_scan_analysis as analyzer
import zmq_controler as zmqctrl
from nested_dict import nested_dict
import sipm_injection_scan_conv_mat


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
    
    calib2V5_total = [i for i in range(0,2500,10)]
    injectedChannels = range(0, 35, 5)
    gain=0
    injection_scan_mode=1
    
    if injection_scan_mode == 1:
        print(" ############## Start injection scan #################")
        for injChannel in injectedChannels:
            injectionConfig = {
            'BXoffset' : 22, # was 22
            'gain' : gain,
            'calib' : [i for i in calib2V5_total],
            'injectedChannels' : [injChannel, injChannel + 36]
            }
            sipm_injection_scan_conv_mat.sipm_injection_scan(i2csocket,daqsocket,clisocket,options.odir,options_dut,injectionConfig,suffix="gain0_ch%i"%injChannel,keepRawData=1,analysis=1)

        odir = "%s/%s/injection_scan/"%(options.odir, options_dut)
        toa_threshold_analyzer = analyzer.toa_scan_analyzer(odir=odir)
        folders = glob.glob(odir+"run_*/")
        df_ = []
        for folder in folders:
                files = glob.glob(folder+"/*.root")
                for f in files[:]:
                        df_summary = uproot3.open(f)['runsummary']['summary'].pandas.df()
                        df_.append(df_summary)
        toa_threshold_analyzer.data = pandas.concat(df_)
        toa_threshold_analyzer.makePlot_calib(config_ns_charge='pC')
        
        del toa_threshold_analyzer
    
     # do not run the inotifier if the unpacker is not yet ready to read vectors inside metaData yaml file using key "chip_params"
    


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

    ############    
    # SUFFIX CONFIG:
    timestamp_fulltest = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if options.suffix == None:
        options_dut = options.dut + "/vreftoa_scurvescan/test_%s"%(timestamp_fulltest)
    else:
        options_dut = options.dut + "/vreftoa_scurvescan/test_%s_%s"%(timestamp_fulltest, options.suffix)
    #print(" ############## options_dut = ",options_dut ," #################")
    ############
    
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
        'BXoffset' : 22,   # was 23
        'gain' : 1,
        'phase' : 7,   #was 7
        # 'calib' : [-1]+[i for i in range(0,4000,100)],
        'calib' : [i for i in range(0,500,50)],
        'injectedChannels' : range(2)
    }
    sipm_injection_scan(i2csocket,daqsocket,clisocket,options.odir,options_dut,injectionConfig,suffix=options.suffix,keepRawData=0,analysis=1)
