import pyinotify,time
import glob, re, os 
import subprocess
import threading
import yaml

class EventHandler(pyinotify.ProcessEvent):
    def __init__(self):
        print("initialize inotifier handler")
        self.inputRAW = []
        self.inputMetaYaml = []

        self.__lock = threading.Lock()  
        self.__interrupt = False
        self.threads=[]
        self.master_thread=None

    def process_IN_CLOSE_WRITE(self, event):
        print("WRITING:", event.pathname)
        with self.__lock:
            if event.pathname.find('.raw')>0:
                self.inputRAW.append(event.pathname)
            elif event.pathname.find('.yaml')>0:
                with open(event.pathname) as fin:
                    yamlnode = yaml.safe_load(fin)
                    if 'metaData' in yamlnode.keys():
                        self.inputMetaYaml.append(event.pathname)
            # elif event.pathname.find('.root')>0:
        
    def __run_unpacker(self,fin,fout,fmeta,flog):
        cmd='unpack -i ' + fin + ' -o ' + fout + ' -M ' + fmeta
        with open(flog,'w') as logout:
            subprocess.check_output( cmd, shell=True,stderr=logout  )

    def __unpacker_server(self):
        while self.__interrupt==False:
            if len(self.inputRAW)>0 and len(self.inputMetaYaml)>0:
                fmeta = self.inputMetaYaml[0]
                fin = re.split('.yaml',fmeta)[0]
                fout = fin + '.root'
                flog = fin + '.log'
                fin = fin + '.raw'
                if not fin in self.inputRAW:
                    continue
                else:
                    x = threading.Thread( target = self.__run_unpacker, args=(fin,fout,fmeta,flog) )
                    x.start()
                    self.threads.append(x)
                    with self.__lock:
                        self.inputRAW.remove(fin)
                        self.inputMetaYaml.remove(fmeta)
            
            
    def startUnpackerServer(self):
        with self.__lock:
            self.__interrupt=False
        self.master_thread = threading.Thread( target = self.__unpacker_server )
        self.master_thread.start()

    def stopUnpackerServer(self):
        while True:
            if len(self.inputRAW)>0 or len(self.inputMetaYaml)>0:
                # time.sleep(0.5)
                continue
            with self.__lock:
                self.__interrupt=True
            for x in self.threads:
                x.join()
            self.master_thread.join()
            break


class mylittleInotifier:
    def __init__(self,odir="./"):
        self.odir = odir
        self.handler = EventHandler()

        self.wm = pyinotify.WatchManager()  # Watch Manager
        self.mask = pyinotify.IN_CLOSE_WRITE # watched events
        self.notifier = pyinotify.ThreadedNotifier(self.wm, self.handler)

    def start(self):
        self.notifier.start()
        wdd = self.wm.add_watch(self.odir, self.mask, rec=False)
        self.handler.startUnpackerServer()

    def stop(self):
        self.handler.stopUnpackerServer()
        self.notifier.join(timeout=.1)# wait half a second to let handler and analyzer processing last run
        self.notifier.stop()
