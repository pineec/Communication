import socket
import time
import struct
from threading import Thread
from queue import Queue, Empty

class Communication(Thread):
    """
    Communication class manages a node and functionalities for data transfer between nodes.
    """

    def __init__(self, host:str = None , port:int = 55555) -> None:
        Thread.__init__(self)
        self._host = host
        self.port = port
        self._kill = False
        self.inbox = Queue()
        self.outbox = Queue()
        self.threads  = []

    @property
    def host(self):
        if self._host == None:
            hostname = socket.gethostname()
            self._host = socket.gethostbyname(hostname)
        return self._host
    
    @property
    def kill(self):
        self._kill = not self._kill
        if self._kill == True:
            print ("\nTerminating program...")
            [t.join() for t in self.threads]
            print ("\nExiting program.")
    
    def Send(self, destination:tuple, datatype:str, data):
        self.outbox.put((destination, datatype, data))

    ### PACKING MESSAGES ###
    def Pack(self, datatype:str, payload:bytearray ):
        byteorder = "<"
        header = (self.host, self.port, datatype)
        headerpack = "/".join(str(h) for h in header).encode("utf-8")
        headersize = len(headerpack)
        payloadsize = len(payload)
        
        framefmt = f"{byteorder}i{headersize}si{payloadsize}s"
        frame = struct.pack(framefmt, headersize, headerpack, payloadsize , payload)
        return frame

    def unPack(self,frame):
        byteorder = "<"
        headersize = struct.unpack(f"{byteorder}i" , frame[:4])[0]
        headerpack = struct.unpack(f"{byteorder}{headersize}s" , frame[4: 4+ headersize])[0].decode("utf-8")
        payloadsize = struct.unpack(f"{byteorder}i" , frame[4+ headersize: 8+ headersize])[0]
        payload = struct.unpack(f"{byteorder}{payloadsize}s" , frame[ -payloadsize: ])[0]
        header= headerpack.split("/")
        return (header , payload)
    
    ### EXECUTE ###
    def Start(self):
        print ("Starting...")
        try:
            print (f"\033[91mERROR\033[0m - No methods added")
        except Exception as e:
            print (f"\033[91mERROR\033[0m - {e}")

class Node (Communication):
    ### OUTGOING ###
    def __init__(self, host: str = None, port: int = 55555) -> None:
        super().__init__(host, port)

    def ClientSetup(self,targethost:str, targetport:int):
        '''ClientSetup attempts to send message to a receving party. Returns socket if sucessful else False.
        targethost: Target IP address
        targetport: Target port address'''

        s = socket.socket(socket.AF_INET,socket.SOCK_STREAM) # Create a socket
        s.settimeout(5) # Set timeout to 5s 
        try:
            s.connect((targethost,targetport)) 
            return s # returns socket 
        except:
            print(f"\033[91mERROR\033[0m - Could not communicate with {targethost} : {targetport}")
            return False # returns bool
    
    def push(self):
        """
        >  packet size
        < okay
        > packet
        < okay
        """
        while not self._kill:
            # While kill = False , look into the outbox and try to send messages to the target.
            try:
                destination , datatype, payload = self.outbox.get(timeout=1) # look at outbox, timeout 2s
                frame  = self.Pack(datatype , payload) # Package module, pack messages into an agreed upon format. i think this should be an attribute so that it could be changed while running.
            except Empty:
                continue
            except Exception as e:
                # unable to unpack - skips task
                print (f"\033[91mERROR\033[0m - {e}")
                continue 

            try:
                s = self.ClientSetup(destination[0], destination[1]) # attempt to connect to target
                
                if s:
                    # Succesful connection
                    try:
                        s.settimeout(None) # set timeout to None, anticipating large packets
                        s.send(str(len(frame)).encode())
                        s.recv(1024)
                        s.send(frame)
                        s.recv(1024)
                        s.close() # terminate connection
                        self.outbox.task_done() # remove task from queue
                        print (f"\033[96m\t>>> {destination[0]} : {destination[1]} \033[0m")
                        print (f"\033[96m\t\t|_ {datatype} : {len(payload)} bytes \033[0m")
                        continue
                    except:
                        print(f"\033[91mERROR\033[0m - Could not send data")
                        continue

            except Exception as e:
                print (f"\033[91mERROR\033[0m - {e}")
                continue

    ### INCOMING ###
    def ServerSetup(self):
        '''ServerSetup. This is where the machine recieves packets. While running, it is waiting for a connection'''
        
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Create a socket
        try:
            s.bind((self.host, self.port)) # Binding to port
            time.sleep(0.05) # Small nap 
            s.listen() # Waits for a connection
            print(f"Listening @ {self.host} : {self.port}" )
            return s # returns socket
        except:
            print (f"\033[91mERROR\033[0m - could not bind to port:{self.host} {self.port}")
            return False # returns bool

    def pull(self):
        """
        < packet size
        > okay
        repeat till all packs recieved:
            < packets
            > okay

        """
        server = self.ServerSetup()
        if server:
            while not self._kill:
                try: 
                    server.settimeout(4)
                    c, source = server.accept()
                    server.settimeout(99)
                    data = c.recv(1024)

                    if data:
                        c.send(b"okay") 
                        size = int(data.decode())
                        frame= bytearray()
                        while len(frame) < size:
                            nextpacksize = min(size - len(frame), 2048)
                            packet = c.recv(nextpacksize)
                            if not packet:
                                c.close()
                            frame.extend(packet)
                        c.send(f"    received {size} bytes".encode())

                        message  = self.unPack(frame)
                        self.inbox.put(message)
                        temp  = message[0]
                        print (f"\033[92m\t<<< {temp[0]} : {temp[1]} \033[0m ")
                        print (f"\033[92m\t\t|_ {temp[2]} : {len(message[1])} bytes \033[0m")
                except socket.timeout:
                    continue
                except Exception as e:
                    print (f"\033[91mERROR\033[0m - {e}")
            print (f"\n{self.host} : {self.port} Server - closed")

    ### EXECUTE ###
    def Start(self):
        print ("Starting...")
        try:
            """
            Standard Mode:
                1. Managing incoming messages
                2. Managing outgoing messages
            """
            print(f"\033[1mNode : Standard\033[0m")
            incoming_thread  = Thread(target = self.pull)
            outgoing_thread = Thread(target= self.push)

            incoming_thread.start()
            outgoing_thread.start()

            self.threads.append(incoming_thread)
            self.threads.append(outgoing_thread)
        except Exception as e:
            print (f"\033[91mERROR\033[0m - {e}")

