from datetime import datetime
import os
import sys
from threading import Thread
from tkinter import PhotoImage, Tk, Widget, Frame, Button, Entry, Text, Menu, Scrollbar, LEFT, BOTH, X, Y, StringVar, END, NORMAL, DISABLED, INSERT
from tkinter.messagebox import showinfo, showerror
from functools import partial
import traceback
from typing import Callable

from utils import get_filename_in_cwd
from theme import ThemeManager
from chat import Session as ChatSession, Initiator, Context
from chatbot import ChatBot
from netbot import NetBot
from section import Section
from prepared_menu import PreparedMenu



class ChatLogSection(Section):
    """
    ChatLogSection
    ---
    Wraps the entire chat log section in a nicely packed class. 
    
    Handles the chat display, scrolling, highlighting, and chat session save as well as reset
    """
    def __init__(self, master: Tk | Widget, frame_cnf: dict = None, chat_session: ChatSession = None, show_time = False):
        super().__init__(master, frame_cnf)
        self.inner_frame = Frame(self.section_frame)
        
        self.chat_session = None
        self.show_time = show_time
        
        self.chat_log_content: dict[ChatSession, str] = {}
        self.chat_log_highlights: dict[ChatSession, tuple[str, str]] = {}
        self.chat_session_listener_removers = []
        self.cached_highlight_theme = {}
        "Maps initiator to its highlight color"
        
        self.chat_log = Text(self.inner_frame, wrap="word", width=25)
        self.chat_log_scrollbar = Scrollbar(self.inner_frame, command=self.chat_log.yview)
        self.chat_log.config(yscrollcommand=self.chat_log_scrollbar.set)
        
        self.set_chat_session(chat_session)
    
    def manage_geom(self):
        self.inner_frame.pack(side=LEFT, fill=BOTH, expand=1)
        self.chat_log.pack(side=LEFT, fill=BOTH, expand=1)
        self.chat_log_scrollbar.pack(side=LEFT, fill=Y)
        return super().manage_geom()
    
    def set_chat_session(self, chat_session: ChatSession):
        "Updates the chat session which the object is bound to, updates listeners, reconfiguring chat log content and highlights."
        self.on_reset()
        for remover in self.chat_session_listener_removers: remover()
        
        self.chat_session = chat_session
        self.chat_session_listener_removers = [
            self.chat_session.add_listener('on_message', self.on_message),
            self.chat_session.add_listener('on_reset', self.on_reset)
        ]
        self.chat_log.configure(state=NORMAL)
        self.chat_log_content[self.chat_session] = self.chat_log_content.get(self.chat_session, '')
        self.chat_log_highlights[self.chat_session] = self.chat_log_highlights.get(self.chat_session, [])
        
        self.chat_log.insert(END, self.chat_log_content[self.chat_session])
        
        for (highlight_tag, start_idx, end_idx) in self.chat_log_highlights[self.chat_session]:
            self.chat_log.tag_add(highlight_tag, start_idx, end_idx)
        
        self.chat_log.yview_moveto(1)
        self.chat_log.configure(state=DISABLED)
    
    def on_theme_change(self, theme):
        for initiator in Initiator:
            self.cached_highlight_theme[initiator] = {
                'tagName': "_from_highlight_"+initiator.value, 
                'foreground': theme['_from_highlight'][initiator]
            }
            self.chat_log.tag_configure(**self.cached_highlight_theme[initiator])
    
    def on_message(self, ctx: Context):
        "Inserts message entries based on bound chat session, then highlight the sender's name and save the entry to be reused upon chat session switching"
        self.chat_log.configure(state=NORMAL)
        self.chat_log.mark_set(INSERT, END) # Fixes _from_highlight when part of text is selected
        
        message = ctx.message
        prefix = "[{}] ".format(message.datetime.strftime("%H:%M:%S")) if self.show_time else ""
        prefix += "{}: ".format(message._from)
        highlight_tag = "_from_highlight_"+ctx.message.initiator.value
        
        # Inserts the prefix and get the start and end index for the prefix
        start_idx = self.chat_log.index(INSERT)
        self.chat_log.insert(END, prefix)
        end_idx = self.chat_log.index(INSERT)
        
        # Highlights it
        self.chat_log.tag_configure(**self.cached_highlight_theme[ctx.message.initiator])
        self.chat_log.tag_add(highlight_tag, start_idx, end_idx)
        self.chat_log_highlights[self.chat_session].append((highlight_tag, start_idx, end_idx))
        
        self.chat_log.insert(END, message.content+'\n')
        self.chat_log_content[self.chat_session]+=prefix+message.content+'\n'
        # self.chat_log.select
        
        self.chat_log.yview_moveto(1)
        self.chat_log.configure(state=DISABLED)
    
    def save(self, filename: str, success_callback: Callable, failed_callback: Callable):
        "Saves the content of the current bound session to a file"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(self.chat_log.get("1.0", END))
            return success_callback()
        return failed_callback()
    
    def on_reset(self):
        "Resets the current bound session's log on this chat log"
        self.chat_log.configure(state=NORMAL)
        self.chat_log.delete("1.0", END)
        self.chat_log.configure(state=DISABLED)


