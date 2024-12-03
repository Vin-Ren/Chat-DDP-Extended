import traceback
from typing import Callable, Optional
from queue import Empty, Queue
from threading import Thread
from functools import partial
from inspect import getfullargspec
from collections import namedtuple

from chat import Context, Session, Initiator


Handler = Callable[[Context], Optional['Handler']]
"Event Handler Generic"


ParsedArg = namedtuple("ParsedArg", ['name', 'required', 'annotation', 'greedy', 'internal'], defaults=(None, False, False))


class BaseFunctionWrapper:
    """
    BaseFunctionWrapper
    ---
    Wraps handler functions to be compatible with the Bot class
    
    Abstracts argument inspection, argument validation, argument casting, and function calls 
    """
    def __init__(self, handler: Handler, require_ctx: bool = False) -> None:
        self.handler = handler
        self.require_ctx = require_ctx
        
        self.handler_argspec = getfullargspec(self.handler)
        self.args = self.handler_argspec.args or []
        self.handler_annotations = self.handler_argspec.annotations
        self.is_class_method = (len(self.args) and self.args[0] == 'self')
        self.parsed_args: list[ParsedArg] = []
        self.required_arg_count = 0
        
        self.prefix_internalized_args_cnt = int(self.is_class_method)
        
        # print(self.handler.__name__, self.handler_argspec)
        if require_ctx:
            self.prefix_internalized_args_cnt += 1
            if (len(self.args)<=int(self.is_class_method) or \
                self.handler_argspec.annotations.get(self.args[int(self.is_class_method)], Context) != Context):
                # print(self.handler_argspec.annotations.get(self.args[0], Context))
                raise RuntimeError("A {} must accept an argument of type Context as its first argument.".format(self.__class__.__name__))
        
        for i in range(self.prefix_internalized_args_cnt):
            self.parsed_args.append(ParsedArg(self.handler_argspec.args[i], True, internal=True))
        
        defaults_cnt = len(self.handler_argspec.defaults or [])
        args_cnt = len(self.handler_argspec.args)
        required_args = self.handler_argspec.args[self.prefix_internalized_args_cnt:args_cnt-defaults_cnt]
        for arg in required_args:
            self.parsed_args.append(ParsedArg(arg, True, annotation=self.handler_argspec.annotations.get(arg, None)))
        
        self.required_arg_count = len(self.parsed_args)
        
        optional_args = self.handler_argspec.args[max(self.prefix_internalized_args_cnt, args_cnt-defaults_cnt):]
        for arg in optional_args:
            self.parsed_args.append(ParsedArg(arg, False, annotation=self.handler_argspec.annotations.get(arg, None)))
        
        kw_defaults_exists = len(self.handler_argspec.kwonlydefaults or [])>0
        kw_only_cnt = len(self.handler_argspec.kwonlyargs)
        assert kw_only_cnt<=1, "A function can have at most one greedy argument."
        if kw_only_cnt:
            self.parsed_args.append(
                ParsedArg(
                    self.handler_argspec.kwonlyargs[0], 
                    greedy=True, 
                    required=not kw_defaults_exists, 
                    annotation=self.handler_argspec.annotations.get(self.handler_argspec.kwonlyargs[0], None)
                )
            )
    
    def __call__(self, *args):
        "A bypass call to the handler"
        new_args,new_kw = self.process_args(*args)
        return self.handler(*new_args, **new_kw)
    
    def process_args(self, *args):
        "Processes given arguments to be compatible with the function's signature"
        new_args = []
        new_kw = {}
        current_idx = 0
        for arg in self.parsed_args:
            try:
                if not arg.greedy:
                    if arg.annotation is not None:
                        new_args.append(arg.annotation(args[current_idx]))
                    else:
                        new_args.append(args[current_idx])
                else:
                    if arg.annotation is not None:
                        new_kw[arg.name] = arg.annotation(" ".join(args[current_idx:]))
                    else:
                        new_kw[arg.name] = " ".join(args[current_idx:])
                    break
                current_idx += 1
            except IndexError as exc:
                if current_idx>=self.required_arg_count:
                    break
                raise RuntimeError("Too little argument received for {}. Got {}, Requires {}. Arguments are={}. Passed args={}".format(
                    self.handler.__name__, len(args), self.required_arg_count, 
                    tuple(e.name for e in self.parsed_args), args)
                ) from exc
        return new_args, new_kw
    
    def validate_args(self, *args: tuple):
        "Validates the arguments against the inspected argument, tries to process the arguments."
        try:
            self.process_args(*args)
            return True
        except RuntimeError as exc:
            print(exc)
            return False


