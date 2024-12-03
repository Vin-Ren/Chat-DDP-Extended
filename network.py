from http import client
import socket
from threading import Thread
import pickle
import traceback
from typing import Callable, Tuple

from chat import Initiator, Context, Message


class DisconnectedError(ConnectionResetError, ConnectionAbortedError, OSError):
    "Encapsulates errors caught by Messenger"


# Ref: https://github.com/Vin-Ren/Synapsis/blob/82e7b2b20c07b42fb8611b214f7e4a838d8fe7cf/web/utils/message.py 
# Public: https://github.com/Vin-Ren/Synapsis-Public
# *With some adjustments
class Messenger:
    """
    Messenger
    ---
    Abstracts the process of sending data through a socket by providing a 
    simple wrapper for socket's receive and send method by supporting variating 
    data length, encoding, and pickle to convert and conserve the transported data.
    """
    HEADER_SIZE = 32
    ENCODING = 'UTF-8'
    PICKLE = True
    DEFAULT_MAKE_WITH_METADATA = False

    def __init__(self, pickleData=False, defaultMetadata: dict = None):
        self.pickleData = pickleData
        self.defaultMetadata = defaultMetadata or {}

    def pack(self, data, withMetadata=DEFAULT_MAKE_WITH_METADATA):
        "Packs a given data to a transportable ready type in sockets, in this case, bytes."
        if withMetadata:
            _data = self.defaultMetadata
            _data.update(data)
            data = _data
        if self.pickleData:
            data = pickle.dumps(data)
        else:
            data = data.encode(self.ENCODING)

        header = "{}".format(len(data)).ljust(self.HEADER_SIZE, " ").encode(self.ENCODING)
        return header + data

    def send(self, socket: socket.socket, data):
        "Sends given data to the socket"
        return socket.send(self.pack(data))
    
    def recv(self, socket: socket.socket):
        "Receives a packed data from the given socket. Mind that this only tries to receive one packed data from the socket."
        try:
            header_data = socket.recv(self.HEADER_SIZE)
            data_length = int(header_data.decode(self.ENCODING).strip())
            data = socket.recv(data_length)

            if self.pickleData:
                return pickle.loads(data)
            return data.decode(self.ENCODING)
        except (ConnectionResetError, ConnectionAbortedError, OSError, ValueError) as exc:
            raise DisconnectedError('Connection Disconnected.') from exc


