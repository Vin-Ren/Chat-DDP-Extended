from tkinter import Tk, Widget, Frame, NSEW


class Section:
    """
    A simple HTML's div imitation for Tkinter
    """
    def __init__(self, master: Tk | Widget, frame_cnf: dict = None):
        self.section_frame = Frame(master)
        self.section_frame_cnf = {'padx':10, 'pady':5, 'sticky': NSEW}
        self.section_frame_cnf.update(frame_cnf if frame_cnf is not None else {})
    
    def manage_geom(self):
        "Manage geometries of all widgets which are contained in subclasses of Section"
        self.section_frame.grid(self.section_frame_cnf)
        return self
