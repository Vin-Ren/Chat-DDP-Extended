from tkinter import Tk, Widget, TclError, Menu, Frame, Text, Entry, Button, Scrollbar

from chat import Initiator


class DefaultWidget:
    pass


THEME_PRESETS = {
    'light-mode': { # https://colorhunt.co/palette/295f98cdc2a5e1d7c6eae4dd
        # Tk: {
            
        # },
        Menu: {
            
        },
        # Frame: {
            
        # },
        Text: {
            'bg': '#EAE4DD',
            'fg': '#17153B',
            'font': ('Segoe UI', 12),
            'highlightcolor': '#295F98'
        },
        Entry: {
            'bg': '#EAE4DD',
            'fg': '#17153B',
            'font': ('Segoe UI', 12)
        },
        # Button: {
            
        # },
        Scrollbar: {
            'bg': '#E1D7C6',
            'activecolor': '#17153B',
            # 'gripcolor': '#222222'
        },
        DefaultWidget: {
            'bg': '#E1D7C6',
            'fg': '#17153B',
            'font': ('Segoe UI', 10),
        },
        '_from_highlight': {
            Initiator.ChatBot: '#CB80AB',
            Initiator.User: '#295F98',
            Initiator.Network: '#DE8B60',
            Initiator.System: '#117700'
        }
    },
    'dark-mode': { # https://colorhunt.co/palette/22283131363f76abaeeeeeee
        # Tk: {
            
        # },
        Menu: {
            
        },
        # Frame: {
            
        # },
        Text: {
            'bg': '#31363F',
            'fg': '#eeeeee',
            'font': ('Segoe UI', 12),
            'highlightcolor': '#76ABAE'
        },
        Entry: {
            'bg': '#31363F',
            'fg': '#eeeeee',
            'font': ('Segoe UI', 12),
        },
        # Button: {
            
        # },
        Scrollbar: {
            'bg': '#222831',
            'activecolor': '#ffffff',
            # 'gripcolor': '#dddddd'
        },
        DefaultWidget: {
            'bg': '#222831',
            'fg': '#dddddd',
            'font': ('Segoe UI', 10),
        },
        '_from_highlight': {
            Initiator.ChatBot: '#A888B5',
            Initiator.User: '#76ABAE',
            Initiator.Network: '#FFB38E',
            Initiator.System: '#55CC55'
        }
    }
}
"""
THEME_PRESETS
---

Contains the themes presets in the following structure:
- {theme-name}
    - {Class}
        - Class specific config in dictionary form
    - ....
- ....
"""


class ThemeManager:
    """
    ThemeManager
    ---
    
    Manages the theme of a tkinter app with given THEME_PRESETS
    """
    def __init__(self, root: Tk | Widget):
        self._theme = list(THEME_PRESETS.keys())[0]
        self.root = root
        self.callbacks = []
        
        self.apply_theme_recursively(self.root)
    
    def add_callback(self, func):
        self.callbacks.append(func)
    
    @property
    def theme(self):
        "Current selected theme"
        return self._theme
    
    @theme.setter
    def theme(self, value):
        "Sets theme to any of the available themes in THEME_PRESETS"
        if value in THEME_PRESETS:
            self._theme = value
            self.apply_theme_recursively(self.root)
            for callback in self.callbacks:
                callback(THEME_PRESETS[self.theme])
        else:
            raise ValueError("Invalid theme!")
    
    def apply_theme_recursively(self, widget: Widget):
        "Applies theme recursively to all of a widget's children"
        config = {}
        if widget.__class__ in THEME_PRESETS[self.theme]:
            config = THEME_PRESETS[self.theme][widget.__class__]
        else:
            config = THEME_PRESETS[self.theme][DefaultWidget]
        
        for key,value in config.items():
            try:
                widget.configure({key:value})
            except TclError as _:
                pass
        for entry in widget.children.values():
            self.apply_theme_recursively(entry)
    
    def cycle_theme(self, rotation: int = 1):
        "Cycles the theme of the root widget and its children by rotation amount and immediately applying it"
        theme_names = list(THEME_PRESETS.keys())
        self.theme = theme_names[(theme_names.index(self.theme)+rotation)%len(theme_names)]
