from tkinter import Menu
from typing import Callable


class PreparedMenu:
    """
    PreparedMenu
    ---
    Encapsulates a Menu initialization process
    """
    def __init__(self, label):
        self.label = label
        self.entries = []
        self.menu = None
    
    def add_command(self, label, command: Callable):
        self.entries.append(("command", {'label':label, 'command':command}))
        return self
    
    def add_seperator(self):
        self.entries.append(("seperator", None))
        return self

    def apply(self, menubar: Menu):
        self.menu = Menu(menubar, tearoff=0)
        for (_type, kwargs) in self.entries:
            if _type == "command":
                self.menu.add_command(kwargs)
            if _type == "seperator":
                self.menu.add_separator()
        menubar.add_cascade(label=self.label, menu=self.menu)
        return self
