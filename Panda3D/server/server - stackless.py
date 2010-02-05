import socket
import threading
import stackless
import SocketServer
import time
import select
import ConfigParser
import json
import logging
import cPickle
import net
from Queue import *


LOG_FILENAME = 'debug.log'
logging.basicConfig(filename=LOG_FILENAME,level=logging.DEBUG)


#Marshalling
class NetHandler(SocketServer.StreamRequestHandler):
    def w(self,data,noCR = 0):
        data = cPickle.dumps(data)
        logging.debug(len(data))
        data = '\x00'+data+'\xff'
        self.request.sendall(data)
        
    def wr(self, text):
        self.request.sendall(text)
        
    def handle(self):
        self.request.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) #turn off nagle
        logging.debug("Client Connected")
        self.player = Player(self)
        players[self.client_address] = self.player
        self.request.setblocking(0)
        self.data = ''
        self.t = stackless.tasklet(self.parseData)()
    
    # this is where the tasklets need to be
    def parseData(self):
        while(1):
            self.data += self.request.recv(1024)
            self.end = self.data.find('\xFF')
            if self.end: 
                message = False
                try:
                    message = cPickle.loads(self.data[:self.end].strip('\xFF\x00'))
                except:
                    logging.warning("Unable to parse:  %s" % (self.data[:self.end].strip('\xFF\x00')))
                if message:
                    try:
                        message = RPCMessage(self.player,message)
                        q.send(message)
                    except:
                        logging.warning("Invalid data format: %s" % (message))
                     
                self.data = self.data[self.end+1:]
            stackless.schedule()
        
class NetMarshall(SocketServer.TCPServer):
    #def handle_error(self, request, client_address):
        #print("Some shit went down from %s" % (client_address,))
    def stackless_serve(self, poll_interval=0.5):
        while self.__serving:
            # XXX: Consider using another file descriptor or
            # connecting to the socket to wake this up instead of
            # polling. Polling reduces our responsiveness to a
            # shutdown request and wastes cpu at all other times.
            r, w, e = select.select([self], [], [], poll_interval)
            if r:
                self._handle_request_noblock()
            stackless.schedule()
            
    def serve_forever(self, poll_interval=0.5):
        self.__serving = True
        stackless.tasklet(self.stackless_serve)(poll_interval)                
        stackless.run()
       
    def close_request(self, request):
        request.close()
        #del players[client_address]
        
class RPCMessage:
    def __init__(self, player, message):
        self.op = message['op']
        self.data = message['data']
        self.ops = {'chat':self.chat,'login':self.login,'seed':self.seed}
        self.player = player
        
    def login(self):
        names = [] 
        self.player.name = self.data
        #doh this could have gone better
        for player in players:
            names.append(players[player].name)
        for player in players:
            players[player].net.w({'op':'list','data':names})
            
    # reply to the clients update with the servers
    def seed(self):
        # in the future, dump the zone(s) that the player is in/near... or just dump the surrounding zones
        self.player.net.w({'op':'seed','data':world.zones[0].dump()})
        
    def chat(self):
        for player in players:
            players[player].net.w({'op':'chat','data':{'name':self.player.name,'message':self.data}})
        
    def execute(self):
        if self.op in self.ops:
            self.ops[self.op]()
        else:
            logging.warning('Unable to find op %s' % [self.op])
            
class Player:
    character = 0
    room = -1
    x = 0
    y = 0
    z = 0
    
    def __init__(self,net):
        self.net = net
        
    def disconnect(self):
        if self.character:
            self.logout()
            
    def logout(self):
        if self.room:
            rooms[self.room].leave(self)
        self.character.loggedIn = 0
        self.character = 0

class World:
    def __init__(self):
        self.zones = []
        self.seed()
    
    def seed(self):
        zoneCount = int(cfg.get('world','zones'))
        for i in range(zoneCount):
            self.zones.append(Zone(i,True))
            
class Zone:
    def __init__(self, id, seed):
        self.blocks = {}
        self.id = id
        self.objects = []
        if seed:
            self.seed()
    
    # doesn't include mountain generation or anything yet xD
    def seed(self):
        self.size = int(cfg.get("zone","size"))
        self.depth = int(cfg.get("zone","depth"))
        for x in range(self.size):
            for y in range(self.size):
                for z in range(self.depth):
                    self.blocks[(x,y,z)] = Block((x, y, z))
            
    # only dump certain things for the net
    def dump(self):
        objects_dump = []
        for i in self.objects:
            objects_dump.append(self.objects[i].dump())
        blocks_dump = []
        for i in self.blocks:
            blocks_dump.append(self.blocks[i].dump())
        return {'id':self.id, 'objects':objects_dump, 'blocks':blocks_dump}

class Block:
    def __init__(self, pos):
        self.pos = pos
        self.type = "grass"
        pass
    def dump(self):
        return {'pos':self.pos,'type':self.type}
class Object:
    def __init__(self, id, type):
        self.id = id
        self.type = type
        
    def dump(self):
        return {'id':self.id,'type':self.type}
        
#Startup Sequence
if __name__ == "__main__":
    cfg = ConfigParser.SafeConfigParser()
    cfg.read('game.cfg')
    
    HOST, PORT = cfg.get('net','host'), int(cfg.get('net','port')) #default telnet port is 23
    #Persistence... the only persistence in this whole thing
    players = {}

    q = stackless.channel()
    world = World()
    server = NetMarshall(('', PORT), NetHandler)
    
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.setDaemon(True)
    server_thread.start()

    print "Server Running"
    while(1):
        rpc = q.receive() # block the shit out of this
        rpc.execute()
    




