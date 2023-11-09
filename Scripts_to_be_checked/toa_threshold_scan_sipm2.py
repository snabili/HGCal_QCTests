import zmq, datetime,  os, subprocess, sys, yaml, glob
from time import sleep
from level0.analyzer import *

import myinotifier, util
import analysis.level0.toa_scan_analysis as analyzer
import zmq_controler as zmqctrl
from nested_dict import nested_dict
import numpy as np
import pandas

def scan(i2csocket, daqsocket, startthr, stopthr, nstep, injectedChannels,calib_dac,odir,keepRawData=0) :
        testName = 'toa_threshold_scan'
        calib_dac_val=calib_dac
        index = 0
        for toa_val in range(startthr, stopthr, nstep) :
                nestedConf = nested_dict()
                for key in i2csocket.yamlConfig.keys() :
                        if key.find('roc_s') == 0 :
                                nestedConf[key]['sc']['ReferenceVoltage']['all']['Toa_vref'] = int(toa_val)
                i2csocket.configure(yamlNode=nestedConf.to_dict())
                i2csocket.sipm_configure_injection(injectedChannels, activate=1, gain=0, calib=calib_dac_val)
                util.acquire_scan(daq=daqsocket)
                chip_params = {'Toa_vref' : toa_val,'injectedChannels':injectedChannels[0]}
                util.saveMetaYaml(odir=odir, i2c=i2csocket, daq=daqsocket, runid=index, testName=testName, keepRawData=keepRawData, chip_params=chip_params)
                index = index + 1
        i2csocket.sipm_configure_injection(injectedChannels, activate=0, gain=0, calib=0) #maybe we should go back to phase 0
        return

def scan_trimToa(i2csocket, daqsocket, odir,chan,calib_dac,keepRawData=0):
        testName = 'toa_trim_scan'
        calib_dac_val=calib_dac
        toa_vals = [i for i in range(0,64,1)]
        # injectedChannels = [chan,chan+18,chan+36,chan+36+18]
        injectedChannels = [chan,chan+36]
        index=0
        for toa_val in toa_vals:
                nestedConf = nested_dict()
                for key in i2csocket.yamlConfig.keys():
                        if key.find('roc_s')==0:
                                nestedConf[key]['sc']['ch'][chan]['trim_toa']=toa_val
                                # nestedConf[key]['sc']['ch'][chan+18]['trim_toa']=toa_val
                                nestedConf[key]['sc']['ch'][chan+36]['trim_toa']=toa_val
                                # nestedConf[key]['sc']['ch'][chan+36+18]['trim_toa']=toa_val
                i2csocket.configure(yamlNode=nestedConf.to_dict())
                i2csocket.sipm_configure_injection(injectedChannels, activate=1, gain=0, calib=calib_dac_val)
                util.acquire_scan(daq=daqsocket)
                chip_params = { 'trim_toa':toa_val, 'injectedChannels':chan}
                util.saveMetaYaml(odir=odir,i2c=i2csocket,daq=daqsocket,runid=index,testName=testName,keepRawData=keepRawData,chip_params=chip_params)
                index+=1
        i2csocket.sipm_configure_injection(injectedChannels, activate=0, gain=0, calib=0) #maybe we should go back to phase 0
        return


