from datetime import datetime
from enum import StrEnum
from threading import Lock
from typing import Callable
from functools import partial


class Initiator(StrEnum):
    User = "User"
    ChatBot = "ChatBot"
    System = "System"
    Network = "Network"


class Message:
    """
    Message
    ---
    Encapsulates a message entry in the chat session.
    
    Available Instance Variables:
    - initiator: System, ChatBot, User, Network
    - _from: Who sent the message
    - content: the content of the message
    - timestamp: when is the message sent 
    
    """
    def __init__(self, initiator: Initiator, _from: str, content: str, timestamp: int = None):
        self.initiator = initiator
        self._from = _from
        self.content = content
        self.timestamp = timestamp if timestamp is not None else datetime.now().timestamp()
    
    def __str__(self):
        return "<Message initiator={} _from={} content='{}' at={}>".format(self.initiator, self._from, self.content[:50], self.datetime.isoformat())
    
    def __repr__(self):
        return self.__str__()
    
    @property
    def datetime(self):
        "Datetime object represented by the message's timestamp"
        return datetime.fromtimestamp(self.timestamp)

    @classmethod
    def get_factory(cls, initiator: Initiator, _from: str = None):
        "A factory for partial application of initiator and _from to create messages quicker"
        if _from:
            return partial(cls, initiator, _from)
        else:
            return partial(cls, initiator)


class Context:
    """
    Context
    ---
    Provides information for a callback function to do feedback.
    
    Available Instance Variables:
    - session: The session from which the context originates from
    - message: The message object which this context is created from
    - context_receiver_initiator: initiator to initialize message factory
    - context_receiver_name: name to initialize message factory
    
    It also provides send_message method as a shorthand for sending messages.
    
    If the Context has a message factory, then send_message can build its own message object from the given content, otherwise a message object is required.
    """
    def __init__(self, session: 'Session', message: Message, context_receiver_initiator: Initiator = None, context_receiver_name: Initiator = None):
        self.session = session
        self.message = message
        self.context_receiver_initiator = context_receiver_initiator
        self.context_receiver_name = context_receiver_name
        self.message_factory = None
        try:
            self.message_factory = Message.get_factory(self.context_receiver_initiator, self.context_receiver_name)
        except:
            pass
    
    @property
    def initiator(self):
        return self.message.initiator
    
    def send_message(self, message: Message = None, content : str  = None):
        "Shorthand for Context.session.send_message with built-in message factory"
        if not message:
            if self.message_factory is None:
                raise ValueError("The context is not initialized with the required arguments to create a message from content alone. A message object is required.")
            message = self.message_factory(content)
        self.session.send_message(message)


class Session:
    """
    Session
    ---
    A simplified event driven chat session.
    
    To add an event listener, call .add_listener(event_name, listener_function[, listener_initiator[, listener_name]])
    
    Available events:
    - on_message: calls the listener function with a context object as its argument
    - on_reset: calls the listener function with no arguments
    
    listener_initiator and listener_name is used to create a message factory for Context
    """
    def  __init__(self):
        self.messages = []
        self.listeners = {
            'on_message': [],
            'on_reset': []
        }
        self.sync_lock = Lock()
    
    def add_listener(self, event: str, listener: Callable[[Context], None], listener_initiator: Initiator = None, listener_name: str = None):
        "Adds a listener for the given event, listener, initiator, and name"
        listener_tuple = (listener_initiator, listener_name, listener)
        self.listeners[event].append(listener_tuple)
        
        def remover():
            return self.listeners[event].remove(listener_tuple)
        return remover
    
    def get_messenger(self, initiator: Initiator, name: str = None):
        "Creates a message factory for given initiator and name"
        message_factory = Message.get_factory(initiator, name)
        def closure(content: str):
            return self.send_message(message_factory(content))
        def closure_with_from(name: str, content: str):
            return self.send_message(message_factory(name, content))
        if name:
            return closure
        return closure_with_from
    
    def _send_message(self, message: Message):
        "Internal logic for sending message"
        self.messages.append(message)
    
    def send_message(self, message: Message):
        "Sends message and calls listener bound to event='on_message'"
        with self.sync_lock:
            # print("Sending message: {} with content: {}".format(message, message.content))
            self._send_message(message)
            for (listener_initiator, listener_name, listener) in self.listeners['on_message']:
                try:
                    ctx = Context(self, message, listener_initiator, listener_name)
                    listener(ctx)
                except Exception as exc:
                    print("Caught error while calling listeners for 'on_message'\n> Listener: {}\n> Error:{}".format(listener, exc))
                    raise exc
    
    def reset(self):
        "Clears message and calls listener bound to event='on_reset'"
        self.messages.clear()
        for (_, _, listener) in self.listeners['on_reset']:
            try:
                listener()
            except Exception as exc:
                print("Caught error while calling listeners for 'on_reset'\n> Listener: {}\n> Error:{}".format(listener, exc))
                raise exc

