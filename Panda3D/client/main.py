import socket
from Queue import *
import ConfigParser
import logging
import threading
import time
import cPickle
import sys
from cube import *
import direct.directbase.DirectStart
from direct.gui.DirectGui import *
from direct.gui.OnscreenText import OnscreenText
from direct.gui.OnscreenImage import OnscreenImage
from pandac.PandaModules import *

LOG_FILENAME = 'debug.log'
logging.basicConfig(filename=LOG_FILENAME,level=logging.DEBUG)

class NetClient():
    def __init__(self, HOST, PORT):
        self.s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) #turn off nagle
        self.host = HOST
        self.port = PORT
        
        #startup handler
    def connect(self):
        try:
            logging.debug("Connecting to server...")
            self.s.connect((self.host, self.port))
        except socket.error,msg:
            print msg
            sys.exit(0)
            
        self.net_thread = threading.Thread(target=self.net)
        self.net_thread.setDaemon(True)
        self.net_thread.start()

    def net(self):
        data = ''
        end = -1
        while(1):
            while(end == -1):
                data += self.s.recv(1024)#blocking, convert to recv until 0xFF
                end = data.find('\xFF')
                logging.debug(data)
            if not data: break
            
            message = False
            try:
                message = cPickle.loads(data[:end].strip('\xFF\x00'))
            except:
                logging.warning("Unable to parse:  %s" % (data[:end].strip('\xFF\x00')))
            
            if message:
                message = RPCMessage(message)
                # not sure about executing this here... 
                message.execute()
          
                 
            data = data[end+1:]
            end = data.find('\xFF')
            
    def w(self,data):
        logging.debug("Sent: %s" % data)
        self.s.sendall('\x00'+cPickle.dumps(data)+'\xFF')
        
class RPCMessage():
    def __init__(self,message):
        self.op = message['op']
        self.ops = {'seed':self.seed}
        self.data = message['data']
        logging.debug("Recieved: %s" % (message['op']))
        
    def execute(self):
        if self.op in self.ops:
            self.ops[self.op]()
        else:
            logging.warning('Unable to find op %s' % [self.op])
    def seed(self):
        game.seed(self.data)

class MainMenu():
    def __init__(self):
        net.connect()
        self.entry = DirectEntry(text="",scale=.05,pos=(0,0,.1),initialText="Enter Name",focus=1,focusInCommand=self.clear)
        self.submit = DirectButton(text = "Login",scale=.05,pos=(.5,0,0),command=self.startGame)

    def clear(self):
        self.entry.enterText('')
        
    def startGame(self):
        net.w({'op':'login','data':{'name':self.entry.get(True)}})
        game.start()
        self.destroy()
 
    def destroy(self):
        self.entry.destroy()
        self.submit.destroy()

class LoadingScreen():
    def __init__(self):
        self.loading = OnscreenImage(image='data/menu/loading.png',pos = (0,0,0))
        
    def destroy(self):
        self.loading.destroy()

class Block():
    def __init__(self, data):
        print "Created node at %s" % data
        texture = loader.loadTexture("textures/grid.png")
        self.node = render.attachNewNode(makeCube(1,"cube"))
        self.node.setPos(data['pos'])
        self.node.setTexture(texture)
        self.node.setColor(0,1,0,1)
        self.node.reparentTo(render)
        base.camera.lookAt(self.node)
        # create onscreen block
        pass
    
    def destroy(self):
        pass
    
class GameWorld():
    blocks = {}
    
    def __init__(self):
        self.ready = False
    
    def start(self):
        base.oobe()
        # Setup loading screen...
        self.loading = LoadingScreen()
        
        self.amb = AmbientLight('alight')
        self.amb.setColor(VBase4(1, 1, 1, 1))
        render.setLight(render.attachNewNode(self.amb))
        
        # Request World Data and Set it Up
        net.w({'op':'seed','data':''})
        # Destroy loading screen and start ticking.
        #while(not self.ready):
        #    time.sleep(1)
        self.loading.destroy()
        taskMgr.add(self.tick, "Game World Tick")
    
    def seed(self, data):
        self.ready = True
        for i in data['blocks']:
            self.blocks[i['pos']] = Block(i)
        
    # handles any gameworld actions
    def tick(self, etc):
        pass        
    
cfg = ConfigParser.SafeConfigParser()
cfg.read('game.cfg')
net = NetClient(cfg.get('net','host'), int(cfg.get('net','port')))
menu = MainMenu()
game = GameWorld()
run()