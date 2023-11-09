import zmq
import yaml
from time import sleep
from nested_dict import nested_dict

def merge(a, b, path=None):
    "merges b into a"
    if path is None: path = []
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge(a[key], b[key], path + [str(key)])
            else:
                a[key] = b[key]
        else:
            a[key] = b[key]
    return a

class zmqController:
    def __init__(self,ip,port,fname="configs/init.yaml"):
        context = zmq.Context()
        self.ip=ip
        self.port=port
        self.socket = context.socket( zmq.REQ )
        self.socket.connect("tcp://"+str(ip)+":"+str(port))
        with open(fname) as fin:
            self.yamlConfig=yaml.safe_load(fin)

    def reset(self):
        self.socket.close()
        context = zmq.Context()
        self.socket = context.socket( zmq.REQ )
        self.socket.connect("tcp://"+str(self.ip)+":"+str(self.port))

    def update_yamlConfig(self,fname="",yamlNode=None):
        if yamlNode:
            config=yamlNode
        elif fname :
            with open(fname) as fin:
                config=yaml.safe_load(fin)
        else:
            print("ERROR in %s"%(__name__))
        merge(self.yamlConfig,config)

    def initialize(self,fname="",yamlNode=None):
        self.socket.send_string("initialize",zmq.SNDMORE)
        if yamlNode:
            config=yamlNode
        elif fname :
            with open(fname) as fin:
                config=yaml.safe_load(fin)
        else:
            config = self.yamlConfig
        self.socket.send_string(yaml.dump(config))
        rep = self.socket.recv()
        print("returned status (from init) = %s"%rep)
        # return rep

    def configure(self,fname="",yamlNode=None):
        self.socket.send_string("configure",zmq.SNDMORE)
        if yamlNode:
            config=yamlNode
        elif fname :
            with open(fname) as fin:
                config=yaml.safe_load(fin)
        else:
            config = self.yamlConfig
        self.socket.send_string(yaml.dump(config))
        rep = self.socket.recv_string()
        print("returned status (from config) = %s"%rep)


class i2cController(zmqController):    
    def __init__(self,ip,port,fname="configs/init.yaml"):
        super(i2cController, self).__init__(ip,port,fname)
        self.maskedDetIds=[]
        					
    def read_config(self,yamlNode=None):
        # only for I2C server
        self.socket.send_string("read",zmq.SNDMORE)
        # rep = self.socket.recv_string()
        if yamlNode:
            self.socket.send_string( yaml.dump(yamlNode) )
        else:
            self.socket.send_string( "" )
        yamlread = yaml.safe_load( self.socket.recv_string() )
        return( yamlread )
		
    def read_pwr(self):
        ## only valid for hexaboard/trophy systems
        self.socket.send_string("read_pwr")
        rep = self.socket.recv_string()
        pwr = yaml.safe_load(rep)
        return( pwr )
        
    def resettdc(self):
        self.socket.send_string("resettdc")
        rep = self.socket.recv_string()
        return( yaml.safe_load(rep) )
       
    def set_gbtsca_dac(self,dac,val):
        self.socket.send_string("set_gbtsca_dac "+str(dac)+" "+str(val))
        return self.socket.recv_string()

    def read_gbtsca_dac(self,dac):
        self.socket.send_string("read_gbtsca_dac "+str(dac))
        dacval = self.socket.recv_string()
        return(dacval)

    def read_gbtsca_adc(self,channel):
        self.socket.send_string("read_gbtsca_adc "+str(channel))
        adcval = self.socket.recv_string()
        return(adcval)
 
    def read_gbtsca_gpio(self):
        self.socket.send_string("read_gbtsca_gpio")
        gpiovals=self.socket.recv_string()
        return(gpiovals)   

    def set_gbtsca_gpio_direction(self,direction):
        self.socket.send_string("set_gbtsca_gpio_direction "+str(direction))
        return(self.socket.recv_string())

    def get_gbtsca_gpio_direction(self):
        self.socket.send_string("get_gbtsca_gpio_direction")
        gpio_directions = self.socket.recv_string()
        return gpio_directions

    def set_gbtsca_gpio_vals(self,vals,mask):
        self.socket.send_string("set_gbtsca_gpio_vals "+str(vals)+" "+str(mask))
        return(self.socket.recv_string())

    def measadc(self,yamlNode):
        ## only valid for hexaboard/trophy systems
        self.socket.send_string("measadc",zmq.SNDMORE)
        # rep = self.socket.recv_string()
        # if rep.lower().find("ready")<0:
        #     print(rep)
        #     return
        if yamlNode:
            config=yamlNode
        else:
            config = self.yamlConfig
        self.socket.send_string(yaml.dump(config))
        rep = self.socket.recv_string()
        adc = yaml.safe_load(rep)
        return( adc )

    def addMaskedDetId(self,detid):
        self.maskedDetIds.append(detid)

    def rmMaskedDetId(self,detid):
        self.maskedDetIds.remove(detid)

    def sipm_configure_injection(self,injectedChannels, activate=0, gain=0, phase=None, calib_dac=0):
        nestedConf = nested_dict()
        for key in self.yamlConfig.keys():
            if key.find('roc_s')==0:
                nestedConf[key]['sc']['ReferenceVoltage']['all']['IntCtest'] = 0
                nestedConf[key]['sc']['ReferenceVoltage']['all']['choice_cinj'] = 0
                if gain < 2:
                    nestedConf[key]['sc']['ReferenceVoltage']['all']['cmd_120p'] = gain
                if calib_dac == -1:
                    nestedConf[key]['sc']['ReferenceVoltage']['all']['Calib_2V5'] = 0
                else:
                    nestedConf[key]['sc']['ReferenceVoltage']['all']['Calib_2V5'] = calib_dac
                if not None==phase: # no default phase, we don't change when not set
                    nestedConf[key]['sc']['Top']['all']['phase_ck'] = phase
                if not None==injectedChannels:
                    for injectedChannel in injectedChannels:
                        nestedConf[key]['sc']['ch'][injectedChannel]['HighRange'] = activate
                        nestedConf[key]['sc']['ch'][injectedChannel]['LowRange'] = 0
        self.configure(yamlNode=nestedConf.to_dict())
        if not None==phase:
            self.resettdc()	# Reset MasterTDCs

    def configure_injection(self,injectedChannels, activate=0, gain=0, phase=None, calib_dac=0):
        nestedConf = nested_dict()
        for key in self.yamlConfig.keys():
            if key.find('roc_s')==0:
                if calib_dac == -1:
                    nestedConf[key]['sc']['ReferenceVoltage']['all']['IntCtest']=0
                else:
                    nestedConf[key]['sc']['ReferenceVoltage']['all']['IntCtest'] = activate
                    nestedConf[key]['sc']['ReferenceVoltage']['all']['Calib'] = calib_dac
                if not None==phase: # no default phase, we don't change when not set
                    nestedConf[key]['sc']['Top']['all']['phase_ck'] = phase
                for injectedChannel in injectedChannels:
                    nestedConf[key]['sc']['ch'][injectedChannel]['LowRange'] = 0
                    nestedConf[key]['sc']['ch'][injectedChannel]['HighRange'] = 0
                    if gain==0:
                        nestedConf[key]['sc']['ch'][injectedChannel]['LowRange'] = activate
                    else:
                        nestedConf[key]['sc']['ch'][injectedChannel]['HighRange'] = activate
        self.configure(yamlNode=nestedConf.to_dict())
        if not None==phase:
            self.resettdc()	# Reset MasterTDCs

