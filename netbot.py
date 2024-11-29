import traceback
from typing import Callable
from chat import Context, Initiator, Message, Session
from bot import Bot, command, listener
from network import Server, Client

class NetBot(Bot):
    """
    NetBot
    ---
    
    A simple bot to manage the networking interface
    /startserver
    /connect
    /disconnect
    /stopserver
    """
    def __init__(self, chat_session: Session, on_username_change: Callable = None):
        super().__init__(chat_session, Initiator.System, Initiator.System, case_sensitive=False, default_help_prefixes=['/help'])
        self.message_factory = Message.get_factory(Initiator.System, Initiator.System)
        self.network_server = None
        self.network_client = None
        self.on_username_change = on_username_change or (lambda *_:None)
    
    def on_broadcast_handler(self, msg: Message):
        self.chat_session.send_message(msg)
    
    def on_auth_handler(self, client: Client):
        self.on_username_change(client.known_as)
    
    def on_disconnected_handler(self, client: Client):
        self.network_client = None
        self.chat_session.send_message(self.message_factory("You have been disconnected from the server!"))
    
    @command(is_fallback=True)
    def broadcaster(self, ctx: Context):
        if self.network_client and self.network_client.authenticated:
            self.network_client.broadcast(ctx.message)
    
    @command('/start server', '/startserver', '/ss', description="Starts a server instance for a chat session on the local network")
    def start_server(self, ctx: Context, port: int = 8080):
        if self.network_server is not None:
            return ctx.send_message(content="Server is already running at {}:{}".format(self.network_server.host, self.network_server.port))
        ctx.send_message(content="Initializing server...")
        try:
            self.network_server = Server()
            self.network_server.start_server()
            ctx.send_message(content="Server spun up successfully!\nTo connect to the server, run '/connect {} {}'".format(self.network_server.local_ip_address, self.network_server.port))
        except:
            self.network_server = None
            ctx.send_message(content="Something went wrong... :(")
    
    @command('/kill server', '/killserver', '/ks', description="Kills the current running server")
    def kill_server(self, ctx: Context):
        if self.network_server is None:
            return ctx.send_message(content="There is no server running")
        ctx.send_message(content="Killing server...")
        self.network_server.kill_server()
        self.network_server = None
        ctx.send_message(content="Server killed successfully.")
    
    @command('/ban', description="Bans a user from your hosted server. Note that this blocks their username and ip from being used again in your server.")
    def ban_user(self, ctx: Context, *, username: str):
        if self.network_server is None:
            return ctx.send_message(content="You are not hosting a server")
        self.network_server.ban_user(username)
        ctx.send_message(content="Banned user {}".format(username))
    
    @command('/connect', '/con', '/c', description="Connects to an existing server")
    def connect_client(self, ctx: Context, address: str = 'localhost', port: int = 8080):
        if self.network_client:
            return ctx.send_message(content="You are already connected to a server! Disconnect first to connect to another server.")
        ctx.send_message(content="Connecting to server at [{}:{}]...".format(address, port))
        try:
            self.network_client = Client(address, port, self.on_broadcast_handler, self.on_auth_handler, self.on_disconnected_handler)
            response_handler = self.network_client.connect()
            return response_handler(ctx)
        except:
            self.network_client = None
            traceback.print_exc()
            ctx.send_message(content="Something went wrong... :(")

    @command('/disconnect', '/dc', description="Disconnects from a server")
    def disconnect_client(self, ctx: Context):
        if self.network_client is None:
            return ctx.send_message(content="There's no connection to be disconnected!")
        ctx.send_message(content="Disconnecting from server...")
        try:
            self.network_client.stop()
            self.network_client = None
        except:
            traceback.print_exc()
            ctx.send_message(content="Something went wrong... :(")