class ActionSection(Section):
    """
    ActionSection
    ---
    
    Wraps basic commands in a row of command buttons as well as an additional special feature button.
    """
    def __init__(self, master: Tk | Widget, frame_cnf: dict = None, chat_session: ChatSession = None, special_command: Callable = None):
        super().__init__(master, frame_cnf)
        self.centered_frame = Frame(self.section_frame, width=300)
        self.chat_session = None
        self.messenger = None
        self.xyz_is_local = True
        self.special_command = special_command
        
        self.joke_button = Button(self.centered_frame, text="Buat Lelucon", command=partial(self.send_message, "buat lelucon"))
        self.time_button = Button(self.centered_frame, text="Tanya Jam", command=partial(self.send_message, "tanya jam"))
        self.math_button = Button(self.centered_frame, text="Soal Matematika", command=partial(self.send_message, "beri aku soal matematika"))
        self.xyz_button = Button(self.centered_frame, text="Connect to Network", command=self.special_command_wrapper)
        "The special button"
        
        self.set_chat_session(chat_session)
    
    def manage_geom(self):
        self.centered_frame.pack(expand=1)
        self.joke_button.pack(side=LEFT, padx=5, fill=X)
        self.time_button.pack(side=LEFT, padx=5, fill=X)
        self.math_button.pack(side=LEFT, padx=5, fill=X)
        self.xyz_button.pack(side=LEFT, padx=5, fill=X)
        return super().manage_geom()
    
    def set_chat_session(self, chat_session: ChatSession):
        self.chat_session = chat_session
        self.messenger = self.chat_session.get_messenger(Initiator.User, Initiator.User)
    
    def special_command_wrapper(self):
        "Changes the state of actions button and calls the special command handler"
        self.xyz_is_local ^= True
        if self.xyz_is_local:
            self.xyz_button.config(text="Connect to network")
            self.joke_button.config(state=NORMAL)
            self.time_button.config(state=NORMAL)
            self.math_button.config(state=NORMAL)
        else:
            self.xyz_button.config(text="Disconnect from network")
            self.joke_button.config(state=DISABLED)
            self.time_button.config(state=DISABLED)
            self.math_button.config(state=DISABLED)
        self.special_command()
    
    def send_message(self, content: str):
        return self.messenger(content)


class InputSection(Section):
    """
    InputSection
    ---
    
    Wraps the Input entry widget and the send button
    """
    def __init__(self, master: Tk | Widget, frame_cnf: dict = None, chat_session: ChatSession = None):
        frame_cnf = frame_cnf if frame_cnf is not None else {}
        super().__init__(master, frame_cnf)
        self.centered_frame = Frame(self.section_frame)
        self.chat_session = None
        self.messenger = None
        self.name = Initiator.User
        
        self.input_contents = StringVar(self.section_frame, "")
        self.input_box = Entry(self.centered_frame, textvariable=self.input_contents)
        self.send_button = Button(self.centered_frame, text="Kirim", command=self.send_handler)
        self.input_box.bind("<Return>", self.send_handler)
        
        self.set_chat_session(chat_session)
    
    def manage_geom(self):
        self.centered_frame.pack(fill=X, expand=1)
        self.input_box.pack(side=LEFT, fill=X, expand=1)
        self.send_button.pack(side=LEFT, padx=5)
        return super().manage_geom()
    
    def set_chat_session(self, chat_session):
        self.chat_session = chat_session
        self.messenger = self.chat_session.get_messenger(Initiator.User, self.name)
    
    def set_name(self, name: str):
        self.name = name
        self.messenger = self.chat_session.get_messenger(Initiator.User, self.name)
    
    def send_message(self, content: str):
        return self.messenger(content)
    
    def send_handler(self, *args):
        content = self.input_contents.get().strip()
        if len(content)==0:
            return
        self.send_message(content)
        self.input_contents.set("")


