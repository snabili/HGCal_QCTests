import zmq, datetime,  os, subprocess, sys, yaml, glob

import myinotifier,util
import analysis.level0.pedestal_run_analysis as analyzer
import zmq_controler as zmqctrl
from nested_dict import nested_dict 

def pedestal_run(i2csocket,daqsocket, clisocket, basedir,device_name):
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
    testName = "pedestal_run"
    odir = "%s/%s/pedestal_run/run_%s/"%( os.path.realpath(basedir), device_name, timestamp )
    os.makedirs(odir)

    #start the zmq_client # ADDED BY MALINDA 20-sept-21
    #zmq_client = subprocess.Popen(["zmq-client"])
    #######

    mylittlenotifier = myinotifier.mylittleInotifier(odir=odir)
    mylittlenotifier.start()
    
    clisocket.yamlConfig['global']['outputDirectory'] = odir
    clisocket.yamlConfig['global']['run_type'] = testName
    clisocket.yamlConfig['global']['serverIP'] = daqsocket.ip
    clisocket.configure()
    daqsocket.yamlConfig['daq']['NEvents']='10000'
    daqsocket.enable_fast_commands(random=1)
    daqsocket.l1a_settings(bx_spacing=45)
    daqsocket.configure()
    	
    
    # nestedConf = nested_dict()
    # for key in i2csocket.yamlConfig.keys():
    #     if key.find('roc_s')==0:
    #         for ch in range(0,36):
    #             nestedConf[key]['sc']['ch'][ch]['Channel_off']=1
    #         nestedConf[key]['sc']['calib'][0]['Channel_off']=1
    # i2csocket.update_yamlConfig(yamlNode=nestedConf.to_dict())
    # i2csocket.configure()

    util.saveFullConfig(odir=odir,i2c=i2csocket,daq=daqsocket,cli=clisocket)
    util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,runid=0,testName=testName,keepRawData=1,chip_params={})

    util.acquire(daq=daqsocket, client=clisocket)
    mylittlenotifier.stop()
    
    print("before analyser")
    ped_analyzer = analyzer.pedestal_run_analyzer(odir=odir)
    print("after analyser")
    files = glob.glob(odir+"/*.root")
    	
    for f in files:
        print("files:",f)
        ped_analyzer.add(f)
    
    print("before merge")
    ped_analyzer.mergeData()
    print("before makeplots")
    ped_analyzer.makePlots()
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
    
    
    (options, args) = parser.parse_args()
    print(options)
    
    daqsocket = zmqctrl.daqController(options.hexaIP,options.daqPort,options.configFile)
    clisocket = zmqctrl.daqController("localhost",options.pullerPort,options.configFile)
    i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)
    
    print("Dac A value is",i2csocket.read_gbtsca_dac("A"))
    i2csocket.set_gbtsca_dac("A",0xFF)
    print("Dac A value is now",i2csocket.read_gbtsca_dac("A"))
    print("ADC Channel 1 is",i2csocket.read_gbtsca_adc(0x1))
    print("GPIO directions are",hex(int(i2csocket.get_gbtsca_gpio_direction())))
    print("GPIO values are",hex(int(i2csocket.read_gbtsca_gpio())))
    i2csocket.set_gbtsca_gpio_direction(0xf0f0)
    i2csocket.set_gbtsca_gpio_vals(0xffff,0xf000)
    print("GPIO directions are",hex(int(i2csocket.get_gbtsca_gpio_direction())))
    print("GPIO values are",hex(int(i2csocket.read_gbtsca_gpio())))



   



   