class Server:
    """
    Server
    ---
    Handles authentication of clients and communication between clients as a chat server.
    """
    def __init__(self, host='0.0.0.0', port=8080):
        self.host = host
        self.port = port
        self.stop_server = False
        
        self.connected_clients: dict[str, str] = {} 
        "Maps username to address"
        
        self.reverse_connected_clients: dict[str, str] = {}
        "Maps address to username"
        
        self.blacklisted_users: list[str] = []
        "Blacklisted usernames"
        
        self.blacklisted_addrs: list[str] = []
        "Blacklisted ip addresses"
        
        self.connected_sockets: dict[str, socket.socket] = {}
        "Maps address to socket"
        
        self.messenger = Messenger(True)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_runner = Thread(target=self._start_server, daemon=True)
        
        self.socket.settimeout(1000)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
    
    @property
    def local_ip_address(self):
        "Gets ip address of the machine on the local network"
        return socket.gethostbyname(socket.gethostname())
    
    def on_sock_recv(self, client_addr: Tuple[str, int], data):
        "Handles data/event received from clients and process them"
        if not isinstance(data, dict): # If received data is not a dictionary object, then invalidate it.
            return {'event': 'error', 'message': Message('Invalid data.')}
        # print(data)
        if data['event'] == 'auth': # If the client is attempting authentication, then try to authenticate it. 
            if data.get('message') is None: # No message received yet, prompt for one
                return {'event': 'auth', 'message': Message(Initiator.System, Initiator.System, "What is your name?")}
            if data['message'].content in self.connected_clients: # Duplicate username
                return {'event': 'auth', 'message': Message(Initiator.System, Initiator.System, "That name has already been used. What is your name?")}
            if data['message'].content in self.blacklisted_users or client_addr[0] in self.blacklisted_addrs: # Banned users
                return {'event': 'auth_reject', 'message': Message(Initiator.System, Initiator.System, "You have been banned.")}
            if data['message'].content: # Assigns a username to the requester client
                # Authenticate the user
                self.connected_clients[data['message'].content] = client_addr
                self.reverse_connected_clients[client_addr] = data['message'].content
                
                # Broadcasts the entry of the new user to the chat
                broadcast_message = Message(Initiator.System, Initiator.System, "{} has joined the chat! ({} user(s) online)".format(self.reverse_connected_clients[client_addr], len(self.connected_clients)))
                self.broadcast(broadcast_message, skip_addrs=[client_addr], verify=False)
                
                return {'event': 'auth_success', 
                        'username': self.reverse_connected_clients[client_addr],
                        'message': Message(Initiator.System, Initiator.System, 'Welcome to the chat session {}! ({} user(s) online)'.format(self.reverse_connected_clients[client_addr], len(self.connected_clients)))}
        
        if not client_addr in self.reverse_connected_clients: # Unauthenticated user tries to send an event other than auth
            return {'event': 'auth', 'message': Message(Initiator.System, Initiator.System, 'Hey! Who are you?')}
        
        if data['event'] == 'broadcast': # Handles broadcast event from authenticated users
            data['message'].initiator = Initiator.Network
            data['message']._from = self.reverse_connected_clients[client_addr]
            self.broadcast(data['message'], skip_addrs=[client_addr])

    def broadcast(self, message: Message, skip_addrs: list[str] = None, verify: bool = True):
        "Broadcasts a given message to all connected sockets except the ones listed in skip_addrs. if verify is True, runs assertion on the message."
        data = {'event': 'broadcast', 'message': message}
        try:
            if verify:
                assert isinstance(message, Message), "Hmmm this is not supposed to happen, a malicious actor is at play here."
            for _, addr in self.connected_clients.items():
                if addr in skip_addrs:
                    continue
                try:
                    self.messenger.send(self.connected_sockets[addr], data)
                except (OSError, ConnectionResetError, ConnectionAbortedError):
                    pass
        except:
            traceback.print_exc()
    
    def client_socket_handler(self, clientsocket: socket.socket, address):
        "Handles a client socket across its lifetime, pooling for message, process it, and sends a response back"
        self.connected_sockets[address] = clientsocket
        while not self.stop_server:
            try:
                content = self.messenger.recv(clientsocket)
                reply = self.on_sock_recv(address, content)
                self.messenger.send(clientsocket, reply)
            except DisconnectedError:
                break
            except:
                traceback.print_exc()
        
        # Handles the disconnection proccess of clientsocket
        if address in self.connected_sockets:
            self.connected_sockets.pop(address)
        if address in self.reverse_connected_clients:
            broadcast_message = Message(Initiator.System, Initiator.System, "{} has left the chat. ({} user(s) online)".format(self.reverse_connected_clients[address], len(self.connected_clients)-1))
            self.broadcast(broadcast_message, skip_addrs=[address], verify=False)
            username = self.reverse_connected_clients.pop(address)
            self.connected_clients.pop(username)
    
    def _start_server(self):
        "Starts the socket server, this is the target of the server runner Thread"
        self.socket.listen()
        while not self.stop_server:
            try:
                (clientsocket, address) = self.socket.accept()
                clientsocket.settimeout(1000)
                ct = Thread(target=self.client_socket_handler, args=(clientsocket,address), daemon=True)
                ct.start()
            except (OSError, ConnectionAbortedError, ConnectionResetError):
                pass
    
    def start_server(self):
        "Starts the server runner thread"
        self.server_runner.start()
    
    def kill_server(self):
        "Kills the running server"
        self.stop_server = True
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except:
            pass
        self.socket.close()
        for socketclient in list(self.connected_sockets.values()):
            try:
                socketclient.shutdown(socket.SHUT_RDWR)
            except:
                pass
            socketclient.close()
        if self.server_runner.is_alive():
            self.server_runner.join(timeout=2)
    
    def ban_user(self, username):
        "Blacklists a username and their ip if they are currently connected"
        self.blacklisted_users.append(username)
        if username in self.connected_clients:
            self.blacklisted_addrs.append(self.connected_clients[username][0])
            self.connected_sockets[self.connected_clients[username]].close()