class daqController(zmqController):
    def start(self):
        status="none"
        while status.lower().find("running")<0: 
            self.socket.send_string("start")
            status = self.socket.recv_string()
            print(status)

    def is_done(self):
        self.socket.send_string("status")
        status = self.socket.recv_string()
        if status.lower().find("configured")<0:
            return False
        else:
            return True

    def delay_scan(self):
        # only for daq server to run a delay scan
        rep=""
        while rep.lower().find("delay_scan_done")<0: 
            self.socket.send_string("delayscan")
            rep = self.socket.recv_string()
        print(rep)
	
    def stop(self):
        self.socket.send_string("stop")
        rep = self.socket.recv_string()
        print(rep)
        
    def enable_fast_commands(self,random=0,external=0,sequencer=0,ancillary=0):
        self.yamlConfig['daq']['l1a_enables']['random_l1a']         = random
        self.yamlConfig['daq']['l1a_enables']['external_l1as']      = external
        self.yamlConfig['daq']['l1a_enables']['block_sequencer']    = sequencer

    def l1a_generator_settings(self,name='A',enable=0x0,BX=0x10,length=43,flavor='L1A',prescale=0,followMode='DISABLE'):
        for gen in self.yamlConfig['daq']['l1a_generator_settings']:
            if gen['name']==name:
                gen['BX']         = BX
                gen['enable']     = enable
                gen['length']     = length
                gen['flavor']     = flavor
                gen['prescale']   = prescale
                gen['followMode'] = followMode
        
    def l1a_settings(self,bx_spacing=43,external_debounced=0,ext_delay=0,prescale=0,log2_rand_bx_period=0):#,length=43
        self.yamlConfig['daq']['l1a_settings']['bx_spacing']          = bx_spacing
        self.yamlConfig['daq']['l1a_settings']['external_debounced']  = external_debounced
        # self.yamlConfig['daq']['l1a_settings']['length']              = length
        self.yamlConfig['daq']['l1a_settings']['ext_delay']           = ext_delay
        self.yamlConfig['daq']['l1a_settings']['prescale']            = prescale
        self.yamlConfig['daq']['l1a_settings']['log2_rand_bx_period'] = log2_rand_bx_period
        
    def ancillary_settings(self,bx=0x10,prescale=0,length=100):
        self.yamlConfig['daq']['ancillary_settings']['bx']       = bx
        self.yamlConfig['daq']['ancillary_settings']['prescale'] = prescale
        self.yamlConfig['daq']['ancillary_settings']['length']   = length
            