def toa_threshold_scan_sipm(i2csocket, daqsocket, clisocket, basedir, device_name, injectionConfig, suffix=''):
        if type(i2csocket) != zmqctrl.i2cController :
                print("ERROR in pedestal_run : i2csocket should be of type %s instead of %s"%(zmqctrl.i2cController,type(i2csocket)))
                sleep(1)
                return

        if type(daqsocket) != zmqctrl.daqController :
                print("ERROR in pedestal_run : daqsocket should be of type %s instead of %s"%(zmqctrl.daqController,type(daqsocket)))
                sleep(1)
                return	

        if type(clisocket) != zmqctrl.daqController :
                print("ERROR in pedestal_run : clisocket should be of type %s instead of %s"%(zmqctrl.daqController,type(clisocket)))
                sleep(1)
                return
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if suffix:
                timestamp = timestamp + "_" + suffix
        odir = "%s/%s/toa_threshold_scan/run_%s/"%(os.path.realpath(basedir), device_name, timestamp)
        os.makedirs(odir)
        
        #####  Setting trim_toa for all channels to 15
        nestedConf = nested_dict()
        for key in i2csocket.yamlConfig.keys():
                if key.find('roc_s')==0:
                        nestedConf[key]['sc']['ch']['all']['trim_toa']=31
                        nestedConf[key]['sc']['cm']['all']['trim_toa']=31
                        nestedConf[key]['sc']['calib']['all']['trim_toa']=31
        i2csocket.configure(yamlNode=nestedConf.to_dict())

	###############################################
        # Configuration:
        calib_dac_0 = 0 #300 #700 #400 #2000
        calib_dac = 700 #300 #700 #400 #2000
        toa_vref_ini = 100
        toa_vref_end = 500
        toa_vref_step = 5
        toa_vref_ini_0 = 10
        toa_vref_end_0 = 100
        toa_vref_step_0 = 2
        chan_range = range(5)
        ###############################################
        ##### Inject calib = 0 to check for ToA triggers with the noise:
        # for ch in range(18):
        # for ch in range(36):
        for ch in chan_range:
                rundir = odir + "calib0_chan_%i" %ch
                os.makedirs(rundir)
                mylittlenotifier = myinotifier.mylittleInotifier(odir=rundir)
                mylittlenotifier.start()
                calibreqA            = 0x10
                BXoffset			= injectionConfig['BXoffset']

                clisocket.yamlConfig['client']['outputDirectory'] = rundir
                clisocket.yamlConfig['client']['run_type'] = "toa_threshold_scan"
                clisocket.yamlConfig['client']['serverIP'] = daqsocket.ip
                clisocket.configure()

                daqsocket.yamlConfig['daq']['active_menu']='calibAndL1A'
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['NEvents']=100
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['bxCalib']=calibreqA
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['bxL1A']=calibreqA+BXoffset
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['lengthCalib']=1
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['lengthL1A']=1
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['prescale']=0
                daqsocket.configure()

                # daqsocket.yamlConfig['daq']['NEvents']='63'
                # daqsocket.enable_fast_commands(0,0,0) ## disable all non-periodic gen L1A sources 
                # daqsocket.l1a_generator_settings(name='A',enable=1,BX=calibreqA,length=1,flavor='CALPULINT',prescale=0,followMode='DISABLE')
                # daqsocket.l1a_generator_settings(name='B',enable=1,BX=calibreqA+BXoffset,length=1,flavor='L1A',prescale=0,followMode='A')
                # daqsocket.configure()

                util.saveFullConfig(odir=odir, i2c=i2csocket, daq=daqsocket, cli=clisocket)
                clisocket.start()
                chan = ch
                # injectedChannels = [chan,chan+18,chan+36,chan+36+18]
                injectedChannels = [chan,chan+36]
                # scan(i2csocket, daqsocket,toa_vref_ini_0, toa_vref_end_0, toa_vref_step_0, injectedChannels,calib_dac_0, rundir,keepRawData=1)
                scan(i2csocket, daqsocket,toa_vref_ini_0, toa_vref_end_0, toa_vref_step_0, injectedChannels,calib_dac_0, rundir,keepRawData=1)
                clisocket.stop()
                mylittlenotifier.stop()
	
        toa_threshold_analyzer = analyzer.toa_scan_analyzer(odir=odir)
        folders = glob.glob(odir+"calib0_chan_*/")
        df_ = []
        for folder in folders:
                files = glob.glob(folder+"/*.root")
                for f in files[:]:
                        df_summary = uproot3.open(f)['runsummary']['summary'].pandas.df()
                        df_.append(df_summary)
        toa_threshold_analyzer.data = pandas.concat(df_)
        toa_threshold_analyzer.makePlot_calib0("calib0")
        # nestedConf = toa_threshold_analyzer.determineToa_vref("calib0")
        # i2csocket.configure(yamlNode= nestedConf.to_dict())
        
        del toa_threshold_analyzer

	###############################################
        # for ch in range(18):
        # for ch in range(36):
        for ch in chan_range:
                rundir = odir + "start_chan_%i" %ch
                os.makedirs(rundir)
                mylittlenotifier = myinotifier.mylittleInotifier(odir=rundir)
                mylittlenotifier.start()
                calibreqA            = 0x10
                BXoffset			= injectionConfig['BXoffset']

                clisocket.yamlConfig['client']['outputDirectory'] = rundir
                clisocket.yamlConfig['client']['run_type'] = "toa_threshold_scan"
                clisocket.yamlConfig['client']['serverIP'] = daqsocket.ip
                clisocket.configure()

                daqsocket.yamlConfig['daq']['active_menu']='calibAndL1A'
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['NEvents']=100
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['bxCalib']=calibreqA
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['bxL1A']=calibreqA+BXoffset
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['lengthCalib']=1
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['lengthL1A']=1
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['prescale']=0
                daqsocket.configure()

                # daqsocket.yamlConfig['daq']['NEvents']='63'
                # daqsocket.enable_fast_commands(0,0,0) ## disable all non-periodic gen L1A sources 
                # daqsocket.l1a_generator_settings(name='A',enable=1,BX=calibreqA,length=1,flavor='CALPULINT',prescale=0,followMode='DISABLE')
                # daqsocket.l1a_generator_settings(name='B',enable=1,BX=calibreqA+BXoffset,length=1,flavor='L1A',prescale=0,followMode='A')
                # daqsocket.configure()

                util.saveFullConfig(odir=odir, i2c=i2csocket, daq=daqsocket, cli=clisocket)
                clisocket.start()
                chan = ch
                # injectedChannels = [chan,chan+18,chan+36,chan+36+18]
                injectedChannels = [chan,chan+36]
                # scan(i2csocket, daqsocket,toa_vref_ini, toa_vref_end, toa_vref_step, injectedChannels,calib_dac, rundir,keepRawData=1)
                scan(i2csocket, daqsocket,toa_vref_ini, toa_vref_end, toa_vref_step, injectedChannels,calib_dac, rundir,keepRawData=1)
                clisocket.stop()
                mylittlenotifier.stop()
	
        toa_threshold_analyzer = analyzer.toa_scan_analyzer(odir=odir)
        folders = glob.glob(odir+"start_chan_*/")
        df_ = []
        for folder in folders:
                files = glob.glob(folder+"/*.root")
                for f in files[:]:
                        df_summary = uproot3.open(f)['runsummary']['summary'].pandas.df()
                        df_.append(df_summary)
        toa_threshold_analyzer.data = pandas.concat(df_)
        toa_threshold_analyzer.makePlot()
        nestedConf = toa_threshold_analyzer.determineToa_vref()
        i2csocket.configure(yamlNode= nestedConf.to_dict())
        
        del toa_threshold_analyzer

        ## Trimmed_dac scan ####################################################
        for ch in chan_range:
        # for ch in range(36):
        # for ch in range(18):
                rundir = odir + "chan_%i" %ch
                os.makedirs(rundir)
                mylittlenotifier = myinotifier.mylittleInotifier(odir=rundir)
                mylittlenotifier.start()
                
                clisocket.yamlConfig['client']['outputDirectory'] = rundir
                clisocket.yamlConfig['client']['run_type'] = "toa_trim_scan"
                clisocket.yamlConfig['client']['serverIP'] = daqsocket.ip
                clisocket.configure()

                daqsocket.yamlConfig['daq']['active_menu']='calibAndL1A'
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['NEvents']=1000
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['bxCalib']=calibreqA
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['bxL1A']=calibreqA+BXoffset
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['lengthCalib']=1
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['lengthL1A']=1
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['prescale']=0
                daqsocket.configure()

                # daqsocket.yamlConfig['daq']['NEvents']='63'
                # daqsocket.enable_fast_commands(0,0,0) ## disable all non-periodic gen L1A sources 
                # daqsocket.l1a_generator_settings(name='A',enable=1,BX=calibreqA,length=1,flavor='CALPULINT',prescale=0,followMode='DISABLE')
                # daqsocket.l1a_generator_settings(name='B',enable=1,BX=calibreqA+BXoffset,length=1,flavor='L1A',prescale=0,followMode='A')
                # daqsocket.configure()

                util.saveFullConfig(odir=rundir, i2c=i2csocket, daq=daqsocket, cli=clisocket)
                clisocket.start()

                scan_trimToa(i2csocket, daqsocket,rundir,ch,calib_dac,keepRawData=1)
                clisocket.stop()
                mylittlenotifier.stop()


        toa_trim_analyzer = analyzer.toa_scan_analyzer(odir=odir)
        folders = glob.glob(odir+"chan_*/")
        df_ = []
        for folder in folders:
                files = glob.glob(folder+"/*.root")
                for f in files[:]:
                        df_summary = uproot3.open(f)['runsummary']['summary'].pandas.df()
                        df_.append(df_summary)
        toa_trim_analyzer.data = pandas.concat(df_)
        toa_trim_analyzer.makePlot_trim()
        toa_trim_analyzer.determineToa_trim()
        i2csocket.update_yamlConfig(fname=odir+'/trimmed_toa.yaml')
        i2csocket.configure(fname=odir+'/trimmed_toa.yaml')

        del toa_trim_analyzer

	###############################################
        for ch in chan_range:
        # for ch in range(36):
        # for ch in range(18):
                rundir = odir + "final_chan_%i" %ch
                os.makedirs(rundir)
                mylittlenotifier = myinotifier.mylittleInotifier(odir=rundir)
                mylittlenotifier.start()

                clisocket.yamlConfig['client']['outputDirectory'] = rundir
                clisocket.yamlConfig['client']['run_type'] = "toa_threshold_scan"
                clisocket.yamlConfig['client']['serverIP'] = daqsocket.ip
                clisocket.configure()

                daqsocket.yamlConfig['daq']['active_menu']='calibAndL1A'
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['NEvents']=1000
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['bxCalib']=calibreqA
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['bxL1A']=calibreqA+BXoffset
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['lengthCalib']=1
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['lengthL1A']=1
                daqsocket.yamlConfig['daq']['menus']['calibAndL1A']['prescale']=0
                daqsocket.configure()

                # daqsocket.yamlConfig['daq']['NEvents']='63'
                # daqsocket.enable_fast_commands(0,0,0) ## disable all non-periodic gen L1A sources 
                # daqsocket.l1a_generator_settings(name='A',enable=1,BX=calibreqA,length=1,flavor='CALPULINT',prescale=0,followMode='DISABLE')
                # daqsocket.l1a_generator_settings(name='B',enable=1,BX=calibreqA+BXoffset,length=1,flavor='L1A',prescale=0,followMode='A')
                # daqsocket.configure()

                util.saveFullConfig(odir=rundir, i2c=i2csocket, daq=daqsocket, cli=clisocket)
                clisocket.start()
                chan = ch
                # injectedChannels = [chan,chan+18,chan+36,chan+36+18]
                injectedChannels = [chan,chan+36]
                scan(i2csocket, daqsocket,toa_vref_ini, toa_vref_end, toa_vref_step, injectedChannels,calib_dac, rundir,keepRawData=1)
                #scan(i2csocket, daqsocket,toa_vref_ini, toa_vref_end, toa_vref_step, injectedChannels,calib_dac, rundir,keepRawData=1)
                clisocket.stop()
                mylittlenotifier.stop()
	
        toa_threshold_analyzer = analyzer.toa_scan_analyzer(odir=odir)
        folders = glob.glob(odir+"final_chan_*/")
        df_ = []
        for folder in folders:
                files = glob.glob(folder+"/*.root")
                for f in files[:]:
                        df_summary = uproot3.open(f)['runsummary']['summary'].pandas.df()
                        df_.append(df_summary)
        toa_threshold_analyzer.data = pandas.concat(df_)
        toa_threshold_analyzer.makePlot("final")
        nestedConf = toa_threshold_analyzer.determineToa_vref("final")
        # i2csocket.update_yamlConfig(yamlNode= nestedConf.to_dict())
        i2csocket.configure(yamlNode= nestedConf.to_dict())

        del toa_threshold_analyzer

        return odir

