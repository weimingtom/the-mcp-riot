import stackless
import asyncore, weakref
import socket as stdsocket # We need the "socket" name for the function we export.

managerRunning = False

def ManageSockets():
    global managerRunning

    try:
        while len(asyncore.socket_map):
            # Check the sockets for activity.
            asyncore.poll(0.05)
            # Yield to give other tasklets a chance to be scheduled.
            _schedule()
    finally:
        managerRunning = False

def StartManager():
    global managerRunning
    if not managerRunning:
        managerRunning = True
        return stackless.tasklet(ManageSockets)()

_schedule = stackless.schedule
_manage_sockets_func = StartManager

def stacklesssocket_manager(mgr):
    global _manage_sockets_func
    _manage_sockets_func = mgr

def socket(*args, **kwargs):
    import sys
    if "socket" in sys.modules and sys.modules["socket"] is not stdsocket:
        raise RuntimeError("Use 'stacklesssocket.install' instead of replacing the 'socket' module")

_realsocket_old = stdsocket._realsocket
_socketobject_old = stdsocket._socketobject

class _socketobject_new(_socketobject_old):
    def __init__(self, family=AF_INET, type=SOCK_STREAM, proto=0, _sock=None):
        # We need to do this here.
        if _sock is None:
            _sock = _realsocket_old(family, type, proto)
            _sock = _fakesocket(_sock)
            _manage_sockets_func()
        _socketobject_old.__init__(self, family, type, proto, _sock)
        if not isinstance(self._sock, _fakesocket):
            raise RuntimeError("bad socket")

    def accept(self):
        sock, addr = self._sock.accept()
        sock = _fakesocket(sock)
        sock.wasConnected = True
        return _socketobject_new(_sock=sock), addr
        
    accept.__doc__ = _socketobject_old.accept.__doc__


def check_still_connected(f):
    " Decorate socket functions to check they are still connected. "
    def new_f(self, *args, **kwds):
        if not self.connected:
            # The socket was never connected.
            if not self.wasConnected:
                raise error(10057, "Socket is not connected")
            # The socket has been closed already.
            raise error(EBADF, 'Bad file descriptor')
        return f(self, *args, **kwds)
    return new_f


def install():
    if stdsocket._realsocket is socket:
        raise StandardError("Still installed")
    stdsocket._realsocket = socket
    stdsocket.socket = stdsocket.SocketType = stdsocket._socketobject = _socketobject_new

def uninstall():
    stdsocket._realsocket = _realsocket_old
    stdsocket.socket = stdsocket.SocketType = stdsocket._socketobject = _socketobject_old


