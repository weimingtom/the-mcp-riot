import socket
import threading
import socketserver
import time

class NetHandler(socketserver.StreamRequestHandler):
    def w(self,text):
        self.wfile.write(bytes(text+"\n\r",'ascii'))
    def handle(self):
        self.data = self.rfile.readline().strip()
        self.w("Welcome to MUD Riot")
        print(threading.current_thread().getName())
        while(True):
            time.sleep(5)
            self.w("onononomomonomo")
            
        #delicous sleep
        #cur_thread = 
        #response = bytes("%s: %s" % (cur_thread.getName(), data),'ascii')
        #self.request.send(response)
        
class NetMarshall(socketserver.ThreadingMixIn, socketserver.TCPServer):
    def __init__(self,listen,handler,):
        super(A,self).__init__(listen,handler)
         
    def handle_error(self,request,client_address):
        print("Some shit went down from %s" % (client_address,))

#Startup Sequence
if __name__ == "__main__":
    HOST, PORT = "localhost", 23 #default telnet port is 23
    incoming = Queue()
    server = NetMarshall((HOST, PORT), NetHandler,incoming)
    
    server_thread = threading.Thread(target=server.serve_forever)
    # Exit the server thread when the main thread terminates
    server_thread.setDaemon(True)
    server_thread.start()
    print("Server loop running in thread:", server_thread.name)