class multicastNode(Communication):
    def __init__(self, host: str = None, port: int = 55555, mode = "R" , MCAST_GRP = "127.0.0.1", MCAST_PORT = 55588) -> None:
        """
        R - reciever
        B - multicasterer
        """
        super().__init__(host, port)
        self.mode = mode
        self.MCAST_GRP  = MCAST_GRP
        self.MCAST_PORT = MCAST_PORT
    
        ### BROADCASTING ###
    def MulticastSetup(self):
        try:
            if self.mode  == "R":
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((self.MCAST_GRP, self.MCAST_PORT))
            elif self.mode == "B":
                MULTICAST_TTL = 2
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, MULTICAST_TTL)
            return s
        except Exception as e:
            print (e)
            return False
    
    def push (self):
        multicaster = self.MulticastSetup()
        while not self._kill:
            try:
                destination , datatype, payload = self.outbox.get(timeout=1) # look at outbox, timeout 2s
                frame  = self.Pack(datatype , payload)
            except Empty:
                continue
            except Exception as e:
                # unable to unpack - skips task
                print (f"\033[91mERROR\033[0m - {e}")
                continue 
            try:
                multicaster.sendto(frame, (destination[0], destination[1]))
                #print (f"\033[96m\t>>> {destination[0]} : {destination[1]} \033[0m")
                #print (f"\033[96m\t\t|_ {datatype} : {len(payload)} bytes \033[0m")
                time.sleep(1)
                self.outbox.task_done()
                self.outbox.put((destination , datatype, payload))
            except Exception as e:
                print (f"\033[91mERROR\033[0m - {e}")
    
    def pull(self):
        multicaster = self.MulticastSetup()
        try:
            while not self._kill:
                ### Fix this
                #mreq = struct.pack("4sl", socket.inet_aton(self.MCAST_GRP), socket.INADDR_ANY)
                #multicaster.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                try:
                    multicaster.settimeout(2)
                    frame = multicaster.recv(1024)
                    message  = self.unPack(frame)
                    self.inbox.put(message)
                    temp  = message[0]
                    print (f"\033[92m\t<<< {temp[0]} : {temp[1]} \033[0m ")
                    print (f"\033[92m\t\t|_ {temp[2]} : {len(message[1])} bytes \033[0m")
                    break
                except socket.timeout:
                    continue
                except Exception as e:
                    print (f"\033[91mERROR\033[0m - {e}")
        except Exception as e:
            print (f"\033[91mERROR\033[0m - {e}")
    
    ### NODE MODES ###
    def multicaster(self):
        print(f"\033[1mNode : Broadcasting\033[0m")
        outgoing_thread = Thread(target= self.push)

        outgoing_thread.start()

        self.threads.append(outgoing_thread)

    def reciever(self):
        print(f"\033[1mNode : Tunning In \033[0m")
        incoming_thread  = Thread(target= self.pull)

        incoming_thread.start()

        self.threads.append(incoming_thread)

    ### EXECUTE ###
    def Start(self):
        print ("Starting...")
        try:
            if self.mode =="R":
                self.reciever()
        
            elif self.mode == "B":
                self.multicaster()
            
            else:
                print (f"\033[91mERROR\033[0m - unknown mode \"{self.mode}\" ")
        except Exception as e:
            print (f"\033[91mERROR\033[0m - {e}")