class Client:
    """
    Client
    ---
    Handles communication and authentication between the server and the client
    """
    def __init__(self, server_host, server_port, on_broadcast_handler: Callable = None, on_auth_handler: Callable = None, on_disconnect_handler: Callable = None):
        self.server_host = server_host
        self.server_port = server_port
        self.on_broadcast_handler = on_broadcast_handler or (lambda *_:None)
        self.on_auth_handler = on_auth_handler or (lambda *_:None)
        self.on_disconnect_handler = on_disconnect_handler or (lambda *_:None)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.authenticated = False
        self.known_as = None
        self.stop_client = False
        
        self.messenger = Messenger(pickleData=True)
        self.socket_listener_runner = Thread(target=self.socket_listener, daemon=True)
        
        self.socket.settimeout(1000)

    def connect(self):
        "Connects to a chat server and attempt to authenticate"
        self.socket.connect((self.server_host, self.server_port))
        last_response = {'event':'auth'}
        
        def initial_response_handler(ctx: Context):
            "Prompts server for input prompt and use ctx to show it to the user"
            nonlocal last_response
            try:
                self.messenger.send(self.socket, {'event':'auth'})
                last_response = self.messenger.recv(self.socket)
                ctx.send_message(last_response['message'])
            except DisconnectedError:
                return ctx.send_message(content="Something went wrong :(")
            return response_handler
        
        def response_handler(ctx: Context):
            "Handles interaction between user and the server while authentication is ongoing"
            nonlocal last_response
            try:
                self.messenger.send(self.socket, {'event':'auth', 'message': ctx.message})
                last_response = self.messenger.recv(self.socket)
                ctx.send_message(last_response['message'])
                if last_response['event'] != 'auth':
                    if last_response['event'] == 'auth_reject':
                        self.socket.close()
                        self.on_disconnect_handler(self)
                        return
                    self.known_as = last_response['username']
                    self.authenticated = True
                    self.on_auth_handler(self)
                    self.socket_listener_runner.start()
                    return
            except DisconnectedError:
                return ctx.send_message(content="Something went wrong :(")
            return response_handler
        return initial_response_handler
    
    def stop(self):
        "Stops and disconnects the client from a chat server"
        self.stop_client = True
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()
        if self.socket_listener_runner.is_alive():
            print(self.socket_listener_runner.is_alive())
            self.socket_listener_runner.join(timeout=2)
    
    def socket_listener(self):
        "Starts the socket connected to a chat server to listen to events, target of the client thread runner after successful authentication."
        while not self.stop_client:
            try:
                data = self.messenger.recv(self.socket)
                if data and data['event'] == 'broadcast':
                    self.on_broadcast_handler(data['message'])
            except DisconnectedError:
                break
            except:
                traceback.print_exc()
        self.on_disconnect_handler(self)
    
    def broadcast(self, message: Message):
        "Broadcasts the given message by sending it to the chat server."
        self.send({'event': 'broadcast', 'message': message})
    
    def send(self, data):
        "Sends the given data to the server"
        try:
            self.messenger.send(self.socket, data)
        except DisconnectedError:
            self.on_disconnect_handler(self)