class Command(BaseFunctionWrapper):
    """
    Command
    ---
    Wrapper for command handler functions
    """
    def __init__(self, handler: Handler, description: str = "", prefixes: list[str] = None, is_fallback: bool = False):
        super().__init__(handler, require_ctx=True)
        self.handler = handler
        self.description = description
        self.is_fallback = is_fallback
        self.prefixes = list(prefixes) if prefixes is not None else [self.handler.__name__]
        if self.is_fallback:
            self.prefixes = []
    
    def __repr__(self):
        return "<Command prefixes={} description={} is_fallback={}>".format(self.prefixes, self.description, self.is_fallback)
    
    @classmethod
    def command(cls, *prefixes, description: str = None, is_fallback: bool = False):
        "Decorator for command functions"
        def closure(func: Handler):
            cmd = Command(func, description, prefixes, is_fallback)
            return cmd
        return closure


class Listener(BaseFunctionWrapper):
    """
    Listener
    ---
    Wrapper for event listener functions
    """
    def __init__(self, handler: Callable, event: str):
        super().__init__(handler, require_ctx=False)
        self.event = event
        self.handler = handler
    
    @classmethod
    def listener(cls, event: str):
        "Decorator for event listener functions"
        def closure(func: Handler):
            listener_obj = Listener(func, event)
            return listener_obj
        return closure


