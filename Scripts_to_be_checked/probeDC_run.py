""" References from HGCROCv2 Datasheet:
p.45: ProbeDC1/2 codes and typical values. """

import zmq, datetime,  os, subprocess, sys, yaml, glob
import zmq_controler as zmqctrl
from nested_lookup import nested_delete, nested_update
from itertools import chain
from nested_dict import nested_dict
import numpy as np
from time import sleep

def scan_probedc(i2csocket, dc_names, dc_range, probe_name, keithley_h0=None, keithley_h1=None):
    ret = nested_dict()
    nestedConf = nested_dict()
    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            nestedConf[key]['sc']['ReferenceVoltage']['all']['probe_dc'] = 0
    for dc_value, name in zip(dc_range, dc_names):
        cfg = nested_update(nestedConf.to_dict(), key=probe_name, value=dc_value, in_place=True)
        print (cfg)
        if keithley_h0 and keithley_h1:  # Single-chip
            i2csocket.configure(yamlNode=cfg)
            keithley_h0.trigger()
            keithley_h1.trigger()
            # give keithleys time to measure before reconfiguring ROC.
            sleep(0.3)  # For using one adapter + Multi-con cable (MODE 1)
            # sleep(0.1)  # For using two adapters (MODE 2)
        else:  # Multi-chip
            ret_cfg = i2csocket.measadc(yamlNode=cfg)
            ret["node"][name] = ret_cfg
    return ret.to_dict()