class App:
    def __init__(self):
        # Global configurations
        self.window = Tk()
        self.window.title("Chat-DDP-Extended")
        self.window.iconphoto(True, PhotoImage(file=get_filename_in_cwd("icon.png")))
        
        self.window.geometry("550x500")
        self.window.minsize(550,400)
        
        self.window.grid_columnconfigure(0, weight=1)  # Allow the column to expand
        self.window.grid_rowconfigure(0, weight=1)
        
        
        self.theme_manager = ThemeManager(self.window)
        
        # App Logic configuration
        self.chat_sessions = [
            ChatSession(), # Local chat session
            ChatSession() # Network connected chat session
        ]
        self.usernames = [
            Initiator.User,
            Initiator.User
        ]
        self.chatbot = ChatBot(self.chat_sessions[0]) # Only for the local session
        self.netbot = NetBot(self.chat_sessions[1], self.handle_username_change)
        
        # Menus configuration
        self.menubar = Menu(self.window, tearoff=0)
        self.window.config(menu=self.menubar)
        
        self.file_menu = PreparedMenu("File") \
            .add_command("Simpan Sesi", self.save_chat_session) \
            .add_command("Reset Sesi", self.reset_chat_session) \
            .add_seperator() \
            .add_command("Keluar", sys.exit) \
            .apply(self.menubar)
        
        self.theme_menu = PreparedMenu("Tema") \
            .add_command("Ubah Tema", self.theme_manager.cycle_theme) \
            .apply(self.menubar)
        
        self.about_menu = PreparedMenu("Tentang") \
            .add_command("Tentang Aplikasi", self.show_about) \
            .apply(self.menubar)
        
        self.help_menu = PreparedMenu("Bantuan") \
            .add_command("Bantuan", self.show_help) \
            .apply(self.menubar)
        
        # Sections configuration
        self.chat_log_section = ChatLogSection(self.window, {'row':0}, self.chat_session) \
            .manage_geom()
        
        self.actions_section = ActionSection(self.window, {'row':1}, self.chat_session, self.special_command) \
            .manage_geom()
        
        self.input_section = InputSection(self.window, {'row':2, 'pady':20}, self.chat_session) \
            .manage_geom()
        
        # Final setups
        self.chat_log_setup()
        self.theme_manager.add_callback(self.chat_log_section.on_theme_change)
        self.theme_manager.cycle_theme(0)
    
    @property
    def chat_session(self):
        return self.chat_sessions[0]
    
    @property
    def username(self):
        return self.usernames[0]
    
    @username.setter
    def username(self, val):
        self.usernames[0] = val
    
    def run(self):
        self.window.mainloop()
    
    def special_command(self):
        "Runs everytime the special command button is pressed"
        self.chat_sessions.reverse()
        self.usernames.reverse()
        
        self.chat_log_section.show_time ^= True # Flips everytime
        self.chat_log_section.set_chat_session(self.chat_session)
        self.actions_section.set_chat_session(self.chat_session)
        self.input_section.set_chat_session(self.chat_session)
        self.input_section.set_name(self.username)
    
    def chat_log_setup(self):
        # Initial prompt of main chat session
        initial_prompt = "Halo! Apakah anda perlu sesuatu? Untuk bantuan penggunaan, silahkan ketik 'help' tanpa tanda petik.\n"
        self.chat_log_section.chat_log_content[self.chat_sessions[0]] = initial_prompt
        
        # Initial prompt of secondary network enabled chat session
        initial_prompt = "Welcome to the network enabled session (English only)!\nTo host a server, run '/startserver' to start a server followed by '/connect' to join the self-hosted server.\nTo join a server hosted by another user, run the command '/connect <IP> <PORT>' where IP and PORT are given by the server hoster.\nFor more commands, run '/help' without quotes.\n"
        self.chat_log_section.chat_log_content[self.chat_sessions[1]] = initial_prompt
        
        # Refresh chat log section
        self.chat_log_section.set_chat_session(self.chat_session)
    
    def handle_username_change(self, new_name):
        self.username = new_name
        self.input_section.set_name(self.username)
    
    def save_chat_session(self):
        filename = datetime.now().strftime("chat_session_%Y_%m_%d_%H-%M-%S.txt")
        success_callback = partial(showinfo, "Sukses", "Sesi percakapan berhasil disimpan sebagai '{}'".format(filename))
        failed_callback = partial(showerror, "Gagal", "Gagal menulis percakapan pada file '{}'".format(filename))
        self.chat_log_section.save(filename, success_callback, failed_callback)
    
    def _reset_chat_session(self):
        "Resets chat session and their respective bots"
        if self.chat_session == self.chatbot.chat_session:
            self.chatbot.reset_state()
        if self.chat_session == self.netbot.chat_session:
            self.netbot.reset_state()
        self.chat_session.reset()
    
    def reset_chat_session(self):
        "A wrapper for the reset function, avoiding blocking issues"
        Thread(target=self._reset_chat_session).start()
    
    def show_about(self):
        showinfo("Tentang Aplikasi", "Aplikasi Chatbot ini dikembangkan oleh Vincent Valentino Oei dari Fasilkom UI di tahun 2024.\nSemoga aplikasi ini dapat menjadi pembelajaran yang bermanfaat, have a great day!")
    
    def show_help(self):
        showinfo("Bantuan", "Untuk chat session lokal (default), masukkan 'help' tanpa tanda kutip ke dalam kolom masukkan dan tekan enter/kirim.\nSedangkan untuk chat session online (setelah klik 'Connect to Network'), masukkan '/help' ke dalam kolom masukkan dan tekan enter/kirim.")


if __name__ == '__main__':
    print("Exceptions showing up here is for debugging purposes.")
    try:
        app = App()
        app.run()
    except:
        traceback.print_exc()