class Bot:
    """
    Bot
    ---
    
    <small>Inspired by discord.py's architecture</small>
    
    A base class for Bots, abstracting low level interaction between handler functions and session.
    This class also provides a simple help message for a given bot.
    
    For continuous flow commands, return a handler function for the next reply to continue the command flow, otherwise, return None to end the flow.
    
    Below are two implementations of the same chat bot with or without classes
    
    Example use without classes:
    ```
    # Configurations above, creating a chat_session object
    bot = Bot(chat_session)
    
    # Listener example
    @bot.listener('on_message')
    def on_message(ctx):
        print("[{}] Got a new message from [{}]: {}".format(ctx.message.datetime.iso_format(), ctx.message._from, ctx.message.content))
    
    # Simple command example
    @bot.command('ping')
    def ping(ctx):
        ctx.send_message(content='pong')
    
    # Simple echo command, introducing greedy params
    @bot.command('echo')
    def echo(ctx, *, message):
        ctx.send_message(content='You said: {}'.format(message))
    
    # Continuous command flow example
    # Typing on arguments will be used to automatically transform the arguments
    @bot.command('guess game', 'guessgame')
    def guess_game(ctx, a: int = 1, b: int = 100):
        answer = random.randint(a, b)
        tries_left = 3
        ctx.send_message("Start guessing a number between {} and {}".format(a, b))
        def response_handler(ctx):
            nonlocal tries_left
            msg = ctx.message.content.strip()
            tries_left -= 1
            if not msg.isdigit():
                ctx.send_message(content="Invalid number, you have {} tries left.".format(tries_left))
                return response_handler
            num = int(msg)
            if num == answer:
                ctx.send_message(content="Congratulations, You guessed correctly!")
                return
            if tries_left==0:
                ctx.send_message(content="You failed to guess the correct number, the answer is {}".format(answer))
                return
            
            if num < answer:
                ctx.send_message(content="Higher! ({} tries left)".format(tries_left))
            if num > answer:
                ctx.send_message(content="Lower! ({} tries left)".format(tries_left))
            return response_handler
        return response_handler
    
    @bot.command(is_fallback=True)
    def handle_invalid_command(ctx):
        ctx.send_message(content="The given command is invalid")
    ```
    
    Example use with classes:
    ```
    # Configurations above, creating a chat_session object
    
    class ChatBot(Bot):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
        
        # Listener example
        @listener('on_message')
        def on_message(self, ctx):
            print("[{}] Got a new message from [{}]: {}".format(ctx.message.datetime.iso_format(), ctx.message._from, ctx.message.content))
        
        # Simple command example
        @command('ping')
        def ping(self, ctx):
            ctx.send_message(content='pong')
        
        # Simple echo command, introducing greedy params
        @command('echo')
        def echo(self, ctx, *, message):
            ctx.send_message(content='You said: {}'.format(message))
        
        # Continuous command flow example
        # Typing on arguments will be used to automatically transform the arguments
        @command('guess game', 'guessgame')
        def guess_game(self, ctx, a: int = 1, b: int = 100):
            answer = random.randint(a, b)
            tries_left = 3
            ctx.send_message(content="Start guessing a number between {} and {}".format(a, b))
            def response_handler(ctx):
                nonlocal tries_left
                msg = ctx.message.content.strip()
                tries_left -= 1
                if not msg.isdigit():
                    ctx.send_message(content="Invalid number, you have {} tries left.".format(tries_left))
                    return response_handler
                num = int(msg)
                if num == answer:
                    ctx.send_message(content="Congratulations, You guessed correctly!")
                    return
                if tries_left==0:
                    ctx.send_message(content="You failed to guess the correct number, the answer is {}".format(answer))
                    return
                
                if num < answer:
                    ctx.send_message(content="Higher! ({} tries left)".format(tries_left))
                if num > answer:
                    ctx.send_message(content="Lower! ({} tries left)".format(tries_left))
                return response_handler
            return response_handler
        
        @command(is_fallback=True)
        def handle_invalid_command(self, ctx):
            ctx.send_message(content="The given command is invalid")
    
    bot = ChatBot(chat_session)
    ```
    """
    def __init__(self, chat_session: Session, initiator: Initiator, name: str, case_sensitive: bool = True, default_help_prefixes: list[str] = None):
        self.chat_session = chat_session
        self.initiator = initiator
        self.name = name
        self.__commands: list[Command] = []
        self.__internal_message_queue: Queue[Context] = Queue()
        self.__internal_current_command_flow: Handler | None = None
        self.__case_sensitive = case_sensitive
        self.__default_help_command_index = -1
        self.__commands_used_prefixes = set()
        self.__chat_session_listener_entries = []
        self.__chat_session_listener_removers = []
        self.__default_help_prefixes = default_help_prefixes if default_help_prefixes else ['help']
        
        self.__fallback_command = Command(self.__class__._default_fallback_command, "Default fallback command", is_fallback=True)
        self.__using_default_fallback_command = True
        
        for entry in self.__class__.__dict__.values():
            if isinstance(entry, Command):
                self.add_command(entry)
            if isinstance(entry, Listener):
                self.add_listener(entry)
        
        if not any(prf in self.__commands_used_prefixes for prf in self.__default_help_prefixes):
            self.__default_help_command_index = len(self.__commands)
            self.__commands.append(Command(self.__class__._default_help_command, "Shows this help message or a help message for a specific command", self.__default_help_prefixes))
        
        self.__internal_add_listener('on_message', self.__internal_message_queue_inserter, initiator, name)
        
        self.internal_message_queue_consumer = Thread(target=self.__internal_message_queue_consumer, daemon=True)
        self.internal_message_queue_consumer.start()
    
    def __internal_add_listener(self, event: str, listener: Callable, initiator: Initiator, name):
        "Adds a given listener handler to the chat session"
        self.__chat_session_listener_entries.append((event, listener, initiator, name))
        remover = self.chat_session.add_listener(event, listener, initiator, name)
        self.__chat_session_listener_removers.append(remover)
    
    def __internal_message_queue_inserter(self, ctx: Context):
        "Inserts message into an internally managed queue, only inserts the messages from user"
        if ctx.message.initiator == Initiator.User:
            self.__internal_message_queue.put(ctx)
    
    def __internal_message_queue_consumer(self):
        "Process message from an internal message queue"
        while True:
            try:
                ctx = self.__internal_message_queue.get(timeout=1)
                self.__internal_commands_handler(ctx)
            except Empty:
                pass
            except Exception:
                print(traceback.format_exc())
    
    def __internal_commands_handler(self, ctx: Context):
        "Handles commands based on given ctx"
        if self.__internal_current_command_flow is not None:
            self.__internal_current_command_flow = self.__internal_current_command_flow(ctx)
        else:
            self.__internal_current_command_flow = self.__internal_commands_router(ctx)
    
    def __internal_commands_router(self, ctx: Context):
        "Routes commands to their appropriate handlers"
        msg = ctx.message.content
        if self.__case_sensitive:
            msg = msg.lower()
        
        for command in self.__commands:
            for prefix in command.prefixes:
                if msg.startswith(prefix):
                    args = [ctx] + ctx.message.content.split(prefix)[1].split()
                    if command.is_class_method:
                        args = [self]+args
                    if not command.validate_args(*args):
                        continue
                    return command(*args)
        
        args = [ctx] + ctx.message.content.split()
        if self.__fallback_command.is_class_method:
            args = [self]+args
        return self.__fallback_command(*args)
    
    def reset_state(self):
        "Resets the current state of the bot."
        self.__internal_current_command_flow = None
        self.__internal_message_queue = Queue()
    
    def set_chat_session(self, chat_session: Session):
        "Changes the bot's chat session"
        self.chat_session = chat_session
        for remover in self.__chat_session_listener_removers: remover()
        
        listener_args = self.__chat_session_listener_entries
        self.__chat_session_listener_removers = []
        self.__chat_session_listener_entries = []
        for args in listener_args:
            self.__internal_add_listener(*args)
    
    def add_command(self, command: Command):
        "Adds the given command to the list of internally managed command"
        if self.__default_help_command_index != -1 and any(prf in command.prefixes for prf in self.__default_help_prefixes):
            self.__commands.pop(self.__default_help_command_index)
            self.__default_help_command_index = -1
        
        for pref in command.prefixes:
            if pref in self.__commands_used_prefixes:
                raise RuntimeError("Prefix='{}' violated unique constraint. A prefix should only be used once!".format(pref))
            self.__commands_used_prefixes.add(pref)
        if command.is_fallback:
            if self.__fallback_command is not None and not self.__using_default_fallback_command:
                raise RuntimeError("A bot should only have at most one fallback command!")
            self.__using_default_fallback_command = False
            self.__fallback_command = command
        if not self.__case_sensitive:
            command.prefixes = [pref.lower() for pref in command.prefixes]
        self.__commands.append(command)
    
    def add_listener(self, listener: Listener):
        "Adds the given command to the list of internally managed listeners"
        if listener.is_class_method:
            self.__internal_add_listener(listener.event, partial(listener.handler, self), self.initiator, self.name)
        else:
            self.__internal_add_listener(listener.event, listener.handler, self.initiator, self.name)

    def command(self, *prefixes, description: str = None):
        "Binds the given handler as a command handler of the bot"
        def closure(func: Handler):
            cmd = Command(func, description, prefixes)
            self.add_command(cmd)
            return cmd
        return closure

    def listener(self, event: str):
        "Binds the given handler as a event listener of the bot"
        def closure(func: Handler):
            listener_obj = Listener(func, event)
            self.add_listener(listener_obj)
            return listener_obj
        return closure
    
    def _default_help_command(self, ctx: Context, *, command_prefix):
        "A simple help command"
        if command_prefix:
            matched_command = None
            for command in self.__commands:
                if command_prefix in command.prefixes:
                    matched_command = command
                    break
            if matched_command is None:
                return ctx.send_message(content="Command not found!")
            line = "Below is the information about {}:\n• ".format(command_prefix)
            line += " | ".join(command.prefixes)
            arguments = []
            for arg in command.parsed_args:
                if arg.internal:
                    continue
                brackets = '<{}>' if arg.required else '[{}]'
                name = arg.name if not arg.greedy else '...'+arg.name
                arguments.append(brackets.format(name))
            line += " " + " ".join(arguments)
            if command.description:
                line+=", "+command.description
            return ctx.send_message(content=line)
        
        help_message = "The following are commands supported by this bot:\n"
        for command in self.__commands:
            line = "• "
            prefixes = " | ".join(command.prefixes)
            if len(prefixes) > 25:
                line += prefixes[:25]+'...'
            else:
                line += prefixes
            arguments = []
            for arg in command.parsed_args:
                if arg.internal:
                    continue
                brackets = '<{}>' if arg.required else '[{}]'
                name = arg.name if not arg.greedy else '...'+arg.name
                arguments.append(brackets.format(name))
            line += (" " + " ".join(arguments)) if arguments else ""
            if command.description:
                line+=", "+command.description
            help_message+=line+'\n'
        help_message+="Note: Arguments enclosed with <> are required and arguments enclosed with [] are optional.\n"
        ctx.send_message(content=help_message.strip())
    
    def _default_fallback_command(self, ctx: Context, *, command_str: str):
        ctx.send_message(content="No such command found")
        raise ValueError("Received unrecognizable command={!r}".format(command_str))


command = Command.command

listener = Listener.listener