class _fakesocket(asyncore.dispatcher):
    connectChannel = None
    acceptChannel = None
    recvChannel = None
    wasConnected = False

    def __init__(self, realSocket):
        # This is worth doing.  I was passing in an invalid socket which
        # was an instance of _fakesocket and it was causing tasklet death.
        if not isinstance(realSocket, _realsocket_old):
            raise StandardError("An invalid socket passed to fakesocket %s" % realSocket.__class__)

        # This will register the real socket in the internal socket map.
        asyncore.dispatcher.__init__(self, realSocket)
        self.socket = realSocket

        self.recvChannel = stackless.channel()
        self.readString = ''
        self.readIdx = 0

        self.sendBuffer = ''
        self.sendToBuffers = []

    def __del__(self):
        # There are no more users (sockets or files) of this fake socket, we
        # are safe to close it fully.  If we don't, asyncore will choke on
        # the weakref failures.
        self.close()

    # The asyncore version of this function depends on socket being set
    # which is not the case when this fake socket has been closed.
    def __getattr__(self, attr):
        if not hasattr(self, "socket"):
            raise AttributeError("socket attribute unset on '"+ attr +"' lookup")
        return getattr(self.socket, attr)

    def add_channel(self, map=None):
        if map is None:
            map = self._map
        map[self._fileno] = weakref.proxy(self)

    def writable(self):
        if self.socket.type != SOCK_DGRAM and not self.connected:
            return True
        return len(self.sendBuffer) or len(self.sendToBuffers)

    def accept(self):
        if not self.acceptChannel:
            self.acceptChannel = stackless.channel()
        return self.acceptChannel.receive()

    def connect(self, address):
        asyncore.dispatcher.connect(self, address)
        
        # UDP sockets do not connect.
        if self.socket.type != SOCK_DGRAM and not self.connected:
            if not self.connectChannel:
                self.connectChannel = stackless.channel()
                # Prefer the sender.  Do not block when sending, given that
                # there is a tasklet known to be waiting, this will happen.
                self.connectChannel.preference = 1
            self.connectChannel.receive()

    @check_still_connected
    def send(self, data, flags=0):
        self.sendBuffer += data
        _schedule()
        return len(data)

    @check_still_connected
    def sendall(self, data, flags=0):
        # WARNING: this will busy wait until all data is sent
        # It should be possible to do away with the busy wait with
        # the use of a channel.
        self.sendBuffer += data
        while self.sendBuffer:
            _schedule()
        return len(data)

    def sendto(self, sendData, sendArg1=None, sendArg2=None):
        # sendto(data, address)
        # sendto(data [, flags], address)
        if sendArg2 is not None:
            flags = sendArg1
            sendAddress = sendArg2
        else:
            flags = 0
            sendAddress = sendArg1
            
        waitChannel = None
        for idx, (data, address, channel, sentBytes) in enumerate(self.sendToBuffers):
            if address == sendAddress:
                self.sendToBuffers[idx] = (data + sendData, address, channel, sentBytes)
                waitChannel = channel
                break
        if waitChannel is None:
            waitChannel = stackless.channel()
            self.sendToBuffers.append((sendData, sendAddress, waitChannel, 0))
        return waitChannel.receive()

    # Read at most byteCount bytes.
    def recv(self, byteCount, flags=0):        
        # recv() must not concatenate two or more data fragments sent with
        # send() on the remote side. Single fragment sent with single send()
        # call should be split into strings of length less than or equal
        # to 'byteCount', and returned by one or more recv() calls.

        remainingBytes = self.readIdx != len(self.readString)
        # TODO: Verify this connectivity behaviour.

        if not self.connected:
            # Sockets which have never been connected do this.
            if not self.wasConnected:
                raise error(10057, 'Socket is not connected')

            # Sockets which were connected, but no longer are, use
            # up the remaining input.  Observed this with urllib.urlopen
            # where it closes the socket and then allows the caller to
            # use a file to access the body of the web page.
        elif not remainingBytes:            
            self.readString = self.recvChannel.receive()
            self.readIdx = 0
            remainingBytes = len(self.readString)

        if byteCount == 1 and remainingBytes:
            ret = self.readString[self.readIdx]
            self.readIdx += 1
        elif self.readIdx == 0 and byteCount >= len(self.readString):
            ret = self.readString
            self.readString = ""
        else:
            idx = self.readIdx + byteCount
            ret = self.readString[self.readIdx:idx]
            self.readString = self.readString[idx:]
            self.readIdx = 0

        # ret will be '' when EOF.
        return ret

    def recvfrom(self, byteCount, flags=0):
        if self.socket.type == SOCK_STREAM:
            return self.recv(byteCount), None

        # recvfrom() must not concatenate two or more packets.
        # Each call should return the first 'byteCount' part of the packet.
        data, address = self.recvChannel.receive()
        return data[:byteCount], address

    def close(self):
        asyncore.dispatcher.close(self)

        self.connected = False
        self.accepting = False
        self.sendBuffer = None  # breaks the loop in sendall

        # Clear out all the channels with relevant errors.
        while self.acceptChannel and self.acceptChannel.balance < 0:
            self.acceptChannel.send_exception(error, 9, 'Bad file descriptor')
        while self.connectChannel and self.connectChannel.balance < 0:
            self.connectChannel.send_exception(error, 10061, 'Connection refused')
        while self.recvChannel and self.recvChannel.balance < 0:
            # The closing of a socket is indicted by receiving nothing.  The
            # exception would have been sent if the server was killed, rather
            # than closed down gracefully.
            self.recvChannel.send("")
            #self.recvChannel.send_exception(error, 10054, 'Connection reset by peer')

    # asyncore doesn't support this.  Why not?
    def fileno(self):
        return self.socket.fileno()

    def handle_accept(self):
        if self.acceptChannel and self.acceptChannel.balance < 0:
            t = asyncore.dispatcher.accept(self)
            if t is None:
                return
            t[0].setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            stackless.tasklet(self.acceptChannel.send)(t)

    # Inform the blocked connect call that the connection has been made.
    def handle_connect(self):
        if self.socket.type != SOCK_DGRAM:
            self.wasConnected = True
            self.connectChannel.send(None)

    # Asyncore says its done but self.readBuffer may be non-empty
    # so can't close yet.  Do nothing and let 'recv' trigger the close.
    def handle_close(self):
        # This also gets called in the case that a non-blocking connect gets
        # back to us with a no.  If we don't reject the connect, then all
        # connect calls that do not connect will block indefinitely.
        if self.connectChannel is not None:
            self.close()

    # Some error, just close the channel and let that raise errors to
    # blocked calls.
    def handle_expt(self):
        self.close()

    def handle_read(self):
        try:
            if self.socket.type == SOCK_DGRAM:
                ret = self.socket.recvfrom(20000)
            else:
                ret = asyncore.dispatcher.recv(self, 20000)
                # Not sure this is correct, but it seems to give the
                # right behaviour.  Namely removing the socket from
                # asyncore.
                if not ret:
                    self.close()
            stackless.tasklet(self.recvChannel.send)(ret)
        except stdsocket.error, err:
            # If there's a read error assume the connection is
            # broken and drop any pending output
            if self.sendBuffer:
                self.sendBuffer = ""
            self.recvChannel.send_exception(stdsocket.error, err)

    def handle_write(self):
        if len(self.sendBuffer):
            sentBytes = asyncore.dispatcher.send(self, self.sendBuffer[:512])
            self.sendBuffer = self.sendBuffer[sentBytes:]
        elif len(self.sendToBuffers):
            data, address, channel, oldSentBytes = self.sendToBuffers[0]
            sentBytes = self.socket.sendto(data, address)
            totalSentBytes = oldSentBytes + sentBytes
            if len(data) > sentBytes:
                self.sendToBuffers[0] = data[sentBytes:], address, channel, totalSentBytes
            else:
                del self.sendToBuffers[0]
                stackless.tasklet(channel.send)(totalSentBytes)