def probeDC_run(i2csocket, basedir, device_name, prologixIP=""):
    if type(i2csocket) != zmqctrl.i2cController:
        print( "ERROR in probeDC_run : i2csocket should be of type %s instead of %s"%(zmqctrl.i2cController,type(i2csocket)) )
        sleep(1)
        return
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    testName = "probedc_run"
    odir = "%s/%s/probedc_run/run_%s/"%( os.path.realpath(basedir), device_name, timestamp )
    os.makedirs(odir)

    initial_full_config={}
    for key in i2csocket.yamlConfig.keys():
        if key.find('roc_s')==0:
            initial_full_config[key] = i2csocket.yamlConfig[key]

    ################      HGCROC3     ############################
    dc_range = range(32)
    dc_name = "probe_dc"

    dc1_names = ["vbi_pa", "vbm_pa", "vbm2_pa", "vbm3_pa", "vbo_pa", "vb_inputdac",
            "vbi_discri_tot", "vbm_discri_tot", "vbo_discri_tot", "vbi_discri_toa",
            "vcasc_discri_toa", "vbm1_discri_toa", "vbm2_discri_toa", "vbo_discri_toa",
            "EXT_REF_TDC", "probe_VrefCf", "vcn", "VD_FTDC_P_EXT", "VD_CTDC_P_EXT",
            "probe_VrefPa", "vcp", "VD_FTDC_N_EXT", "VD_CTDC_N_EXT", "vb_hyst_tot", "vbi_itot_neg",
            "vbi_itot_pos", "vbiN_sk", "vbiP_sk", "vbFCN_sk", "vbFCP_sk", "vbiN_noinv", "vbiP_noinv"]
                
    dc2_names = ["vbFCN_noinv", "vbFCP_noinv", "vbiN_inv", "vbip_inv", "vbFCN_inv", "vbFCP_inv", "vbiN_noinv_buf",
                 "vbiP_noinv_buf", "vbFCN_noinv_buf", "vbFCP_noinv_buf", "vbiN_inv_buf",
                 "vbFCP_inv_buf",  "vbiP_inv_buf", "vbFCN_inv_buf", "vb_5bdac_out_inv", "vb_5bdac_tot", "vb_5bdac_toa",
                 "vcm_0p6_inv", "vcm_0p6_noinv", "vref_adc", "vcm_adc", "Vref_sk", "Vref_noinv", "Vref_inv", "Vref_tot", "Vref_toa",
                 "vbg_1v", "probe_center", "ibi_ref_adc", "ibo_ref_adc", "probe_vddd", "probe_vdda"]

    roc_config = {k: v for k, v in i2csocket.yamlConfig.items() if k.startswith('roc')}
    single_chip = True if len(roc_config)==1 else False
    if single_chip:
        from PrologixEthernetAdapter import PrologixEthernetAdapter
        from keithley2000_with_scanner_card import Keithley2000WithScannerCard

        ### MODE 1: One GPIB-ETH adapter + Multi-connector cable
        adapter = PrologixEthernetAdapter(prologixIP)
        j4 = Keithley2000WithScannerCard(adapter.gpib(14))
        j7 = Keithley2000WithScannerCard(adapter.gpib(16))

        ### MODE 2: Two GPIB-ETH adapters with separate IPs
        # j4_adapter = PrologixEthernetAdapter('128.141.89.187', address=21)
        # j7_adapter = PrologixEthernetAdapter('128.141.89.204', address=24)
        # j4 = Keithley2000WithScannerCard(j4_adapter)
        # j7 = Keithley2000WithScannerCard(j7_adapter)

        for i in range(2):
            nestedConf = nested_dict()
            for key in i2csocket.yamlConfig.keys():
                if key.find('roc_s')==0:
                    nestedConf[key]['sc']['ReferenceVoltage']['all']['probe_dc1']=i+1
                    nestedConf[key]['sc']['ch'][10]['probe_inv']=1
                    nestedConf[key]['sc']['ch'][10]['probe_noinv']=1
                    nestedConf[key]['sc']['ch'][46]['probe_inv']=1
                    nestedConf[key]['sc']['ch'][46]['probe_noinv']=1
            print(nestedConf)
            i2csocket.update_yamlConfig(yamlNode=nestedConf.to_dict())
            i2csocket.configure()
            if i == 0:
                probe_points = dc1_names
            else:
                probe_points = dc2_names
            buf_size = len(dc_range)
            print("buf_size ", buf_size)
            j4.config_buffer(buf_size)
            j7.config_buffer(buf_size)

            # Probe_dc1
            print("channel is ", dc_name)
            j4.channel = dc_name
            j7.channel = dc_name
            print("Taking data")
            scan_probedc(i2csocket, probe_points, dc_range, dc_name, keithley_h0=j4, keithley_h1=j7)

            print("Start waiting for buffer")
            j4.wait_for_buffer()
            j7.wait_for_buffer()
            print("Stop waiting for buffer")

            #dc1, dc2 = len(dc_range), 3
            #j4_splits = np.split(j4.buffer_data, [dc1, dc2])
            #j7_splits = np.split(j7.buffer_data, [dc1, dc2])
            #dc_splits = np.split(probe_points,   [dc1, dc2])
            j4_ret = j4.buffer_data
            j7_ret = j7.buffer_data

            ret = nested_dict()
            for name, h0_pt, h1_pt in zip(probe_points, j4_ret, j7_ret):
                ret["node"][str(name)]["half"][0] = float(abs(h0_pt))
                ret["node"][str(name)]["half"][1] = float(abs(h1_pt))

            ret1 = ret.to_dict()

            # deconfigure probeDC measurement via J4/J7
            nestedConf = nested_dict()
            for key in i2csocket.yamlConfig.keys():
                if key.find('roc_s')==0:
                    nestedConf[key]['sc']['ReferenceVoltage']['all']['probe_dc1']=0
                    nestedConf[key]['sc']['ReferenceVoltage']['all']['probe_dc']=0
                    nestedConf[key]['sc']['ch'][10]['probe_inv']=0
                    nestedConf[key]['sc']['ch'][10]['probe_noinv']=0
                    nestedConf[key]['sc']['ch'][46]['probe_inv']=0
                    nestedConf[key]['sc']['ch'][46]['probe_noinv']=0
            print(nestedConf)
            i2csocket.update_yamlConfig(yamlNode=nestedConf.to_dict())
            i2csocket.configure()

            fname = "dc%i_probe" %(i+1)
            with open(odir + "/" + fname  + ".yaml", "w") as fout:
                yaml.dump(ret1, fout)


    else:  # Multi-chip 
        ret1 = scan_probedc(i2csocket, dc1_names, dc1_range, dc1_name)
        ret2 = scan_probedc(i2csocket, dc2_names, dc2_range, dc2_name)


def main():
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
    
    parser.add_option("--prologixIP",
                      action="store", dest="prologixIP",default='0.0.0.0',
                      help="IP address of the prologix GPIB to ethernet connector (mandatory only when running with the Keithley multimeter for v2 single ROC boards)")

    parser.add_option("--i2cPort",
                      action="store", dest="i2cPort",default='5555',
                      help="port of the zynq waiting for I2C config and commands (initialize/configure/read_pwr,read/measadc)")
    
    
    (options, args) = parser.parse_args()
    print(options)
    
    i2csocket = zmqctrl.i2cController(options.hexaIP,options.i2cPort,options.configFile)
    
    i2csocket.configure()
    probeDC_run(i2csocket,options.odir,options.dut,options.prologixIP)

if __name__ == "__main__":
	main()