if __name__ == "__main__" :
        from optparse import OptionParser
        parser = OptionParser()

        parser.add_option("-d", "--dut", dest="dut", help="device under test")

        parser.add_option("-i", "--hexaIP", action="store", dest="hexaIP", help="IP addres of the zynq on the hexactrl board")

        parser.add_option("-f", "--configFile", default="./configs/init.yaml", action="store", dest="configFile", help="initial configuration yaml file")	

        parser.add_option("-o", "--odir", action="store", dest="odir", default='./data', help="output bas directory")

        parser.add_option("--daqPort", action="store", dest="daqPort", default='6000', help="port of the zynq waiting for daq config and commands (configure/start/stop/is_done)")

        parser.add_option("--i2cPort", action="store", dest="i2cPort", default='5555', help="port of the zynq waiting for I2C config and commands (initialize/configure/read_pwr,read/measadc)")

        parser.add_option("--pullerPort", action="store", dest="pullerPort", default='6001', help="port of the client PC (loccalhost for the moment) waiting for daq config and commands (configure/start/stop)")

        (options, args) = parser.parse_args()
        print (options)

        daqsocket = zmqctrl.daqController(options.hexaIP, options.daqPort, options.configFile)
        clisocket = zmqctrl.daqController("localhost", options.pullerPort, options.configFile)
        i2csocket = zmqctrl.i2cController(options.hexaIP, options.i2cPort, options.configFile)
        
        phase =1 #i2csocket.yamlConfig['roc_s0']['sc']['Top'][0]['phase_ck']
        nestedConf = nested_dict()
        for key in i2csocket.yamlConfig.keys():
                if key.find('roc_s')==0:
                        nestedConf[key]['sc']['Top'][0]['phase_ck']=phase
        i2csocket.update_yamlConfig(yamlNode= nestedConf.to_dict())
        i2csocket.configure(yamlNode=nestedConf.to_dict())
        i2csocket.resettdc()	# Reset MasterTDCs

        l1a_offset = i2csocket.yamlConfig['roc_s0']['sc']['DigitalHalf'][0]['L1Offset']
        if phase in range(5):
                l1_val = 1
        else:
                l1_val = 0
        BXoffset = l1a_offset + 11 + l1_val  ## Calib_offset = 11
        print(BXoffset)
        injectionConfig = {
                'BXoffset' : BXoffset
        }
	
        # i2csocket.configure()
        toa_threshold_scan_sipm(i2csocket, daqsocket, clisocket, options.odir, options.dut, injectionConfig, suffix='')
	
