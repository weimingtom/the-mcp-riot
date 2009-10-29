import socket
import threading
import socketserver
import time
from inspect import getargspec
import configparser
from queue import *

#Marshalling
class NetHandler(socketserver.StreamRequestHandler):
    def w(self,text,noCR = 0):
        if noCR:
            self.wfile.write(bytes(text,'ascii'))
        else:
            self.wfile.write(bytes(text+"\n\r::",'ascii'))
            
    def handle(self):
        self.w(cfg.get('strings','welcome'));
        self.w(cfg.get('strings','warning'));
        player = Player(self)
        players[self.client_address] = player
        #readline is a blocking call so we're safe, otherwise it'll destroy your CPU
        while(1):
            data = self.rfile.readline()
            if not data: break #if data is empty and not blocking, the connection went poof
            q.put(RPCMessage(player,data))

#Marshalling           
class NetMarshall(socketserver.ThreadingMixIn, socketserver.TCPServer):
    #def handle_error(self, request, client_address):
        #print("Some shit went down from %s" % (client_address,))
    def handle_exit(self, request, client_address):
        players[client_address].disconnect()

#Marshalling + Simulation
class RPCMessage:
    def __init__(self,player,message):
        self.player = player
        self.message = str(message.strip())[1:].strip('"\'').lower().split(' ',1)
        if len(self.message) == 1:
            self.message = [self.message[0],0]
        self.funcs = {'help': self.rpc_help} # any time
        self.afuncs = {'create':self.rpc_create,'login':self.rpc_login} # anonymous only
        self.rfuncs = {'logout':self.rpc_logout} # logged in only
        self.sfuncs = {} # admin commands... if you want them

    def rpc_logout(self, args):
        self.player.logout()
        self.player.net.w("You are now logged out.")
        
    def rpc_create(self, args):
        args = str(args).split(' ',1)
        if len(args) == 1:
            self.player.net.w("CREATE takes two arguments, NAME and PASSWORD seperated by a space\r\nex: CREATE name password")
            pass
        if args[0] in characters:
            self.player.net.w("\"%s\" is already taken :(" % (args[1]))
        
        self.player.character = Character(args[0],args[1])
        characters[args[0]] = self.player.character
        self.player.net.w("You have created %s! The first step is always the hardest." % self.player.character.name)
        
    def rpc_login(self, args):
        args = str(args).split(' ',1)
        if len(args) == 1:
            self.player.net.w("Login takes two arguments, NAME and PASSWORD seperated by a space\r\nex: LOGIN name password")
            pass
        if args[0] in characters:
            character = characters[args[0]]
            if character.password == args[1]:
                self.player.character = character
                self.player.net.w("You are now logged into %s." % character.name)
            else:
                self.player.net.w("The password supplied does not match the name \"%s\"." % (args[1]))
                pass
        else:
            self.player.net.w("\"%s\" does not exist! Why don't you CREATE it?" % (args[1]))
            pass
        
    def rpc_help(self, args):
        if args:
            self.player.net.w(cfg.get('rpc',self.message[0]))
        else:
            rpcs = 'FULL ACCESS>>  '
            for rpc in self.funcs.keys():
                rpcs += rpc + ', '
            rpcs.strip(',')
            rpcs += "\n\rANONYMOUS ONLY>>  "
            for rpc in self.afuncs.keys():
                rpcs += rpc + ', '
            rpcs.strip(',')
            rpcs += "\n\rLOGGED IN ONLY>>  "
            for rpc in self.rfuncs.keys():
                rpcs += rpc + ', '
            rpcs.strip(',')
            self.player.net.w("The following commands are available:\n\r%s\n\rType HELP {COMMAND} to get more info" % rpcs)
            
    def execute(self):
        if self.message[0] in self.funcs:
            #print(getargspec(self.funcs[self.message[0]]))
            self.funcs[self.message[0]](self.message[1])
        elif self.message[0] in self.afuncs:
            if not self.player.character:
                self.afuncs[self.message[0]](self.message[1])
            else:
                self.player.net.w("You may only use %s when not logged in. Please LOGOUT if you want to use this command." % self.message[0].upper())
        elif self.message[0] in self.rfuncs:
            if self.player.character:
                self.rfuncs[self.message[0]](self.message[1])
            else:
                self.player.net.w("You may only use %s when logged in. Please either LOGIN or CREATE to use this command." % self.message[0].upper())
        else:
            self.player.net.w("I did not understand your command: %s" % (self.message[0]))
            
class Player:
    character = 0
                                  
    def __init__(self,net):
        self.net = net
        
    def disconnect(self):
        if self.character:
            self.logout()
        players.remove(self)

    def logout(self):
        self.character = 0
        
class Character:
    def __init__(self, name, password, accessLevel = 0):
        self.level = 0
        self.name = name
        self.password = password #super safe ya?
        self.accessLevel = accessLevel


#Startup Sequence
if __name__ == "__main__":
    cfg = configparser.SafeConfigParser()
    cfg.read('game.cfg')
    
    HOST, PORT = cfg.get('net','host'), int(cfg.get('net','port')) #default telnet port is 23
    
    #Persistence... the only persistence in this whole thing
    characters = {cfg.get('admin','name'):Character(cfg.get('admin','name'),cfg.get('admin','password'),9)}
    players = {}
    q = Queue()
    
    server = NetMarshall((HOST, PORT), NetHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.setDaemon(True)
    server_thread.start()
    
    print("Server loop running in thread:", server_thread.name)

    #Simulation - If we were doing more than handling RPCs harhar :D
    while(1):
        rpc = q.get(1) # block the shit out of this
        rpc.execute()
        
        


