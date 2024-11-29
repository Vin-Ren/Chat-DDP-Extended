from http import client
import socket
from threading import Thread
import pickle
import traceback
from typing import Callable, Tuple

from chat import Initiator, Context, Message


class DisconnectedError(ConnectionResetError, ConnectionAbortedError):
    pass


# Ref: https://github.com/Vin-Ren/Synapsis/blob/82e7b2b20c07b42fb8611b214f7e4a838d8fe7cf/web/utils/message.py 
# Public: https://github.com/Vin-Ren/Synapsis-Public
# *With some adjustments
class Messenger:
    HEADER_SIZE = 32
    ENCODING = 'UTF-8'
    PICKLE = True
    DEFAULT_MAKE_WITH_METADATA = False

    def __init__(self, pickleData=False, defaultMetadata: dict = None):
        self.pickleData = pickleData
        self.defaultMetadata = defaultMetadata or {}

    def make(self, data, withMetadata=DEFAULT_MAKE_WITH_METADATA):
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

    def send(self, request, data):
        return request.send(self.make(data))
    
    def recv(self, request):
        try:
            header_data = request.recv(self.HEADER_SIZE)
            data_length = int(header_data.decode(self.ENCODING).strip())
            data = request.recv(data_length)

            if self.pickleData:
                return pickle.loads(data)
            return data.decode(self.ENCODING)
        except ValueError as exc:
            raise RuntimeError('You are trying to receive None.') from exc
        except (ConnectionResetError, ConnectionAbortedError) as exc:
            raise DisconnectedError('Connection Disconnected.') from exc


class Server:
    def __init__(self, host='0.0.0.0', port=8080):
        self.host = host
        self.port = port
        self.connected_clients = {} # username: address
        self.reverse_connected_clients = {} # address: username
        self.blacklisted_clients = []
        self.blacklisted_addr = []
        self.connected_sockets = []
        self.stop_server = False
        
        self.messenger = Messenger(True)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_runner = Thread(target=self._start_server, daemon=True)
        
        self.socket.settimeout(1000)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
    
    @property
    def local_ip_address(self):
        return socket.gethostbyname(socket.gethostname())
    
    def on_sock_recv(self, clientsocket: socket.socket, client_addr: Tuple[str, int], data):
        if not isinstance(data, dict):
            return {'event': 'error', 'message': Message('Invalid data.')}
        # print(data)
        if data['event'] == 'auth':
            if data.get('message') is None:
                return {'event': 'auth', 'message': Message(Initiator.System, Initiator.System, "What is your name?")}
            if data['message'].content in self.connected_clients:
                return {'event': 'auth', 'message': Message(Initiator.System, Initiator.System, "That name has already been used. What is your name?")}
            if data['message'].content:
                self.connected_clients[data['message'].content] = client_addr
                self.reverse_connected_clients[client_addr] = data['message'].content
                return {'event': 'auth_success', 
                        'username': self.reverse_connected_clients[client_addr],
                        'message': Message(Initiator.System, Initiator.System, 'Welcome to the chat session {}!'.format(self.reverse_connected_clients[client_addr]))}
        
        if not client_addr in self.reverse_connected_clients:
            return {'event': 'auth', 'message': Message(Initiator.System, Initiator.System,'Hey! Who are you?')}
        
        if data['event'] == 'broadcast':
            try:
                assert isinstance(data['message'], Message), "Hmmm this is not supposed to happen, a malicious actor is at play here."
                data['message'].initiator = Initiator.Network
                data['message']._from = self.reverse_connected_clients[client_addr]
                for socket in self.connected_sockets:
                    if socket == clientsocket:
                        continue
                    self.messenger.send(socket, data)
            except:
                traceback.print_exc()
    
    def client_socket_handler(self, clientsocket: socket.socket, address):
        self.connected_sockets.append(clientsocket)
        while not self.stop_server:
            try:
                content = self.messenger.recv(clientsocket)
                reply = self.on_sock_recv(clientsocket, address, content)
                self.messenger.send(clientsocket, reply)
            except DisconnectedError:
                break
            except:
                traceback.print_exc()
        self.connected_sockets.remove(clientsocket)
        username = self.reverse_connected_clients.pop(address)
        self.connected_clients.pop(username)
    
    def _start_server(self):
        self.socket.listen()
        while not self.stop_server:
            (clientsocket, address) = self.socket.accept()
            clientsocket.settimeout(1000)
            ct = Thread(target=self.client_socket_handler, args=(clientsocket,address), daemon=True)
            ct.start()
    
    def start_server(self):
        self.server_runner.start()
    
    def kill_server(self):
        self.stop_server = True
        self.server_runner.join(timeout=5)
    
    def ban_user(self, name):
        self.blacklisted_clients.append(name)
        if name in self.connected_clients:
            self.disconnect(self.connected_clients[name])


class Client:
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
        self.socket.connect((self.server_host, self.server_port))
        last_response = {'event':'auth'}
        
        def initial_response_handler(ctx: Context):
            nonlocal last_response
            self.messenger.send(self.socket, {'event':'auth'})
            last_response = self.messenger.recv(self.socket)
            ctx.send_message(last_response['message'])
            return response_handler
        
        def response_handler(ctx: Context):
            nonlocal last_response
            self.messenger.send(self.socket, {'event':'auth', 'message': ctx.message})
            last_response = self.messenger.recv(self.socket)
            ctx.send_message(last_response['message'])
            if last_response['event'] == 'auth_success':
                self.known_as = last_response['username']
                self.authenticated = True
                self.on_auth_handler(self)
                self.socket_listener_runner.start()
                return
            return response_handler
        return initial_response_handler
    
    def stop(self):
        self.stop_client = True
        self.socket_listener_runner.join(timeout=5)
    
    def socket_listener(self):
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
        self.send({'event': 'broadcast', 'message': message})
    
    def send(self, data):
        try:
            self.messenger.send(self.socket, data)
        except (DisconnectedError, ConnectionResetError, ConnectionAbortedError):
            self.on_disconnect_handler()

